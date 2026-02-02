import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import g

DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DATABASE_URL = os.getenv("DATABASE_URL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE_DIR, "restaurant.db")

# ---------------- DB CONNECTION ----------------
def get_db():
    if "db" not in g:
        if DB_TYPE == "postgres":
            g.db = psycopg2.connect(
                DATABASE_URL,
                cursor_factory=RealDictCursor
            )
            g.db.autocommit = True   # 🔥 REQUIRED
        else:
            g.db = sqlite3.connect(
                SQLITE_PATH,
                timeout=10,
                check_same_thread=False
            )
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA journal_mode=WAL;")
            g.db.execute("PRAGMA synchronous=NORMAL;")

    return g.db


# ---------------- CLOSE CONNECTION ----------------
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


# ---------------- INIT DB (SQLITE ONLY) ----------------
def init_db():
    if DB_TYPE != "sqlite":
        return

    db = sqlite3.connect(SQLITE_PATH)
    c = db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subdomain TEXT UNIQUE NOT NULL,
        gstin TEXT,
        address TEXT,
        phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        category TEXT,
        image TEXT,
        available INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        table_no INTEGER,
        customer_name TEXT,
        items TEXT,
        total REAL,
        status TEXT DEFAULT 'Received',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS order_additions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        restaurant_id INTEGER NOT NULL,
        table_no INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        status TEXT DEFAULT 'New',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
    )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_restaurant ON orders(restaurant_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_additions_restaurant ON order_additions(restaurant_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_additions_status ON order_additions(status)")

    db.commit()
    db.close()
def commit(db):
    if DB_TYPE != "postgres":
        db.commit()

def today_clause(column):
    if DB_TYPE == "postgres":
        return f"{column}::date = CURRENT_DATE"
    return f"DATE({column}) = DATE('now')"

def sql(query):
    """
    Converts SQLite placeholders (?) to Postgres (%s) when needed
    """
    if DB_TYPE == "postgres":
        return query.replace("?", "%s")
    return query
