"""Reviews service — per-user star ratings + free-text reviews of titles.

Mirrors the shape of HistoryService: one row per (user, tmdb_id, media_type)
upserted on save. rating is on a 0.5–5.0 (half-star) scale; both rating and
review_text are nullable independently — the only constraint is at least one
must be set.
"""

from typing import List, Optional

from src.core.db import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

_service: Optional["ReviewService"] = None

# Half-star steps from 0.5 to 5.0. Used to validate input.
_VALID_RATINGS = {round(0.5 * i, 1) for i in range(1, 11)}


def get_review_service() -> "ReviewService":
    global _service
    if _service is None:
        _service = ReviewService()
    return _service


class ReviewService:
    def __init__(self) -> None:
        self.db = get_db()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            with self.db.connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reviews (
                        user_id TEXT NOT NULL,
                        tmdb_id INTEGER NOT NULL,
                        media_type TEXT NOT NULL,
                        rating REAL,
                        review_text TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, tmdb_id, media_type)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS reviews_user_updated "
                    "ON reviews(user_id, updated_at DESC)"
                )
        except Exception as exc:
            logger.warning(f"Reviews schema init: {exc}")

    @staticmethod
    def _validate(media_type: str, rating: Optional[float], review_text: Optional[str]) -> None:
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be movie|tv, got {media_type!r}")
        if rating is None and not (review_text and review_text.strip()):
            raise ValueError("Provide a rating, review_text, or both")
        if rating is not None and round(rating, 1) not in _VALID_RATINGS:
            raise ValueError("rating must be a half-star value between 0.5 and 5.0")
        if review_text is not None and len(review_text) > 5000:
            raise ValueError("review_text exceeds 5000 character limit")

    def upsert(
        self,
        user_id: str,
        tmdb_id: int,
        media_type: str,
        rating: Optional[float] = None,
        review_text: Optional[str] = None,
    ) -> dict:
        self._validate(media_type, rating, review_text)
        clean_text = review_text.strip() if review_text else None
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reviews
                (user_id, tmdb_id, media_type, rating, review_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM reviews
                                  WHERE user_id=? AND tmdb_id=? AND media_type=?),
                                  CURRENT_TIMESTAMP),
                        CURRENT_TIMESTAMP)
                """,
                (
                    user_id, tmdb_id, media_type, rating, clean_text,
                    user_id, tmdb_id, media_type,
                ),
            )
        return self.get(user_id, tmdb_id, media_type) or {}

    def get(self, user_id: str, tmdb_id: int, media_type: str) -> Optional[dict]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT user_id, tmdb_id, media_type, rating, review_text, "
                "created_at, updated_at FROM reviews "
                "WHERE user_id=? AND tmdb_id=? AND media_type=?",
                (user_id, tmdb_id, media_type),
            ).fetchone()
        return dict(row) if row else None

    def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> List[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT user_id, tmdb_id, media_type, rating, review_text, "
                "created_at, updated_at FROM reviews "
                "WHERE user_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, user_id: str, tmdb_id: int, media_type: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM reviews WHERE user_id=? AND tmdb_id=? AND media_type=?",
                (user_id, tmdb_id, media_type),
            )
