"""Watchlist service — per-user 'save for later' list.

Schema is created lazily on first call. We use the existing inline-DDL
pattern from user_service.py rather than introducing Alembic in this phase.
"""

from typing import List, Optional

from src.core.db import get_db, register_pk
from src.utils.logging import get_logger

logger = get_logger(__name__)

_service: Optional["WatchlistService"] = None


def get_watchlist_service() -> "WatchlistService":
    global _service
    if _service is None:
        _service = WatchlistService()
    return _service


class WatchlistService:
    def __init__(self) -> None:
        self.db = get_db()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            with self.db.connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS watchlist (
                        user_id TEXT NOT NULL,
                        tmdb_id INTEGER NOT NULL,
                        media_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        poster_path TEXT,
                        year INTEGER,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, tmdb_id, media_type)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS watchlist_user_added "
                    "ON watchlist(user_id, added_at DESC)"
                )
            register_pk("watchlist", ["user_id", "tmdb_id", "media_type"])
        except Exception as exc:
            logger.warning(f"Watchlist schema init: {exc}")

    def list(self, user_id: str) -> List[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT user_id, tmdb_id, media_type, title, poster_path, year, added_at "
                "FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add(
        self,
        user_id: str,
        tmdb_id: int,
        media_type: str,
        title: str,
        poster_path: Optional[str] = None,
        year: Optional[int] = None,
    ) -> None:
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be movie|tv, got {media_type!r}")
        with self.db.connect() as conn:
            # INSERT OR REPLACE handles re-add (refreshes added_at + metadata).
            conn.execute(
                "INSERT OR REPLACE INTO watchlist "
                "(user_id, tmdb_id, media_type, title, poster_path, year, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (user_id, tmdb_id, media_type, title, poster_path, year),
            )

    def remove(self, user_id: str, tmdb_id: int, media_type: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM watchlist "
                "WHERE user_id = ? AND tmdb_id = ? AND media_type = ?",
                (user_id, tmdb_id, media_type),
            )

    def clear(self, user_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM watchlist WHERE user_id = ?", (user_id,))
