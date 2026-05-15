"""Watch history service — per-user 'continue watching' state.

For TV titles we also persist last_season / last_episode so the player can
resume at the right episode. For movies these are NULL.
"""

from typing import List, Optional

from src.core.db import get_db, register_pk
from src.utils.logging import get_logger

logger = get_logger(__name__)

_service: Optional["HistoryService"] = None


def get_history_service() -> "HistoryService":
    global _service
    if _service is None:
        _service = HistoryService()
    return _service


class HistoryService:
    def __init__(self) -> None:
        self.db = get_db()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            with self.db.connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS watch_history (
                        user_id TEXT NOT NULL,
                        tmdb_id INTEGER NOT NULL,
                        media_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        poster_path TEXT,
                        year INTEGER,
                        last_season INTEGER,
                        last_episode INTEGER,
                        watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, tmdb_id, media_type)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS watch_history_user_watched "
                    "ON watch_history(user_id, watched_at DESC)"
                )
            register_pk("watch_history", ["user_id", "tmdb_id", "media_type"])
        except Exception as exc:
            logger.warning(f"Watch history schema init: {exc}")

    def list(self, user_id: str, limit: int = 60) -> List[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT user_id, tmdb_id, media_type, title, poster_path, year, "
                "last_season, last_episode, watched_at "
                "FROM watch_history WHERE user_id = ? "
                "ORDER BY watched_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def record(
        self,
        user_id: str,
        tmdb_id: int,
        media_type: str,
        title: str,
        poster_path: Optional[str] = None,
        year: Optional[int] = None,
        last_season: Optional[int] = None,
        last_episode: Optional[int] = None,
    ) -> None:
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be movie|tv, got {media_type!r}")
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO watch_history "
                "(user_id, tmdb_id, media_type, title, poster_path, year, "
                "last_season, last_episode, watched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (
                    user_id,
                    tmdb_id,
                    media_type,
                    title,
                    poster_path,
                    year,
                    last_season,
                    last_episode,
                ),
            )

    def remove(self, user_id: str, tmdb_id: int, media_type: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM watch_history "
                "WHERE user_id = ? AND tmdb_id = ? AND media_type = ?",
                (user_id, tmdb_id, media_type),
            )

    def clear(self, user_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM watch_history WHERE user_id = ?", (user_id,))

    def get_heatmap(self, user_id: str, year: int) -> dict:
        """Return {ISO date: count} of watch events for the given calendar year.

        Powers the diary heatmap. Days with zero watches are omitted — the
        frontend fills them in.
        """
        start = f"{year:04d}-01-01 00:00:00"
        end = f"{year + 1:04d}-01-01 00:00:00"
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT DATE(watched_at) AS day, COUNT(*) AS count "
                "FROM watch_history "
                "WHERE user_id = ? AND watched_at >= ? AND watched_at < ? "
                "GROUP BY DATE(watched_at)",
                (user_id, start, end),
            ).fetchall()
        result: dict = {}
        for row in rows:
            day = row["day"] if isinstance(row, dict) else row[0]
            count = row["count"] if isinstance(row, dict) else row[1]
            if day:
                # Postgres returns date objects; SQLite returns strings.
                result[str(day)] = int(count)
        return result
