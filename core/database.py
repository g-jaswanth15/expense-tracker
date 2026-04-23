import sqlite3
import threading

# ── Module-level state ────────────────────────────────────────────────────────
_db_path: str = ""

# When set, ALL get_connection() calls return this single connection.
# Used exclusively in tests (in-memory SQLite needs one shared connection).
_forced_connection: sqlite3.Connection | None = None
_lock = threading.Lock()


def force_connection(conn: sqlite3.Connection | None):
    """
    Override the connection used by get_connection().
    Pass a real connection to force all DB calls through it (tests only).
    Pass None to restore normal behaviour.
    """
    global _forced_connection
    _forced_connection = conn


def configure(path: str):
    """Set the DB file path."""
    global _db_path
    _db_path = path


def get_connection() -> sqlite3.Connection:
    """
    Return a sqlite3 connection with Row factory enabled.
    In test mode a single shared connection is returned so that
    in-memory SQLite data is visible across all calls.
    """
    if _forced_connection is not None:
        return _forced_connection          # shared test connection

    if not _db_path:
        raise RuntimeError(
            "Database path not configured. Call init_db() first."
        )
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(path: str):
    """
    Configure the DB path and create schema + indexes.
    Safe to call multiple times (idempotent).
    """
    configure(path)
    _create_schema(get_connection())


def init_db_with_connection(conn: sqlite3.Connection):
    """
    Initialise schema on an already-open connection.
    Used by the test fixture so the same in-memory connection is reused.
    """
    conn.row_factory = sqlite3.Row
    _create_schema(conn)


def _create_schema(conn: sqlite3.Connection):
    """Create tables and indexes — idempotent."""
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