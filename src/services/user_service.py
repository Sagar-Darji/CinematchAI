"""User Service - User profile management."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()


class UserService:
    """Service for managing user profiles."""

    def __init__(self):
        """Initialize user service."""
        self.db_path = Path(settings.data_dir) / "users.db"
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                embedding_json TEXT,
                embedding_rating_count INTEGER DEFAULT 0
            )
        """)

        # Add columns if upgrading from older schema
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN embedding_json TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN embedding_rating_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # Ratings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                movie_id TEXT NOT NULL,
                rating REAL NOT NULL,
                watched BOOLEAN DEFAULT 1,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, movie_id)
            )
        """)

        # Contexts table (session context)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                user_id TEXT PRIMARY KEY,
                context_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        conn.commit()
        conn.close()

        logger.info(f"Database initialized at {self.db_path}")

    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """
        Get user profile by ID.

        Args:
            user_id: User ID.

        Returns:
            UserProfile or None if not found.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            profile_data = json.loads(row[0])
            # Reconstruct UserProfile
            # (Simplified - in production, you'd deserialize properly)
            return profile_data
        else:
            return None

    def save_user_profile(self, user_id: str, profile):
        """
        Save user profile.

        Args:
            user_id: User ID.
            profile: UserProfile object.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        # Serialize profile using Pydantic v2 model_dump
        profile_json = json.dumps(
            {
                "user_id": user_id,
                "preferences": profile.preferences.model_dump() if profile.preferences else {},
                "temporal_patterns": profile.temporal_patterns.model_dump() if profile.temporal_patterns else {},
                "total_ratings": profile.total_ratings,
                "avg_rating_given": profile.avg_rating_given,
                "is_cold_start": profile.is_cold_start,
                "last_updated": now,
            }
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO users (user_id, created_at, updated_at, profile_json)
            VALUES (?, ?, ?, ?)
        """,
            (user_id, now, now, profile_json),
        )

        conn.commit()
        conn.close()

        logger.info(f"Saved profile for user_id={user_id}")

    def add_rating(
        self, user_id: str, movie_id: str, rating: float, watched: bool = True
    ):
        """
        Add or update a rating.

        Args:
            user_id: User ID.
            movie_id: Movie TMDB ID.
            rating: Rating value (0.5-5.0).
            watched: Whether the user watched the movie.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO ratings (user_id, movie_id, rating, watched, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, movie_id, rating, watched, now),
        )

        conn.commit()
        conn.close()

        logger.info(f"Added rating: user={user_id}, movie={movie_id}, rating={rating}")

    def get_user_ratings(self, user_id: str) -> List[Dict]:
        """
        Get all ratings for a user.

        Args:
            user_id: User ID.

        Returns:
            List of rating dictionaries.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT movie_id, rating, watched, timestamp
            FROM ratings
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """,
            (user_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        ratings = []
        for row in rows:
            ratings.append(
                {
                    "movie_id": row[0],
                    "rating": row[1],
                    "watched": bool(row[2]),
                    "timestamp": row[3],
                }
            )

        return ratings

    def update_context(self, user_id: str, context: Dict[str, str]):
        """
        Update user's current context.

        Args:
            user_id: User ID.
            context: Context dictionary.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()
        context_json = json.dumps(context)

        cursor.execute(
            """
            INSERT OR REPLACE INTO contexts (user_id, context_json, updated_at)
            VALUES (?, ?, ?)
        """,
            (user_id, context_json, now),
        )

        conn.commit()
        conn.close()

        logger.info(f"Updated context for user_id={user_id}")

    def get_context(self, user_id: str) -> Dict[str, str]:
        """
        Get user's current context.

        Args:
            user_id: User ID.

        Returns:
            Context dictionary.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT context_json FROM contexts WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        else:
            return {}

    def get_cached_embedding(self, user_id: str) -> Optional[Dict]:
        """Get cached profile embedding if it exists and is current."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT embedding_json, embedding_rating_count FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return {
                "embedding": json.loads(row[0]),
                "rating_count": row[1] or 0,
            }
        return None

    def save_embedding(self, user_id: str, embedding: list, rating_count: int):
        """Cache profile embedding with the rating count it was built from."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            UPDATE users SET embedding_json = ?, embedding_rating_count = ?, updated_at = ?
            WHERE user_id = ?
        """,
            (json.dumps(embedding), rating_count, now, user_id),
        )
        conn.commit()
        conn.close()
        logger.info(f"Cached embedding for user_id={user_id} (ratings={rating_count})")

    def count_users(self) -> int:
        """Count total registered users."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def count_ratings(self) -> int:
        """Count total ratings across all users."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ratings")
        count = cursor.fetchone()[0]
        conn.close()
        return count


# Singleton instance
_user_service = None


def get_user_service() -> UserService:
    """Get user service instance."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
