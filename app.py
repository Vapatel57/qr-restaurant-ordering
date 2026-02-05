from flask import (
    Flask, render_template, request, redirect,
    session, Response, send_file, jsonify,
    current_app
)
import uuid
from flask import url_for
from flask_dance.contrib.google import google
from db import (
    execute, fetchone, fetchall, commit, sql,
    init_db, close_db, today_clause, get_db
)
from email_utils import send_otp_email
from otp_utils import generate_otp   # or wherever you put it
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

app.secret_key = os.getenv("SECRET_KEY", "dev-secret")


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
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ]
)

app.register_blueprint(google_bp, url_prefix="/login")
google_bp.redirect_url = "/google/after-login"

# --------------------------------------------------
# AUTH
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["username"].strip().lower()
        password = request.form["password"]

        user = fetchone(
            sql("SELECT * FROM users WHERE username=?"),
            (email,)
        )

        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid email or password")

        # 🔐 IF NOT VERIFIED → SEND OTP
        if not user["is_verified"]:
            otp = generate_otp()

            execute(sql("""
                UPDATE users
                SET otp_code=?, otp_expires_at=NOW() + INTERVAL '10 minutes'
                WHERE username=?
            """), (otp, email))

            commit()
            send_otp_email(email, otp)

            session.clear()
            session["pending_email"] = email
            return redirect("/verify-email")

        # ===============================
        # ✅ LOGIN SUCCESS
        # ===============================
        session.clear()
        session["user"] = user["username"]

        SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL")

        # 🔥 SUPER ADMIN OVERRIDE (OPTION 2)
        if SUPERADMIN_EMAIL and user["username"] == SUPERADMIN_EMAIL:
            session["role"] = "superadmin"
            session["restaurant_id"] = None
            return redirect("/platform/restaurants")

        # 👤 NORMAL USERS
        session["role"] = user["role"]
        session["restaurant_id"] = user["restaurant_id"]

        if user["role"] == "admin":
            return redirect("/admin")
        elif user["role"] == "kitchen":
            return redirect("/kitchen")
        else:
            return redirect("/login")
    print("LOGIN DEBUG →",
      user["username"],
      user["role"],
      "verified:", user["is_verified"])

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

        if fetchone(sql("SELECT id FROM users WHERE username=?"), (email,)):
            return render_template("signup.html", error="Email already registered.")

        if fetchone(sql("SELECT id FROM restaurants WHERE subdomain=?"), (subdomain,)):
            return render_template("signup.html", error="Subdomain already taken.")

        try:
            otp = generate_otp()

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

            restaurant_id = cursor.fetchone()["id"]

            execute(sql("""
                INSERT INTO users (
                    restaurant_id,
                    username,
                    password,
                    role,
                    is_verified,
                    otp_code,
                    otp_expires_at
                )
                VALUES (?, ?, ?, 'admin', FALSE, ?, NOW() + INTERVAL '10 minutes')
            """), (
                restaurant_id,
                email,
                generate_password_hash(request.form["password"]),
                otp
            ))

            commit()

        except Exception as e:
            current_app.logger.exception(e)
            get_db().rollback()
            return render_template("signup.html", error="Signup failed.")

        # 🔥 Send OTP safely
        send_otp_email(email, otp)

        session.clear()
        session["pending_email"] = email
        return redirect("/verify-email")

    return render_template("signup.html")

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    user_id = session.get("pending_google_user")
    email = session.get("pending_email")

    if not user_id or not email:
        return redirect("/login")

    if request.method == "POST":
        subdomain = request.form["subdomain"].strip().lower()

        if fetchone(
            sql("SELECT id FROM restaurants WHERE subdomain=?"),
            (subdomain,)
        ):
            return render_template(
                "onboarding.html",
                email=email,
                error="Subdomain already taken"
            )

        cursor = execute(sql("""
            INSERT INTO restaurants (name, subdomain, phone, address)
            VALUES (?, ?, ?, ?)
            RETURNING id
        """), (
            request.form["restaurant_name"],
            subdomain,
            request.form.get("phone"),
            request.form.get("address")
        ))

        restaurant_id = cursor.fetchone()["id"]

        execute(sql("""
            UPDATE users
            SET restaurant_id=?
            WHERE id=?
        """), (restaurant_id, user_id))

        commit()

        session.clear()
        session["user"] = email
        session["role"] = "admin"
        session["restaurant_id"] = restaurant_id

        return redirect("/admin")

    return render_template("onboarding.html", email=email)

