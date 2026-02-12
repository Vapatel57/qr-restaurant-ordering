@app.route("/api/daily-report", methods=["GET"])
def daily_report():
    today = datetime.date.today()

    orders = fetchall("""
        SELECT table_number, dish_name, total, wait_time
        FROM orders
        WHERE DATE(created_at)=?
        AND status='Closed'
    """, (today,))

    total_revenue = sum(o["total"] for o in orders)
    total_orders = len(orders)

    dish_count = {}
    for o in orders:
        dish_count[o["dish_name"]] = dish_count.get(o["dish_name"], 0) + 1

    top_dish = max(dish_count, key=dish_count.get) if dish_count else None

    return jsonify({
        "revenue": total_revenue,
        "orders": total_orders,
        "top_dish": top_dish
    })
