from flask import (
    Flask, render_template, request, redirect,
    session, Response, send_file, jsonify,
    current_app
)
import uuid

from db import (
    execute, fetchone, fetchall, commit, sql,
    init_db, close_db, today_clause, get_db
)

import cloudinary
import cloudinary.uploader

from auth import login_required

import os, json, time, qrcode
from zipfile import ZipFile
from reportlab.pdfgen import canvas
from flask_dance.contrib.google import make_google_blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from menu_templates import MENU_TEMPLATES
from decimal import Decimal
from datetime import datetime
def serialize_row(row):
    return {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in dict(row).items()
    }


def json_safe(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
BASE_URL = os.getenv(
    "BASE_URL",
    "http://127.0.0.1:5000"
)

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_SECURE=bool(os.getenv("RENDER")),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

app.secret_key = "saas_qr_restaurant_secret"

init_db()
app.teardown_appcontext(close_db)

UPLOAD_FOLDER = "static/uploads"
QR_FOLDER = "static/qr"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

# --------------------------------------------------
# GOOGLE AUTH (optional)
# --------------------------------------------------

google_bp = make_google_blueprint(
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_CLIENT_SECRET",
    scope=["profile", "email"]
)
app.register_blueprint(google_bp, url_prefix="/login")

# --------------------------------------------------
# AUTH
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = fetchone(
            sql("SELECT * FROM users WHERE username=?"),
            (request.form["username"],)
        )

        if not user or not check_password_hash(user["password"], request.form["password"]):
            return render_template("login.html", error="Invalid email or password")

        if not user:
            return render_template(
                "login.html",
                error="Account not found or invalid password"
            )

        session["user"] = user["username"]
        session["role"] = user["role"]
        session["restaurant_id"] = user["restaurant_id"]

        if user["role"] == "superadmin":
            return redirect("/platform/restaurants")
        elif user["role"] == "admin":
            return redirect("/admin")
        else:
            return redirect("/kitchen")

    return render_template("login.html")
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        user = fetchone(
            sql("SELECT id FROM users WHERE username=?"),
            (email,)
        )

        if not user:
            return render_template(
                "forgot_password.html",
                error="No account found with this email"
            )

        return render_template(
            "forgot_password.html",
            success="Password reset link sent (demo mode)"
        )

    return render_template("forgot_password.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        subdomain = request.form["subdomain"].strip().lower()

        # 🔴 CHECK EMAIL
        if fetchone(
            sql("SELECT id FROM users WHERE username=?"),
            (email,)
        ):
            return render_template(
                "signup.html",
                error="This email is already registered. Please login."
            )

        # 🔴 CHECK SUBDOMAIN
        if fetchone(
            sql("SELECT id FROM restaurants WHERE subdomain=?"),
            (subdomain,)
        ):
            return render_template(
                "signup.html",
                error="This subdomain is already taken."
            )

        try:
            # ✅ CREATE RESTAURANT
            cursor = execute(sql("""
                INSERT INTO restaurants (name, subdomain, gstin, phone, address)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
            """), (
                request.form["restaurant_name"],
                subdomain,
                request.form.get("gstin"),
                request.form.get("phone"),
                request.form.get("address")
            ))

            # ✅ GET ID (Postgres vs SQLite)
            if os.getenv("DB_TYPE") == "postgres":
                restaurant_id = cursor.fetchone()["id"]
            else:
                restaurant_id = cursor.lastrowid

            # ✅ CREATE ADMIN USER
            hashed_pw = generate_password_hash(request.form["password"])

            execute(sql("""
                INSERT INTO users (restaurant_id, username, password, role)
                VALUES (?, ?, ?, ?)
            """), (
                restaurant_id,
                email,
                hashed_pw,
                "admin"
            ))

            commit()

        except Exception as e:
            current_app.logger.exception(e)

            if os.getenv("DB_TYPE", "sqlite") == "sqlite":
                db = get_db()
                db.rollback()

            return render_template(
                "signup.html",
                error="Something went wrong. Please try again."
            )


        # ✅ AUTO LOGIN
        session.clear()
        session["user"] = email
        session["role"] = "admin"
        session["restaurant_id"] = restaurant_id

        return redirect("/admin")

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# --------------------------------------------------
# PLATFORM (SUPERADMIN)
# --------------------------------------------------

@app.route("/platform/restaurants")
@login_required("superadmin")
def platform_restaurants():
    rows = fetchall(sql("""
        SELECT r.id, r.name, r.subdomain,
       COUNT(o.id) AS total_orders,
       COALESCE(SUM(o.total), 0) AS total_revenue
        FROM restaurants r
        LEFT JOIN orders o ON r.id=o.restaurant_id
        GROUP BY r.id
        ORDER BY r.id DESC
    """))

    return render_template(
        "platform_restaurants.html",
        restaurants=[dict(r) for r in rows]
    )

# --------------------------------------------------
# CUSTOMER
# --------------------------------------------------


@app.route("/customer/<restaurant>")
def customer(restaurant):
    r = fetchone(
        sql("SELECT * FROM restaurants WHERE subdomain=?"),
        (restaurant,)
    )

    if not r:
        return "Restaurant not found", 404

    menu = fetchall(
        sql("SELECT * FROM menu WHERE restaurant_id=? AND available=TRUE"),
        (r["id"],)
    )

    return render_template(
        "customer.html",
        menu=[dict(m) for m in menu],
        restaurant_name=r["name"],
        restaurant_id=r["id"],
        table=request.args.get("table")
    )


@app.route("/order", methods=["POST"])
def place_order():
    data = request.get_json()
    restaurant_id = data["restaurant_id"]
    table_no = data["table"]
    items = data["items"]

    # 🔎 Find existing OPEN order for table
    existing = fetchone(sql("""
        SELECT id, items, total
        FROM orders
        WHERE restaurant_id=? AND table_no=? AND status!='Closed'
        ORDER BY id DESC
        LIMIT 1
    """), (restaurant_id, table_no))

    new_items = [{
        "name": i["name"],
        "price": float(i["price"]),
        "qty": int(i["qty"])
    } for i in items]

    new_total = sum(i["price"] * i["qty"] for i in new_items)

    # ✅ CASE 1: APPEND TO EXISTING ORDER
    if existing:
        old_items = (
            existing["items"]
            if isinstance(existing["items"], list)
            else json.loads(existing["items"] or "[]")
        )

        combined_items = old_items + new_items
        updated_total = float(existing["total"]) + new_total

        execute(sql("""
            UPDATE orders
            SET items=?, total=?
            WHERE id=?
        """), (
            json.dumps(combined_items),
            updated_total,
            existing["id"]
        ))

        commit()
        return jsonify({"success": True, "order_id": existing["id"]})

    # ✅ CASE 2: CREATE NEW ORDER
    execute(sql("""
        INSERT INTO orders
        (restaurant_id, table_no, customer_name, items, total, status, created_at)
        VALUES (?,?,?,?,?, 'Received', CURRENT_TIMESTAMP)
    """), (
        restaurant_id,
        table_no,
        data.get("customer_name", ""),
        json.dumps(new_items),
        new_total
    ))

    commit()
    return jsonify({"success": True})


# --------------------------------------------------
# ADMIN & KITCHEN
# --------------------------------------------------

@app.route("/admin")
@login_required(["admin", "superadmin"])
def admin():
    return render_template("admin.html")

@app.route("/api/order/<int:order_id>/add-item", methods=["POST"])
@login_required("admin")
def add_item_to_order(order_id):
    data = request.json
    qty = int(data["qty"])
    item_id = data["item_id"]

    # 1️⃣ Fetch menu item
    item = fetchone(sql("""
        SELECT name, price
        FROM menu
        WHERE id=? AND restaurant_id=?
    """), (item_id, session["restaurant_id"]))

    if not item:
        return jsonify({"error": "Menu item not found"}), 404

    price = float(item["price"])

    # 2️⃣ Fetch order
    order = fetchone(sql("""
        SELECT items, total, table_no
        FROM orders
        WHERE id=? AND restaurant_id=?
    """), (order_id, session["restaurant_id"]))

    if not order:
        return jsonify({"error": "Order not found"}), 404

    # 3️⃣ Parse items
    items = order["items"]
    if isinstance(items, str):
        items = json.loads(items)
    if not items:
        items = []

    # 4️⃣ Add item
    items.append({
    "id": str(uuid.uuid4()),   # 🔥 UNIQUE
    "name": item["name"],
    "price": price,
    "qty": qty
    })


    new_total = float(order["total"]) + (price * qty)

    # 5️⃣ Update order
    execute(sql("""
        UPDATE orders
        SET items=?, total=?
        WHERE id=? AND restaurant_id=?
    """), (
        json.dumps(items),
        new_total,
        order_id,
        session["restaurant_id"]
    ))

    # 6️⃣ Kitchen addition
    execute(sql("""
        INSERT INTO order_additions
        (order_id, restaurant_id, table_no, item_name, qty, price, status, created_at)
        VALUES (?,?,?,?,?,?,'New',CURRENT_TIMESTAMP)
    """), (
        order_id,
        session["restaurant_id"],
        order["table_no"],
        item["name"],
        qty,
        price
    ))

    commit()
    return jsonify({"success": True})


# -----------------------
#    KITCHEN
# --------------------    

@app.route("/kitchen")
@login_required("kitchen")
def kitchen():
    return render_template("kitchen.html")

# 🔥 ONLY NEW ADDITIONS
@app.route("/api/kitchen/additions")
@login_required("kitchen")
def api_kitchen_additions():
    rid = session["restaurant_id"]

    rows = fetchall(sql("""
        SELECT *
        FROM order_additions
        WHERE restaurant_id=?
        AND status='New'
        ORDER BY created_at ASC
        LIMIT 50
    """), (rid,))

    return jsonify([
        {k: json_safe(v) for k, v in dict(r).items()}
        for r in rows
    ])


@app.route("/api/kitchen/addition/<int:id>/status", methods=["POST"])
@login_required("kitchen")
def update_addition_status(id):
    execute(sql("""
        UPDATE order_additions
        SET status='Preparing'
        WHERE id=? AND restaurant_id=?
    """), (id, session["restaurant_id"]))

    commit()
    return jsonify({"success": True})


# ====== ADMIN PROFILE ========#
@app.route("/admin/profile", methods=["GET", "POST"])
@login_required("admin")
def admin_profile():
    rid = session["restaurant_id"]

    if request.method == "POST":
        execute(sql("""
            UPDATE restaurants
            SET name = ?, gstin = ?, address = ?, phone = ?
            WHERE id = ?
        """), (
            request.form["name"],
            request.form["gstin"],
            request.form["address"],
            request.form["phone"],
            rid
        ))

        commit()
        return redirect("/admin/profile")

    restaurant = fetchone(sql("""
        SELECT name, gstin, address, phone
        FROM restaurants
        WHERE id=?
    """), (rid,))

    return render_template(
        "admin_profile.html",
        restaurant=restaurant,
        email=session["user"]
    )

@app.route("/admin/orders/by-date")
@login_required("admin")
def orders_by_date():
    date = request.args.get("date")  # YYYY-MM-DD
    rid = session["restaurant_id"]

    if not date:
        return jsonify({"error": "Date required"}), 400

    orders = fetchall(sql("""
        SELECT *
        FROM orders
        WHERE restaurant_id=?
        AND DATE(created_at)=?
        ORDER BY id DESC
    """), (rid, date))

    revenue_row = fetchone(sql("""
        SELECT COALESCE(SUM(total), 0) AS revenue
        FROM orders
        WHERE restaurant_id=?
        AND status='Served'
        AND DATE(created_at)=?
    """), (rid, date))

    return jsonify({
        "orders": [dict(o) for o in orders],
        "revenue": revenue_row["revenue"],
        "count": len(orders)
    })


# ================= KITCHEN USERS (ADMIN) =================

@app.route("/admin/kitchen-users")
@login_required("admin")
def kitchen_users():
    users = fetchall(sql("""
        SELECT id, username
        FROM users
        WHERE restaurant_id=? AND role='kitchen'
        ORDER BY id DESC
    """), (session["restaurant_id"],))

    return render_template(
        "kitchen_users.html",
        users=[dict(u) for u in users]
    )


@app.route("/api/kitchen-users", methods=["POST"])
@login_required("admin")
def create_kitchen_user():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email & password required"}), 400

    # ❗ Prevent duplicate user
    if fetchone(
        sql("SELECT id FROM users WHERE username=?"),
        (email,)
    ):
        return jsonify({"error": "User already exists"}), 400

    hashed_pw = generate_password_hash(password)

    execute(sql("""
        INSERT INTO users (restaurant_id, username, password, role)
        VALUES (?, ?, ?, 'kitchen')
    """), (
        session["restaurant_id"],
        email,
        hashed_pw
    ))

    commit()
    return jsonify({"success": True})

@app.route("/api/kitchen-users/<int:user_id>", methods=["DELETE"])
@login_required("admin")
def delete_kitchen_user(user_id):
    execute(sql("""
        DELETE FROM users
        WHERE id=? AND role='kitchen' AND restaurant_id=?
    """), (user_id, session["restaurant_id"]))

    commit()
    return jsonify({"success": True})


# --------------------------------------------------
# MENU MANAGEMENT
# --------------------------------------------------

@app.route("/menu")
@login_required("admin")
def menu_page():
    return render_template("menu.html")


@app.route("/api/menu")
@login_required("admin")
def api_get_menu():
    rows = fetchall(
        sql("""
            SELECT * FROM menu
            WHERE restaurant_id=?
            ORDER BY id DESC
        """),
        (session["restaurant_id"],)
    )

    return jsonify([dict(r) for r in rows])



@app.route("/api/menu", methods=["POST"])
@login_required("admin")
def api_add_menu():
    image = request.files.get("image")
    if not image:
        return jsonify({"error": "Image required"}), 400

    # 🔥 Upload to Cloudinary
    result = cloudinary.uploader.upload(
        image,
        folder="menu_images"
    )

    image_url = result["secure_url"]

    execute(sql("""
        INSERT INTO menu
        (restaurant_id, name, price, category, image, available)
        VALUES (?,?,?,?,?,TRUE)
    """), (
        session["restaurant_id"],
        request.form["name"],
        float(request.form["price"]),
        request.form["category"],
        image_url
    ))

    commit()
    return jsonify({"success": True})


@app.route("/api/menu/toggle/<int:item_id>", methods=["POST"])
@login_required("admin")
def toggle_menu(item_id):
    execute(sql("""
        UPDATE menu
        SET available = NOT available
        WHERE id=? AND restaurant_id=?
    """), (item_id, session["restaurant_id"]))
    commit()
    return jsonify({"success": True})


@app.route("/api/menu/<int:item_id>", methods=["DELETE"])
@login_required("admin")
def delete_menu(item_id):
    execute(
        sql("DELETE FROM menu WHERE id=? AND restaurant_id=?"),
        (item_id, session["restaurant_id"])
    )
    commit()
    return jsonify({"success": True})

@app.route("/api/menu/import", methods=["POST"])
@login_required("admin")
def import_menu_template():
    data = request.json
    template = data.get("template")

    if template not in MENU_TEMPLATES:
        return jsonify({"error": "Invalid template"}), 400

    restaurant_id = session["restaurant_id"]

    for name, category in MENU_TEMPLATES[template]:
        execute(sql("""
            INSERT INTO menu (restaurant_id, name, price, category, image, available)
            VALUES (?, ?, ?, ?, ?, TRUE)
        """), (
            restaurant_id,
            name,
            0.0,
            category,
            ""   # no image initially
        ))

    commit()
    return jsonify({"success": True})

@app.route("/api/menu/<int:item_id>", methods=["PUT"])
@login_required("admin")
def update_menu_item(item_id):
    name = request.form.get("name")
    price = request.form.get("price")
    category = request.form.get("category")
    image = request.files.get("image")

    if image:
        result = cloudinary.uploader.upload(
            image,
            folder="menu_images"
        )
        image_url = result["secure_url"]

        execute(sql("""
            UPDATE menu
            SET name=?, price=?, category=?, image=?
            WHERE id=? AND restaurant_id=?
        """), (
            name,
            float(price),
            category,
            image_url,
            item_id,
            session["restaurant_id"]
        ))

    else:
        execute(sql("""
            UPDATE menu
            SET name=?, price=?, category=?
            WHERE id=? AND restaurant_id=?
        """), (
            name,
            float(price),
            category,
            item_id,
            session["restaurant_id"]
        ))


    commit()
    return jsonify({"success": True})

# --------------------------------------------------
# ORDER STATUS
# --------------------------------------------------

@app.route("/api/order/<int:order_id>/status", methods=["POST"])
@login_required("kitchen")
def update_order_status(order_id):
    status = request.json.get("status")

    if status not in ["Preparing", "Ready", "Served"]:
        return jsonify({"error": "Invalid status"}), 400

    execute(sql("""
        UPDATE orders
        SET status=?
        WHERE id=? AND restaurant_id=?
    """), (status, order_id, session["restaurant_id"]))

    commit()
    return jsonify({"success": True})


# --------------------------------------------------
# QR GENERATION
# --------------------------------------------------

@app.route("/admin/qr")
@login_required(["admin", "superadmin"])
def admin_qr():
    return render_template("qr_auto.html")


@app.route("/generate_qr/<int:table_no>")
@login_required("admin")
def generate_single_qr(table_no):
    r = fetchone(
        sql("SELECT subdomain FROM restaurants WHERE id=?"),
        (session["restaurant_id"],)
    )

    qr_dir = f"{QR_FOLDER}/{r['subdomain']}"
    os.makedirs(qr_dir, exist_ok=True)

    qr_path = f"{qr_dir}/table_{table_no}.png"
    url = f"{BASE_URL}/customer/{r['subdomain']}?table={table_no}"
    qrcode.make(url).save(qr_path)

    return jsonify({"success": True, "qr": f"/{qr_path}"})


@app.route("/admin/qr/auto", methods=["POST"])
@login_required("admin")
def auto_generate_qr():
    count = int(request.form["table_count"])

    r = fetchone(
        sql("SELECT subdomain FROM restaurants WHERE id=?"),
        (session["restaurant_id"],)
    )

    qr_dir = f"{QR_FOLDER}/{r['subdomain']}"
    os.makedirs(qr_dir, exist_ok=True)

    zip_path = f"{qr_dir}/table_qrs.zip"

    with ZipFile(zip_path, "w") as zipf:
        for t in range(1, count + 1):
            url = f"{BASE_URL}/customer/{r['subdomain']}?table={t}"
            img = f"{qr_dir}/table_{t}.png"
            qrcode.make(url).save(img)
            zipf.write(img, os.path.basename(img))

    return jsonify({"success": True, "zip": f"/{zip_path}"})

# --------------------------------------------------
# BILLING
# --------------------------------------------------
@app.route("/admin/order/<int:order_id>/edit")
@login_required("admin")
def edit_order(order_id):
    order = fetchone(sql("""
        SELECT *
        FROM orders
        WHERE id=? AND restaurant_id=?
    """), (order_id, session["restaurant_id"]))

    if not order:
        return "Order not found", 404

    # ✅ SAFE PARSE ITEMS
    items = (
        order["items"]
        if isinstance(order["items"], list)
        else json.loads(order["items"] or "[]")
    )

    # ✅ CALCULATE TOTALS
    subtotal = sum(i["price"] * i["qty"] for i in items)
    gst = round(subtotal * 0.05, 2)
    total = round(subtotal + gst, 2)

    return render_template(
        "edit_bill.html",
        order=order,
        items=items,
        subtotal=subtotal,
        gst=gst,
        total=total
    )
@app.route("/api/order/<int:order_id>/generate-close", methods=["POST"])
@login_required("admin")
def generate_and_close(order_id):
    execute(sql("""
        UPDATE orders
        SET status='Closed'
        WHERE id=? AND restaurant_id=?
    """), (order_id, session["restaurant_id"]))

    commit()
    return jsonify({"success": True})


@app.route("/bill/<int:order_id>")
@login_required("admin")
def bill(order_id):

    order = fetchone(
        sql("""
            SELECT 
                o.*,
                r.name AS restaurant_name,
                r.gstin AS restaurant_gstin,
                r.address AS restaurant_address,
                r.phone AS restaurant_phone
            FROM orders o
            JOIN restaurants r ON o.restaurant_id = r.id
            WHERE o.id=? AND o.restaurant_id=?
        """),
        (order_id, session["restaurant_id"])
    )

    if not order:
        return "Order not found", 404

    raw_items = (
    order["items"]
    if isinstance(order["items"], list)
    else json.loads(order["items"])
)

    grouped = {}

    for i in raw_items:
        key = i["name"]
        if key not in grouped:
            grouped[key] = {
                "name": i["name"],
                "price": i["price"],
                "qty": 0
            }
        grouped[key]["qty"] += i["qty"]

    items = list(grouped.values())


    subtotal = sum(i["price"] * i["qty"] for i in items)
    gst = round(subtotal * 0.05, 2)
    total = round(subtotal + gst, 2)

    # PDF download
    if request.args.get("pdf"):
        filename = f"bill_{order_id}.pdf"
        c = canvas.Canvas(filename)

        c.drawString(100, 780, order["restaurant_name"])
        c.drawString(100, 760, f"Table: {order['table_no']}")

        if order["customer_name"]:
            c.drawString(100, 740, f"Customer: {order['customer_name']}")

        y = 720
        for i in items:
            c.drawString(
                100, y,
                f"{i['name']} x {i['qty']} = ₹{i['price'] * i['qty']}"
            )
            y -= 20

        c.drawString(100, y - 20, f"Total: ₹{total}")
        c.save()

        return send_file(filename, as_attachment=True)

    return render_template(
        "bill.html",
        order=order,
        items=items,
        subtotal=subtotal,
        gst=gst,
        total=total,
        restaurant_name=order["restaurant_name"],
        gstin=order["restaurant_gstin"],
        address=order["restaurant_address"],
        phone=order["restaurant_phone"]
    )
@app.route("/api/order/<int:order_id>/remove-item", methods=["POST"])
@login_required("admin")
def remove_item_from_order(order_id):
    data = request.json
    item_name = data.get("item_name")

    order = fetchone(sql("""
        SELECT items
        FROM orders
        WHERE id=? AND restaurant_id=?
    """), (order_id, session["restaurant_id"]))

    if not order:
        return jsonify({"error": "Order not found"}), 404

    items = order["items"]
    if isinstance(items, str):
        items = json.loads(items or "[]")

    # 🔥 REMOVE ONLY ONE ITEM
    removed = False
    new_items = []

    for i in items:
        if i["name"] == item_name and not removed:
            removed = True
            continue
        new_items.append(i)

    if not removed:
        return jsonify({"error": "Item not found"}), 400

    # 🔥 RECALCULATE TOTAL
    new_total = sum(i["price"] * i["qty"] for i in new_items)

    execute(sql("""
        UPDATE orders
        SET items=?, total=?
        WHERE id=? AND restaurant_id=?
    """), (
        json.dumps(new_items),
        new_total,
        order_id,
        session["restaurant_id"]
    ))

    commit()
    return jsonify({"success": True})

@app.route("/bill/<int:order_id>/thermal")
@login_required("admin")
def thermal_bill(order_id):

    order = fetchone(
        sql("""
            SELECT o.*, r.name, r.gstin, r.address, r.phone
            FROM orders o
            JOIN restaurants r ON o.restaurant_id = r.id
            WHERE o.id=? AND o.restaurant_id=?
        """),
        (order_id, session["restaurant_id"])
    )

    if not order:
        return "Order not found", 404

    items = json.loads(order["items"])

    subtotal = sum(i["price"] * i["qty"] for i in items)
    cgst = round(subtotal * 0.025, 2)
    sgst = round(subtotal * 0.025, 2)
    total = round(subtotal + cgst + sgst, 2)

    return render_template(
        "bill_thermal.html",
        order=order,
        items=items,
        subtotal=subtotal,
        cgst=cgst,
        sgst=sgst,
        total=total
    )



# --------------------------------------------------
# SSE (ORDERS + REVENUE)
# --------------------------------------------------

# @app.route("/events")
# @login_required(["admin", "kitchen"])
# def events():
#     rid = session["restaurant_id"]

#     def stream():
#         with app.app_context():
#             while True:
#                 orders = fetchall(
#                     sql(f"""
#                         SELECT *
#                         FROM orders
#                         WHERE restaurant_id=?
#                         AND {today_clause("created_at")}
#                         ORDER BY id DESC
#                     """),
#                     (rid,)
#                 )

#                 revenue_row = fetchone(
#                     sql(f"""
#                         SELECT COALESCE(SUM(total), 0) AS revenue
#                         FROM orders
#                         WHERE restaurant_id=?
#                         AND status='Served'
#                         AND {today_clause("created_at")}
#                     """),
#                     (rid,)
#                 )

#                 payload = {
#                     "orders": [
#                         {k: json_safe(v) for k, v in dict(o).items()}
#                         for o in orders
#                         ],
#                         "today_revenue": float(revenue_row["revenue"] or 0)
#                 }


#                 yield f"data:{json.dumps(payload)}\n\n"
#                 time.sleep(2)

#     return Response(stream(), mimetype="text/event-stream")

# @app.route("/events/additions")
# @login_required("kitchen")
# def addition_events():
#     rid = session["restaurant_id"]

#     def stream():
#         with app.app_context():
#             while True:
#                 additions = fetchall(
#                     sql("""
#                         SELECT *
#                         FROM order_additions
#                         WHERE restaurant_id=?
#                         AND status='New'
#                         ORDER BY created_at ASC
#                     """),
#                     (rid,)
#                 )

#                 yield f"data:{json.dumps([
#                     {k: json_safe(v) for k, v in dict(a).items()}
#                     for a in additions
#                 ])}\n\n"

#                 time.sleep(2)

#     return Response(stream(), mimetype="text/event-stream")
@app.route("/api/orders")
@login_required("admin")
def api_orders():
    rid = session["restaurant_id"]

    orders = fetchall(sql("""
        SELECT *
        FROM orders
        WHERE restaurant_id=?
        ORDER BY id DESC
        LIMIT 50
    """), (rid,))

    return jsonify([
        {k: json_safe(v) for k, v in dict(o).items()}
        for o in orders
    ])
@app.route("/api/kitchen/orders")
@login_required("kitchen")
def kitchen_orders():
    rid = session["restaurant_id"]

    orders = fetchall(sql("""
        SELECT *
        FROM orders
        WHERE restaurant_id=?
        AND status != 'Served'
        ORDER BY created_at ASC
    """), (rid,))

    return jsonify([
        {k: json_safe(v) for k, v in dict(o).items()}
        for o in orders
    ])


# --------------------------------------------------
# ROOT
# --------------------------------------------------

@app.route("/")
def home():
    return redirect("/login")

# --------------------------------------------------

if __name__ == "__main__":
    app.run()

# if __name__ == "__main__":
#     app.run(debug=True)
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000)


