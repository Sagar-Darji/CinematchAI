"""Watch history service — per-user 'continue watching' state.

For TV titles we also persist last_season / last_episode so the player can
resume at the right episode. For movies these are NULL.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

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

        Sources from BOTH `ratings.timestamp` and `watch_history.watched_at`,
        deduped by (day, movie_id, media_type). Rationale: most users on this
        product log a film by *rating* it (Letterboxd imports come in as
        rating rows with the original watch date as `timestamp`). The player's
        watch_history table is a far sparser signal. Reading only from
        watch_history produced "1 day in 2026" for users with 300+ Letterboxd
        ratings — accurate to the table, wrong as a heatmap.

        Days with zero watches are omitted — the frontend fills them in.
        """
        start = f"{year:04d}-01-01 00:00:00"
        end = f"{year + 1:04d}-01-01 00:00:00"
        # day → set of (movie_id, media_type) so a same-day rating + play of
        # the same title only counts once.
        day_entries: Dict[str, Set[Tuple[str, str]]] = {}

        def _ingest(day_val: Any, mid: Any, mtype: Any) -> None:
            if not day_val:
                return
            day_str = str(day_val)[:10]  # Postgres returns date; SQLite str
            key = (str(mid) if mid is not None else "", str(mtype or "movie"))
            day_entries.setdefault(day_str, set()).add(key)

        with self.db.connect() as conn:
            # ratings (Letterboxd-imported timestamps live here).
            # Exclude implicit feedback — those are likert reactions, not
            # watch events. Tolerate the table not existing (tests that only
            # exercise watch_history).
            try:
                rating_rows = conn.execute(
                    "SELECT DATE(timestamp) AS day, movie_id "
                    "FROM ratings "
                    "WHERE user_id = ? AND timestamp IS NOT NULL "
                    "AND timestamp >= ? AND timestamp < ? "
                    "AND COALESCE(source, '') != 'implicit_feedback'",
                    (user_id, start, end),
                ).fetchall()
            except Exception as exc:
                logger.debug(f"heatmap: ratings query skipped ({exc})")
                rating_rows = []
            for row in rating_rows:
                if isinstance(row, dict):
                    _ingest(row.get("day"), row.get("movie_id"), "movie")
                else:
                    _ingest(row[0], row[1], "movie")

            # watch_history (player-recorded progress events).
            for row in conn.execute(
                "SELECT DATE(watched_at) AS day, tmdb_id, media_type "
                "FROM watch_history "
                "WHERE user_id = ? AND watched_at >= ? AND watched_at < ?",
                (user_id, start, end),
            ).fetchall():
                if isinstance(row, dict):
                    _ingest(row.get("day"), row.get("tmdb_id"), row.get("media_type"))
                else:
                    _ingest(row[0], row[1], row[2])

        return {day: len(entries) for day, entries in day_entries.items()}
