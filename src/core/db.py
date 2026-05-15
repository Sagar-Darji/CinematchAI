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
from typing import Any, Dict, List, Optional


class _DualAccessRow(dict):
    """Dict subclass that also supports integer index access like sqlite3.Row.
    Allows code like row[0] or row['column_name'] to work interchangeably."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

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
_RE_INSERT_OR_REPLACE = re.compile(r"INSERT\s+OR\s+REPLACE\s+INTO", re.IGNORECASE)
_RE_ALTER_ADD = re.compile(
    r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS\s+)(\w+\s+.+)",
    re.IGNORECASE,
)
# Matches: INSERT INTO table (col1, col2, ...) VALUES ...
_RE_INSERT_COLS = re.compile(
    r"INSERT\s+INTO\s+\w+\s*\(([^)]+)\)\s*VALUES",
    re.IGNORECASE,
)
# Matches: INSERT INTO <table> — captures table name only.
_RE_INSERT_TABLE = re.compile(r"INSERT\s+INTO\s+(\w+)", re.IGNORECASE)


# ── Per-table PK registry ──────────────────────────────────────────────────────
#
# Postgres needs an explicit conflict target on ON CONFLICT DO UPDATE — but
# our SQLite-flavored `INSERT OR REPLACE` doesn't carry that information.
# Services teach the adapter their primary keys at schema-init time via
# `register_pk`. `_build_upsert_suffix` then generates the right
# `ON CONFLICT (col1, col2, ...) DO UPDATE SET col_a=EXCLUDED.col_a, ...`
# regardless of how many columns the PK has.
#
# The old behaviour hardcoded `(user_id, movie_id)` for the ratings table and
# silently emitted `ON CONFLICT (<first column>)` for everything else, which
# raised psycopg2.errors.InvalidColumnReference on any multi-column PK
# (watch_history, watchlist, reviews — all (user_id, tmdb_id, media_type)).

_PK_REGISTRY: Dict[str, List[str]] = {}


def register_pk(table: str, cols: List[str]) -> None:
    """Tell the DB adapter which columns make up a table's primary key.
    Call from each service's `_ensure_schema` right after CREATE TABLE."""
    _PK_REGISTRY[table.lower()] = list(cols)


def _to_pg(sql: str) -> str:
    """Convert SQLite-flavoured SQL to PostgreSQL-compatible SQL."""
    sql = _RE_PLACEHOLDER.sub("%s", sql)
    sql = _RE_INSERT_OR_IGNORE.sub("INSERT INTO", sql)
    sql = _RE_INSERT_OR_REPLACE.sub("INSERT INTO", sql)
    sql = _RE_ALTER_ADD.sub(r"ALTER TABLE \1 ADD COLUMN IF NOT EXISTS \2", sql)
    return sql


def _is_replace(sql: str) -> bool:
    """Return True if original SQL was INSERT OR REPLACE (upsert, not ignore)."""
    return bool(_RE_INSERT_OR_REPLACE.search(sql))


def _build_upsert_suffix(sql: str, original_sql: str = "") -> str:
    """For INSERT OR REPLACE, build ON CONFLICT DO UPDATE SET clause.

    Looks up the target table's primary key from the registry. Falls back
    to a safe `ON CONFLICT DO NOTHING` if the table never registered its
    PK — better than guessing and emitting an invalid conflict target.
    """
    m_cols = _RE_INSERT_COLS.search(sql)
    if not m_cols:
        return " ON CONFLICT DO NOTHING"
    cols = [c.strip() for c in m_cols.group(1).split(",")]
    if not cols:
        return " ON CONFLICT DO NOTHING"

    m_table = _RE_INSERT_TABLE.search(sql)
    table = m_table.group(1).lower() if m_table else None
    pk_cols = _PK_REGISTRY.get(table, []) if table else []

    if not pk_cols:
        # Legacy heuristic for ratings — services that haven't called
        # register_pk yet still need to work. (user_id, movie_id) is the
        # only multi-col PK we used to special-case.
        if len(cols) >= 2 and cols[0] == "user_id" and cols[1] == "movie_id":
            pk_cols = ["user_id", "movie_id"]
        elif len(cols) >= 1 and cols[0] in ("user_id", "key"):
            # Single-col PK is the common case for the rest.
            pk_cols = [cols[0]]
        else:
            # Don't guess — emit DO NOTHING. That's safer than emitting
            # `ON CONFLICT (col) DO UPDATE` with a column that may not
            # actually be unique, which is the bug we just fixed.
            return " ON CONFLICT DO NOTHING"

    conflict_target = "(" + ", ".join(pk_cols) + ")"
    update_cols = [c for c in cols if c not in pk_cols]
    if not update_cols:
        return f" ON CONFLICT {conflict_target} DO NOTHING"
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
    return f" ON CONFLICT {conflict_target} DO UPDATE SET {updates}"