@app.route("/google/after-login")
def google_after_login():
    SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL")
    if email == SUPERADMIN_EMAIL:
        return redirect("/login")
    if not google.authorized:
        return redirect("/login")

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect("/login")

    info = resp.json()
    email = info["email"].lower()
    name = info.get("name", "")
    google_id = info.get("id")

    user = fetchone(
        sql("SELECT * FROM users WHERE username=?"),
        (email,)
    )

    # ✅ EXISTING USER
    if user:
        session.clear()
        session["user"] = user["username"]
        session["role"] = user["role"]

        # 🚨 IMPORTANT: restaurant missing → onboarding
        if not user["restaurant_id"]:
            session["pending_google_user"] = user["id"]
            session["pending_email"] = email
            session["pending_name"] = name
            return redirect("/onboarding")

        session["restaurant_id"] = user["restaurant_id"]
        return redirect("/admin")

    # 🆕 BRAND NEW GOOGLE USER
    cursor = execute(sql("""
        INSERT INTO users
        (username, password, role, is_verified, auth_provider)
        VALUES (?, ?, 'admin', TRUE, 'google')
        RETURNING id
    """), (
        email,
        generate_password_hash(google_id)
    ))

    user_id = cursor.fetchone()["id"]
    commit()

    session.clear()
    session["pending_google_user"] = user_id
    session["pending_email"] = email
    session["pending_name"] = name

    return redirect("/onboarding")


@app.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    email = session.get("pending_email")

    if not email:
        return redirect("/login")

    if request.method == "POST":
        code = request.form["otp"]

        user = fetchone(sql("""
            SELECT * FROM users
            WHERE username=?
            AND otp_code=?
            AND otp_expires_at > NOW()
        """), (email, code))

        if not user:
            return render_template("verify_email.html", error="Invalid or expired OTP")

        execute(sql("""
            UPDATE users
            SET is_verified=TRUE,
                otp_code=NULL,
                otp_expires_at=NULL
            WHERE username=?
        """), (email,))

        commit()

        session.clear()
        session["user"] = user["username"]
        session["role"] = user["role"]
        session["restaurant_id"] = user["restaurant_id"]

        return redirect(
            "/admin" if user["role"] == "admin" else "/kitchen"
        )

    return render_template("verify_email.html")

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
@app.route("/platform/restaurants/<int:restaurant_id>")
@login_required("superadmin")
def platform_restaurant_details(restaurant_id):

    restaurant = fetchone(sql("""
        SELECT r.*, u.username AS admin_email
        FROM restaurants r
        JOIN users u ON u.restaurant_id = r.id AND u.role='admin'
        WHERE r.id=?
    """), (restaurant_id,))

    if not restaurant:
        return "Restaurant not found", 404

    stats = fetchone(sql("""
        SELECT
            COUNT(id) AS total_orders,
            COALESCE(SUM(total), 0) AS revenue
        FROM orders
        WHERE restaurant_id=?
    """), (restaurant_id,))

    menu_count = fetchone(sql("""
        SELECT COUNT(*) AS count
        FROM menu
        WHERE restaurant_id=?
    """), (restaurant_id,))

    kitchen_users = fetchall(sql("""
        SELECT username
        FROM users
        WHERE restaurant_id=? AND role='kitchen'
    """), (restaurant_id,))

    return render_template(
        "platform_restaurant_details.html",
        restaurant=restaurant,
        stats=stats,
        menu_count=menu_count["count"],
        kitchen_users=[u["username"] for u in kitchen_users]
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

    # ===============================
    # ✅ CASE 1: APPEND TO EXISTING ORDER
    # ===============================
    if existing:
        old_items = (
            existing["items"]
            if isinstance(existing["items"], list)
            else json.loads(existing["items"] or "[]")
        )

        combined_items = old_items + new_items
        updated_total = float(existing["total"]) + new_total

        # ✅ Update order
        execute(sql("""
            UPDATE orders
            SET items=?, total=?
            WHERE id=?
        """), (
            json.dumps(combined_items),
            updated_total,
            existing["id"]
        ))

        # 🔥 Send ONLY new items to kitchen
        for i in new_items:
            execute(sql("""
                INSERT INTO order_additions
                (order_id, restaurant_id, table_no, item_name, qty, price, status, created_at)
                VALUES (?,?,?,?,?,?,'New',CURRENT_TIMESTAMP)
            """), (
                existing["id"],
                restaurant_id,
                table_no,
                i["name"],
                i["qty"],
                i["price"]
            ))

        commit()
        return jsonify({"success": True, "order_id": existing["id"]})

    # ===============================
    # ✅ CASE 2: CREATE NEW ORDER
    # ===============================
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


@app.route("/api/order/<int:order_id>/close", methods=["POST"])
@login_required("admin")
def close_order(order_id):
    execute(sql("""
        UPDATE orders
        SET status='Closed'
        WHERE id=? AND restaurant_id=?
    """), (order_id, session["restaurant_id"]))

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
        AND status='Closed'
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
    email = data.get("email", "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email & password required"}), 400

    if fetchone(sql("SELECT id FROM users WHERE username=?"), (email,)):
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

    otp = generate_otp()

    execute(sql("""
        UPDATE users
        SET otp_code=?, otp_expires_at=NOW() + INTERVAL '10 minutes'
        WHERE username=?
    """), (otp, email))

    commit()
    send_otp_email(email, otp)

    return jsonify({"success": True, "message": "OTP sent to kitchen user"})


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
    rid = session["restaurant_id"]
    search = request.args.get("search", "").strip().lower()
    category = request.args.get("category", "")

    query = """
        SELECT *
        FROM menu
        WHERE restaurant_id=?
    """
    params = [rid]

    if search:
        query += " AND LOWER(name) LIKE ?"
        params.append(f"%{search}%")

    if category:
        query += " AND category=?"
        params.append(category)

    query += " ORDER BY id DESC"

    rows = fetchall(sql(query), tuple(params))
    return jsonify([dict(r) for r in rows])



