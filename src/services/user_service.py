"""User Service - User profile management."""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

    # ── Collaborative Filtering ───────────────────────────────────────────────

    # In-memory cache for the full ratings matrix (avoid repeated DB scans).
    _cf_matrix_cache: Dict = {}
    _CF_CACHE_TTL = 1800  # 30 minutes

    def get_all_ratings_matrix(self) -> Dict[str, Dict[str, float]]:
        """Return {user_id: {movie_id: rating}} for all users.

        Cached in memory for 30 minutes to avoid per-request DB scans.
        """
        now = time.time()
        cache = UserService._cf_matrix_cache
        if cache and (now - cache.get("loaded_at", 0)) < self._CF_CACHE_TTL:
            return cache["matrix"]

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, movie_id, rating FROM ratings")
        rows = cursor.fetchall()
        conn.close()

        matrix: Dict[str, Dict[str, float]] = {}
        for uid, mid, rating in rows:
            matrix.setdefault(uid, {})[str(mid)] = float(rating)

        UserService._cf_matrix_cache = {"matrix": matrix, "loaded_at": now}
        logger.info(f"CF matrix loaded: {len(matrix)} users, {len(rows)} ratings")
        return matrix

    def get_cf_candidates(
        self,
        user_id: str,
        k: int = 15,
        min_neighbors: int = 2,
    ) -> List[Tuple[str, float]]:
        """Return top-k (movie_id, cf_score) pairs via user-based CF.

        Algorithm:
        1. Load the full ratings matrix (cached).
        2. Compute cosine similarity between the target user and every other user.
        3. Gather movies rated highly (≥ 4.0) by the top-20 neighbors that the
           target user has NOT yet rated.
        4. Aggregate by weighted rating; return top-k.
        """
        matrix = self.get_all_ratings_matrix()
        if user_id not in matrix or len(matrix) < 3:
            return []

        user_ratings = matrix[user_id]
        rated_ids = set(user_ratings.keys())

        # Build cosine similarity against all other users
        user_vec = np.array(list(user_ratings.values()), dtype=float)
        user_movies = list(user_ratings.keys())

        neighbors: List[Tuple[str, float]] = []
        for other_id, other_ratings in matrix.items():
            if other_id == user_id:
                continue
            # Find movies rated by BOTH users
            common = set(user_movies) & set(other_ratings.keys())
            if len(common) < 2:
                continue
            u = np.array([user_ratings[m] for m in common])
            v = np.array([other_ratings[m] for m in common])
            norm = np.linalg.norm(u) * np.linalg.norm(v)
            if norm < 1e-9:
                continue
            sim = float(np.dot(u, v) / norm)
            if sim > 0.1:
                neighbors.append((other_id, sim))

        if not neighbors:
            return []

        neighbors.sort(key=lambda x: x[1], reverse=True)
        top_neighbors = neighbors[:20]

        # Aggregate scores: weighted sum of neighbor ratings for unseen movies
        movie_scores: Dict[str, float] = {}
        movie_weights: Dict[str, float] = {}
        movie_neighbor_count: Dict[str, int] = {}

        for neighbor_id, sim in top_neighbors:
            for mid, rating in matrix[neighbor_id].items():
                if mid in rated_ids or rating < 4.0:
                    continue
                movie_scores[mid] = movie_scores.get(mid, 0.0) + sim * rating
                movie_weights[mid] = movie_weights.get(mid, 0.0) + abs(sim)
                movie_neighbor_count[mid] = movie_neighbor_count.get(mid, 0) + 1

        results: List[Tuple[str, float]] = []
        for mid, score in movie_scores.items():
            w = movie_weights[mid]
            if w > 0 and movie_neighbor_count[mid] >= min_neighbors:
                normalized = score / w  # weighted average rating (0–5 scale)
                results.append((mid, min(normalized / 5.0, 1.0)))  # normalise to 0–1

        results.sort(key=lambda x: x[1], reverse=True)
        logger.info(
            f"CF for {user_id}: {len(top_neighbors)} neighbors, "
            f"{len(results)} candidate movies"
        )
        return results[:k]


# Singleton instance
_user_service = None


def get_user_service() -> UserService:
    """Get user service instance."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
