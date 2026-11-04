"""
SmartPark India — Database connection layer.

Uses SQLite for the college/dev build (zero setup). The schema.sql is plain
ANSI-ish SQL and maps cleanly onto PostgreSQL for the production build —
swap get_db() for a psycopg2/SQLAlchemy engine and the rest of the app
(routers/services) does not need to change, since all queries go through
this module's helpers.
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "smartpark.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False):
    """Create tables from schema.sql. If reset=True, drop the existing DB file first."""
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[db] initialized at {DB_PATH}")


def query(sql, params=(), fetch="all"):
    conn = get_db()
    cur = conn.execute(sql, params)
    if sql.strip().upper().startswith("SELECT"):
        rows = cur.fetchall() if fetch == "all" else cur.fetchone()
        conn.close()
        return [dict(r) for r in rows] if fetch == "all" and rows is not None else (dict(rows) if rows else None)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


if __name__ == "__main__":
    init_db(reset=True)
