"""Database adapter — transparently switches between SQLite (local) and PostgreSQL (Supabase/HF Spaces).

Usage:
    from src.core.db import get_db
    with get_db().connect() as conn:
        rows = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchall()
        # rows are always dict-like (sqlite3.Row or RealDictRow)

The adapter normalises SQLite-flavoured SQL for PostgreSQL automatically:
  - Parameter markers:  ?  →  %s
  - INSERT OR IGNORE  →  INSERT … ON CONFLICT DO NOTHING
  - ALTER TABLE … ADD COLUMN  →  ALTER TABLE … ADD COLUMN IF NOT EXISTS
  - PRAGMA statements are silently skipped
"""

import re
import sqlite3
from typing import Any, Optional

_adapter: Optional["DBAdapter"] = None


def get_db() -> "DBAdapter":
    """Return the singleton DB adapter (initialised lazily)."""
    global _adapter
    if _adapter is None:
        _adapter = DBAdapter()
    return _adapter


# ── SQL normalisation helpers ──────────────────────────────────────────────────

_RE_PLACEHOLDER = re.compile(r"\?")
_RE_INSERT_OR_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.IGNORECASE)
_RE_ALTER_ADD = re.compile(
    r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS\s+)(\w+\s+.+)",
    re.IGNORECASE,
)


def _to_pg(sql: str) -> str:
    """Convert SQLite-flavoured SQL to PostgreSQL-compatible SQL."""
    sql = _RE_PLACEHOLDER.sub("%s", sql)
    sql = _RE_INSERT_OR_IGNORE.sub("INSERT INTO", sql)
    # Ensure ON CONFLICT DO NOTHING is appended to converted INSERT stmts
    # (handled in _PgCursor.execute via flag)
    sql = _RE_ALTER_ADD.sub(r"ALTER TABLE \1 ADD COLUMN IF NOT EXISTS \2", sql)
    return sql


# ── PostgreSQL wrapper ─────────────────────────────────────────────────────────

class _PgCursor:
    """Wraps a psycopg2 RealDictCursor, normalising SQLite-flavoured SQL."""

    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, sql: str, params: tuple = ()):
        sql = _to_pg(sql)
        if sql.strip().upper().startswith("PRAGMA"):
            return self
        # Append ON CONFLICT DO NOTHING if this was an INSERT OR IGNORE
        if re.search(r"INSERT INTO", sql, re.IGNORECASE) and not re.search(
            r"ON CONFLICT", sql, re.IGNORECASE
        ):
            # Only add for statements that came from INSERT OR IGNORE
            # We detect this by checking if VALUES is present (not INSERT INTO … SELECT)
            if re.search(r"\bVALUES\b", sql, re.IGNORECASE):
                sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        self._cur.execute(sql, params or None)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [dict(r) for r in rows]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount


class _PgConnection:
    """Wraps a psycopg2 connection to provide a sqlite3-like interface."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self) -> _PgCursor:
        import psycopg2.extras
        return _PgCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def execute(self, sql: str, params: tuple = ()):
        """Convenience: execute without explicit cursor (mirrors sqlite3 Connection.execute)."""
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ── SQLite wrapper (adds context-manager support) ──────────────────────────────

class _SqliteConnection:
    """Thin wrapper around sqlite3.Connection adding __enter__/__exit__."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        # Expose underlying attributes needed by UserService
        self.row_factory = conn.row_factory

    def cursor(self):
        return self._conn.cursor()

    def execute(self, sql: str, params: tuple = ()):
        if sql.strip().upper().startswith("PRAGMA"):
            return self._conn.execute(sql, params)
        return self._conn.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ── Main adapter ───────────────────────────────────────────────────────────────

class DBAdapter:
    """
    Connects to PostgreSQL when DATABASE_URL is set, otherwise falls back to
    SQLite stored at <data_dir>/users.db.
    """

    def __init__(self):
        from config.settings import get_settings
        s = get_settings()
        self.database_url: Optional[str] = s.database_url
        self.db_path = None
        if not self.database_url:
            from pathlib import Path
            self.db_path = Path(s.data_dir) / "users.db"

    @property
    def is_postgres(self) -> bool:
        return bool(self.database_url) and self.database_url.startswith(("postgres://", "postgresql://"))

    def connect(self):
        """Return an open connection (SQLite or PostgreSQL)."""
        if self.is_postgres:
            import psycopg2
            conn = psycopg2.connect(self.database_url)
            return _PgConnection(conn)
        else:
            conn = sqlite3.connect(str(self.db_path), timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=15000")
            return _SqliteConnection(conn)
