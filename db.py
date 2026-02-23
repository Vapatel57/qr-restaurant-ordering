import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import g

DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DATABASE_URL = os.getenv("DATABASE_URL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE_DIR, "restaurant.db")


# --------------------------------------------------
# DB CONNECTION
# --------------------------------------------------

def get_db():
    if "db" not in g:
        if DB_TYPE == "postgres":
            g.db = psycopg2.connect(
                DATABASE_URL,
                cursor_factory=RealDictCursor
            )
            g.db.autocommit = True
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


def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


# --------------------------------------------------
# SQLITE INIT (LOCAL DEV ONLY)
# --------------------------------------------------

def init_db():
    if DB_TYPE != "sqlite":
        return

    db = sqlite3.connect(SQLITE_PATH)
    c = db.cursor()

    # ---------------- RESTAURANTS ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subdomain TEXT UNIQUE NOT NULL,
        gstin TEXT,
        address TEXT,
        phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        trial_start DATETIME,
        trial_expires_at DATETIME
    )
    """)

    # ---------------- USERS ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        is_verified INTEGER DEFAULT 0,
        auth_provider TEXT DEFAULT 'local',
        otp_code TEXT,
        otp_expires_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
    )
    """)

    # ---------------- MENU ----------------
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

    # ---------------- ORDERS ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        table_no INTEGER,
        customer_name TEXT,
        customer_phone TEXT,
        items TEXT,
        subtotal REAL,
        cgst REAL,
        sgst REAL,
        total REAL,
        status TEXT DEFAULT 'Received',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
    )
    """)

    # ---------------- ORDER ADDITIONS ----------------
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

    # ---------------- INDEXES ----------------
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_restaurant ON orders(restaurant_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_additions_restaurant ON order_additions(restaurant_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_additions_status ON order_additions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_restaurant ON users(restaurant_id)")

    db.commit()
    db.close()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def today_clause(column):
    if DB_TYPE == "postgres":
        return f"{column}::date = CURRENT_DATE"
    return f"DATE({column}) = DATE('now')"


def sql(query):
    """
    Convert SQLite placeholders (?) to Postgres (%s)
    """
    if DB_TYPE == "postgres":
        return query.replace("?", "%s")
    return query


def execute(query, params=()):
    db = get_db()

    if DB_TYPE == "postgres":
        cur = db.cursor()
        cur.execute(query, params)
        return cur

    return db.execute(query, params)


def fetchone(query, params=()):
    cur = execute(query, params)
    return cur.fetchone()


def fetchall(query, params=()):
    cur = execute(query, params)
    return cur.fetchall()


def commit(db=None):
    if DB_TYPE == "sqlite":
        (db or get_db()).commit()