# ── PostgreSQL wrapper ─────────────────────────────────────────────────────────

class _PgCursor:
    """Wraps a psycopg2 RealDictCursor, normalising SQLite-flavoured SQL."""

    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, sql: str, params: tuple = ()):
        is_replace = _is_replace(sql)
        sql = _to_pg(sql)
        if sql.strip().upper().startswith("PRAGMA"):
            return self
        # Append ON CONFLICT clause for INSERT statements
        if re.search(r"\bINSERT\s+INTO\b", sql, re.IGNORECASE) and not re.search(
            r"ON CONFLICT", sql, re.IGNORECASE
        ):
            if re.search(r"\bVALUES\b", sql, re.IGNORECASE):
                if is_replace:
                    sql = sql.rstrip().rstrip(";") + _build_upsert_suffix(sql)
                else:
                    sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        self._cur.execute(sql, params or None)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return _DualAccessRow(row) if row else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_DualAccessRow(r) for r in rows]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount


class _PgConnection:
    """Wraps a psycopg2 connection to provide a sqlite3-like interface.

    The wrapper supports two close semantics:
    - When `pooled=True`, close() commits/rolls back but does not actually
      close the underlying connection — the connection is parked back into
      the module-level cache for reuse on the next invocation in the same
      Lambda container.
    - When `pooled=False`, close() closes the underlying socket as before.
    """

    def __init__(self, conn, pooled: bool = False, on_release=None):
        self._conn = conn
        self._pooled = pooled
        self._on_release = on_release  # called with (conn, ok: bool)
        self._released = False

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
        if self._released:
            return
        self._released = True
        if self._pooled and self._on_release:
            self._on_release(self._conn, True)
        else:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ok = exc_type is None
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        except Exception:
            ok = False
        finally:
            if self._released:
                return
            self._released = True
            if self._pooled and self._on_release:
                self._on_release(self._conn, ok)
            else:
                self._conn.close()


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

    For PostgreSQL we keep a single per-process cached connection. Lambda
    containers serve one request at a time, so a single connection is enough,
    and reusing it across invocations within the same warm container avoids
    the ~50–200ms TLS+auth handshake every request.
    """

    # Class-level cache. One connection per Lambda container instance.
    _cached_pg_conn = None

    def __init__(self):
        from config.settings import get_settings
        s = get_settings()
        # Prefer AUTH_DATABASE_URL; fall back to DATABASE_URL only if it looks like postgres
        raw = s.auth_database_url or s.database_url or ""
        self.database_url: Optional[str] = raw if raw.startswith(("postgres://", "postgresql://")) else None
        self.db_path = None
        if not self.database_url:
            from pathlib import Path
            self.db_path = Path(s.data_dir) / "users.db"

    @property
    def is_postgres(self) -> bool:
        return bool(self.database_url) and self.database_url.startswith(("postgres://", "postgresql://"))

    @classmethod
    def _drop_cached(cls):
        conn = cls._cached_pg_conn
        cls._cached_pg_conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    @classmethod
    def _release(cls, conn, ok: bool):
        """Return a connection to the cache (or drop it if the txn errored)."""
        if not ok:
            try:
                conn.close()
            except Exception:
                pass
            if cls._cached_pg_conn is conn:
                cls._cached_pg_conn = None
            return
        # Sanity check the cache slot.
        if cls._cached_pg_conn is None:
            cls._cached_pg_conn = conn

    def connect(self):
        """Return an open connection (SQLite or PostgreSQL).

        For Postgres, reuses a cached connection within the same process when
        possible.
        """
        if self.is_postgres:
            import psycopg2
            cached = self.__class__._cached_pg_conn
            # `closed` is 0 when alive; non-zero when closed.
            if cached is not None and getattr(cached, "closed", 0) == 0:
                # Take it out of the cache while in use to avoid two callers
                # sharing a single connection.
                self.__class__._cached_pg_conn = None
                return _PgConnection(cached, pooled=True, on_release=self.__class__._release)
            conn = psycopg2.connect(self.database_url)
            return _PgConnection(conn, pooled=True, on_release=self.__class__._release)
        else:
            conn = sqlite3.connect(str(self.db_path), timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=15000")
            return _SqliteConnection(conn)
