"""User Service - User profile management."""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from config.settings import get_settings
from src.core.db import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()


class UserService:
    """Service for managing user profiles."""

    def __init__(self):
        """Initialize user service."""
        self.db_path = Path(settings.data_dir) / "users.db"
        self._init_database()

    def _connect(self):
        """Return an open DB connection (SQLite or PostgreSQL via adapter)."""
        return get_db().connect()

    def _init_database(self):
        """Initialize database schema (SQLite or PostgreSQL)."""
        db = get_db()
        if not db.is_postgres:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._connect()
        cursor = conn.cursor()

        # Postgres uses SERIAL; SQLite uses INTEGER PRIMARY KEY AUTOINCREMENT
        _serial = "SERIAL" if db.is_postgres else "INTEGER"

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                embedding_json TEXT,
                embedding_rating_count INTEGER DEFAULT 0,
                email TEXT UNIQUE,
                password_hash TEXT,
                auth_provider TEXT DEFAULT 'password',
                google_id TEXT UNIQUE
            )
        """)

        # Add columns when upgrading from older schema
        # Each ALTER runs in its own savepoint so a "column already exists" error
        # doesn't abort the whole transaction (PostgreSQL requires explicit rollback).
        for col, definition in [
            ("embedding_json",          "TEXT"),
            ("embedding_rating_count",  "INTEGER DEFAULT 0"),
            ("email",                   "TEXT"),
            ("password_hash",           "TEXT"),
            ("auth_provider",           "TEXT DEFAULT 'password'"),
            ("google_id",               "TEXT"),
            ("reset_token",             "TEXT"),
            ("reset_token_expires",     "TEXT"),
            ("favorite_tmdb_ids",       "TEXT"),
        ]:
            try:
                if db.is_postgres:
                    cursor.execute("SAVEPOINT alter_col")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
                if db.is_postgres:
                    cursor.execute("RELEASE SAVEPOINT alter_col")
            except Exception:
                if db.is_postgres:
                    cursor.execute("ROLLBACK TO SAVEPOINT alter_col")
                    cursor.execute("RELEASE SAVEPOINT alter_col")

        # Ratings table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS ratings (
                id {_serial} PRIMARY KEY {"AUTOINCREMENT" if not db.is_postgres else ""},
                user_id TEXT NOT NULL,
                movie_id TEXT NOT NULL,
                rating REAL NOT NULL,
                watched BOOLEAN DEFAULT TRUE,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, movie_id)
            )
        """)

        # Contexts table
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

        logger.info(f"Database initialised ({'PostgreSQL' if db.is_postgres else self.db_path})")

    def create_user_stub(self, user_id: str, email: Optional[str] = None) -> None:
        """Insert a minimal user row so foreign-key constraints are satisfied."""
        now = datetime.now(timezone.utc).isoformat()
        stub = json.dumps({"user_id": user_id, "total_ratings": 0, "is_cold_start": True})
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, created_at, updated_at, profile_json) VALUES (?,?,?,?)",
                (user_id, now, now, stub),
            )
            conn.commit()
        finally:
            conn.close()

    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile by ID."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row["profile_json"] if isinstance(row, dict) else row[0])
        return None

    def _row_to_auth(self, row) -> dict:
        """Normalise a DB row (sqlite3.Row or dict) to an auth dict."""
        if isinstance(row, dict):
            return row
        return {
            "user_id": row[0], "email": row[1], "password_hash": row[2],
            "auth_provider": row[3], "google_id": row[4],
        }

    def get_auth_record(self, user_id: str) -> Optional[dict]:
        """Return auth fields (email, password_hash, auth_provider, google_id) for a user."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, email, password_hash, auth_provider, google_id "
            "FROM users WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_auth(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Look up a user by email address."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, email, password_hash, auth_provider, google_id "
            "FROM users WHERE email = ?", (email.lower().strip(),)
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_auth(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """Look up a user by username (user_id)."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, email, password_hash, auth_provider, google_id "
            "FROM users WHERE user_id = ?", (username.strip(),)
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_auth(row) if row else None

    def get_user_by_google_id(self, google_id: str) -> Optional[dict]:
        """Look up a user by Google sub ID."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, email, password_hash, auth_provider, google_id "
            "FROM users WHERE google_id = ?", (google_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_auth(row) if row else None

    def set_reset_token(self, user_id: str, token: str, expires_at: str) -> None:
        """Store a password-reset token for the user."""
        conn = self._connect()
        conn.execute(
            "UPDATE users SET reset_token=?, reset_token_expires=? WHERE user_id=?",
            (token, expires_at, user_id),
        )
        conn.commit()
        conn.close()

    def consume_reset_token(self, token: str) -> Optional[str]:
        """
        Validate and consume a reset token.
        Returns the user_id if the token is valid and unexpired, else None.
        The token is cleared on success.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, reset_token_expires FROM users WHERE reset_token = ?", (token,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        user_id = row["user_id"] if isinstance(row, dict) else row[0]
        expires_at = row["reset_token_expires"] if isinstance(row, dict) else row[1]
        if not expires_at or expires_at < now:
            conn.close()
            return None
        # Clear the token so it can only be used once
        conn.execute(
            "UPDATE users SET reset_token=NULL, reset_token_expires=NULL WHERE user_id=?",
            (user_id,),
        )
        conn.commit()
        conn.close()
        return user_id

    def update_password(self, user_id: str, password_hash: str) -> None:
        """Set a new password hash for the user."""
        conn = self._connect()
        conn.execute(
            "UPDATE users SET password_hash=?, auth_provider='password', updated_at=? WHERE user_id=?",
            (password_hash, datetime.now(timezone.utc).isoformat(), user_id),
        )
        conn.commit()
        conn.close()

    def rename_user(self, old_user_id: str, new_user_id: str) -> bool:
        """Rename a user's user_id (username). Returns True on success."""
        conn = self._connect()
        try:
            # Update the stub profile_json that contains user_id
            conn.execute(
                "UPDATE users SET user_id=?, updated_at=? WHERE user_id=?",
                (new_user_id, datetime.now(timezone.utc).isoformat(), old_user_id),
            )
            # Update any ratings rows
            try:
                conn.execute(
                    "UPDATE ratings SET user_id=? WHERE user_id=?",
                    (new_user_id, old_user_id),
                )
            except Exception:
                pass  # ratings table may not exist yet
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    MAX_FAVORITES = 4

    def get_favorites(self, user_id: str) -> List[dict]:
        """Return the user's pinned favorites (movies/TV).

        Each item is a dict {tmdb_id, media_type, title, poster_path}. The
        list preserves insertion order and is at most MAX_FAVORITES long.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT favorite_tmdb_ids FROM users WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return []
        raw = row["favorite_tmdb_ids"] if isinstance(row, dict) else row[0]
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_favorites(self, user_id: str, items: List[dict]) -> List[dict]:
        """Replace the user's favorites list. Validates shape, dedupes, caps
        at MAX_FAVORITES, ensures the user row exists, and returns the
        canonical list that was stored."""
        cleaned: List[dict] = []
        seen: set = set()
        for item in items[: self.MAX_FAVORITES]:
            tmdb_id = item.get("tmdb_id")
            media_type = item.get("media_type")
            title = item.get("title")
            if not isinstance(tmdb_id, int) or media_type not in ("movie", "tv") or not title:
                raise ValueError(
                    f"Invalid favorite item: tmdb_id (int), media_type (movie|tv), and title are required"
                )
            key = (tmdb_id, media_type)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "title": title,
                "poster_path": item.get("poster_path"),
            })

        payload = json.dumps(cleaned)
        now = datetime.now(timezone.utc).isoformat()
        # Ensure the user row exists — UPDATE silently no-ops on a missing
        # row, which was eating saves for any user who hadn't yet had a
        # profile_json row written.
        stub = json.dumps({"user_id": user_id, "total_ratings": 0, "is_cold_start": True})
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, created_at, updated_at, profile_json) "
                "VALUES (?,?,?,?)",
                (user_id, now, now, stub),
            )
            conn.execute(
                "UPDATE users SET favorite_tmdb_ids=?, updated_at=? WHERE user_id=?",
                (payload, now, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        # Read-back to confirm persistence — surfaces silent failures (cached
        # connection holding stale schema, etc.) as a clear exception.
        stored = self.get_favorites(user_id)
        if len(stored) != len(cleaned):
            logger.warning(
                f"Favorites persistence mismatch for user_id={user_id}: "
                f"wrote {len(cleaned)} read back {len(stored)}"
            )
        return cleaned

    def set_auth_credentials(self, user_id: str, email: str,
                              password_hash: Optional[str],
                              auth_provider: str,
                              google_id: Optional[str] = None) -> None:
        """Write / overwrite auth columns for an existing user row."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET email=?, password_hash=?, auth_provider=?, google_id=?, updated_at=? "
            "WHERE user_id=?",
            (email.lower().strip(), password_hash, auth_provider, google_id,
             datetime.utcnow().isoformat(), user_id)
        )
        conn.commit()
        conn.close()


    def save_user_profile(self, user_id: str, profile):
        """
        Save user profile.

        Args:
            user_id: User ID.
            profile: UserProfile object.
        """
        conn = self._connect()
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
        conn = self._connect()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        # Ensure the user row exists so the user is visible in CLI/admin tools
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (user_id, created_at, updated_at, profile_json)
            VALUES (?, ?, ?, '{}')
        """,
            (user_id, now, now),
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO ratings (user_id, movie_id, rating, watched, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, movie_id, rating, watched, now),
        )

        conn.commit()
        conn.close()

        # Invalidate CF matrix cache so the next request uses updated ratings
        UserService._cf_matrix_cache.clear()
        # Drop the cached /admin profile response so the Profile page picks
        # up the new rating immediately on next refresh (otherwise the user
        # waits up to 30 min for the cache TTL).
        try:
            from src.api.routes.admin import invalidate_admin_profile_cache
            invalidate_admin_profile_cache(user_id)
        except Exception:
            pass

        logger.info(f"Added rating: user={user_id}, movie={movie_id}, rating={rating}")

    def record_feedback(
        self,
        user_id: str,
        movie_id: str,
        action: str,
    ) -> None:
        """Record implicit feedback from a recommendation interaction.

        Converts actions into implicit ratings stored in the ratings table.
        Only stores a rating if the user hasn't explicitly rated this movie
        already — explicit ratings always win.

        Args:
            user_id:  User ID.
            movie_id: TMDB movie ID.
            action:   One of "clicked", "watched", "dismissed".
        """
        IMPLICIT_RATING = {"watched": 4.0, "clicked": 3.5, "dismissed": 1.5}
        if action not in IMPLICIT_RATING:
            return

        implicit = IMPLICIT_RATING[action]
        conn = self._connect()
        cursor = conn.cursor()

        # Only insert if no explicit rating exists (explicit > implicit)
        cursor.execute(
            "SELECT rating FROM ratings WHERE user_id=? AND movie_id=?",
            (user_id, movie_id),
        )
        existing = cursor.fetchone()

        if existing is None:
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO ratings (user_id, movie_id, rating, watched, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, movie_id, implicit, action == "watched", now),
            )
            conn.commit()
            logger.info(
                f"Feedback recorded: user={user_id}, movie={movie_id}, "
                f"action={action}, implicit_rating={implicit}"
            )
        conn.close()

        # Invalidate the CF matrix cache so the next recommendation request
        # benefits from this new signal immediately.
        UserService._cf_matrix_cache.clear()
        try:
            from src.api.routes.admin import invalidate_admin_profile_cache
            invalidate_admin_profile_cache(user_id)
        except Exception:
            pass

    def get_user_ratings(self, user_id: str) -> List[Dict]:
        """
        Get all ratings for a user.

        Args:
            user_id: User ID.

        Returns:
            List of rating dictionaries.
        """
        conn = self._connect()
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
        conn = self._connect()
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
        conn = self._connect()
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
        conn = self._connect()
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
        conn = self._connect()
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
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def count_ratings(self) -> int:
        """Count total ratings across all users."""
        conn = self._connect()
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

        conn = self._connect()
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
            if sim > 0.25:  # Raised from 0.1 — fewer but higher-quality neighbors (#3)
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
