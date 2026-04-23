import sqlite3
import os


_db_path: str = ""


def configure(path: str):
    """Set the DB path (called by init_db or overridden in tests)."""
    global _db_path
    _db_path = path


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe sqlite3 connection with Row factory."""
    if not _db_path:
        raise RuntimeError("Database path not configured. Call init_db() first.")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(path: str):
    """
    Configure the DB path and create schema if it doesn't exist.
    Safe to call multiple times (idempotent).
    """
    configure(path)

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id              INTEGER  PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT     UNIQUE,
                amount          INTEGER  NOT NULL,
                category        TEXT     NOT NULL,
                description     TEXT     NOT NULL DEFAULT '',
                date            TEXT     NOT NULL,
                created_at      TEXT     NOT NULL
                                DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expenses_category
            ON expenses(category)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expenses_date
            ON expenses(date)
        """)
        conn.commit()