@app.route("/api/menu", methods=["POST"])
@login_required("admin")
def api_add_menu():
    name = request.form.get("name", "").strip()
    price = request.form.get("price")
    category = request.form.get("category")
    image = request.files.get("image")

    # 🔒 BASIC VALIDATION
    if not name or not price or not category:
        return jsonify({"error": "Name, price and category are required"}), 400

    if not image:
        return jsonify({"error": "Image required"}), 400

    # 🔥 DUPLICATE CHECK (CASE-INSENSITIVE)
    exists = fetchone(sql("""
        SELECT id FROM menu
        WHERE restaurant_id = ?
        AND LOWER(name) = LOWER(?)
    """), (
        session["restaurant_id"],
        name
    ))

    if exists:
        return jsonify({
            "error": "Item with this name already exists"
        }), 400

    try:
        # ☁️ Upload image to Cloudinary
        result = cloudinary.uploader.upload(
            image,
            folder="menu_images"
        )
        image_url = result["secure_url"]

        # 💾 Insert menu item
        execute(sql("""
            INSERT INTO menu
            (restaurant_id, name, price, category, image, available)
            VALUES (?, ?, ?, ?, ?, TRUE)
        """), (
            session["restaurant_id"],
            name,
            float(price),
            category,
            image_url
        ))

        commit()
        return jsonify({"success": True})

    except Exception as e:
        current_app.logger.exception(e)
        get_db().rollback()

        return jsonify({
            "error": "Failed to add menu item"
        }), 500

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

    inserted = 0
    skipped = 0

    for name, category in MENU_TEMPLATES[template]:
        exists = fetchone(sql("""
            SELECT id FROM menu
            WHERE restaurant_id = ?
            AND LOWER(name) = LOWER(?)
        """), (
            restaurant_id,
            name
        ))

        if exists:
            skipped += 1
            continue  # 🔥 skip duplicates

        execute(sql("""
            INSERT INTO menu
            (restaurant_id, name, price, category, image, available)
            VALUES (?, ?, 0, ?, '', TRUE)
        """), (
            restaurant_id,
            name,
            category
        ))

        inserted += 1

    commit()

    return jsonify({
        "success": True,
        "added": inserted,
        "skipped": skipped
    })


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

    # ✅ AUTO CLOSE ORDER WHEN BILL IS GENERATED
    if order["status"] != "Closed":
        execute(sql("""
            UPDATE orders
            SET status='Closed'
            WHERE id=? AND restaurant_id=?
        """), (order_id, session["restaurant_id"]))
        commit()

        # refresh order after update
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

    # ✅ SAFE PARSE ITEMS
    raw_items = (
        order["items"]
        if isinstance(order["items"], list)
        else json.loads(order["items"] or "[]")
    )

    # ✅ GROUP SAME ITEMS
    grouped = {}
    for i in raw_items:
        key = i["name"]
        if key not in grouped:
            grouped[key] = {
                "name": i["name"],
                "price": float(i["price"]),
                "qty": 0
            }
        grouped[key]["qty"] += int(i["qty"])

    items = list(grouped.values())

    # ✅ TOTALS
    subtotal = sum(i["price"] * i["qty"] for i in items)
    gst = round(subtotal * 0.05, 2)
    total = round(subtotal + gst, 2)

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
        AND status NOT IN ('Served', 'Closed')
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

# if __name__ == "__main__":
#     app.run()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

