"""Profile Analyzer Agent - Analyzes user viewing history and builds profiles."""

import json
import math
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.agents.base_agent import BaseAgent
from src.core.models import TemporalPattern, UserPreferences, UserProfile
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProfileAnalyzerAgent(BaseAgent):
    """Agent that analyzes user viewing history and builds psychological profiles."""

    def __init__(self):
        """Initialize Profile Analyzer agent."""
        super().__init__(
            name="Profile Analyzer",
            description="Analyzes user viewing history and builds psychological profile",
            temperature=0.3,  # Lower temperature for consistent analysis
            use_fast_model=False,  # Use main model for better analysis
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user data and build profile.

        Args:
            state: Current state with user_id.

        Returns:
            Updated state with user_profile.
        """
        self.log_processing("Starting profile analysis")

        user_id = state.get("user_id")
        if not user_id:
            state["errors"] = state.get("errors", []) + ["No user_id provided"]
            return state

        # Load user data
        user_data = self._load_user_data(user_id)

        if not user_data or user_data["total_ratings"] == 0:
            # Cold-start user - create minimal profile
            self.log_processing(f"Cold-start user: {user_id}")
            user_profile = self._create_cold_start_profile(user_id)
        else:
            # Build full profile
            self.log_processing(f"Building profile for user {user_id} ({user_data['total_ratings']} ratings)")
            user_profile = self._build_profile(user_id, user_data)

        # Update state
        state["user_profile"] = user_profile
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Profile Analyzer: Analyzed user {user_id}"
        ]

        # Persist profile to database for non-cold-start users
        if user_profile and not user_profile.is_cold_start:
            try:
                from src.services.user_service import get_user_service
                get_user_service().save_user_profile(user_id, user_profile)
                self.log_processing(f"Persisted profile for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to persist profile for {user_id}: {e}")

        return state

    def _load_user_data(self, user_id: str) -> Optional[Dict]:
        """
        Load user's viewing history and ratings.

        Args:
            user_id: User identifier.

        Returns:
            User data dictionary or None if not found.
        """
        try:
            # CRITICAL FIX: Load ratings from SQLite database (not Parquet)
            # This allows Letterboxd imports and manual ratings to work
            from src.services.user_service import get_user_service
            from src.services.movie_service import get_movie_service

            user_service = get_user_service()
            movie_service = get_movie_service()

            # Get ratings from SQLite
            ratings = user_service.get_user_ratings(user_id)

            if not ratings or len(ratings) == 0:
                logger.info(f"No ratings found for user {user_id} in database")
                return None

            logger.info(f"Found {len(ratings)} ratings for user {user_id} in database")

            # Batch fetch all movies in parallel (instead of 1-by-1)
            movie_ids = [int(r["movie_id"]) for r in ratings]
            movies_batch = movie_service.get_movies_batch(movie_ids, max_workers=8)
            movie_lookup = {mid: movie for mid, movie in zip(movie_ids, movies_batch) if movie}

            # Convert to DataFrame for processing
            ratings_data = []
            movies_data = []

            for rating in ratings:
                movie_id = int(rating["movie_id"])
                movie = movie_lookup.get(movie_id)
                if movie:
                    ratings_data.append({
                        "movieId": movie_id,
                        "rating": rating["rating"],
                        "timestamp": pd.to_datetime(rating["timestamp"]),
                    })
                    movies_data.append({
                        "movieId": movie_id,
                        "title": movie.metadata.title,
                        "tmdb_genres": movie.metadata.genres,
                        "director": movie.metadata.director,
                        "cast": movie.metadata.cast or [],
                        "year": movie.metadata.year,
                        "vote_average": movie.metadata.vote_average,
                    })

            if not ratings_data:
                logger.warning(f"No valid movies found for user {user_id}")
                return None

            ratings_df = pd.DataFrame(ratings_data)
            movies_df = pd.DataFrame(movies_data)

            # Merge ratings with movies
            user_movies = ratings_df.merge(movies_df, on="movieId", how="left")

            return {
                "total_ratings": len(ratings_df),
                "ratings_df": ratings_df,
                "movies_df": user_movies,
                "avg_rating": ratings_df["rating"].mean(),
                "rating_variance": ratings_df["rating"].var(),
            }

        except Exception as e:
            logger.error(f"Failed to load user data: {e}", exc_info=True)
            return None

    def _create_cold_start_profile(self, user_id: str) -> UserProfile:
        """
        Create minimal profile for cold-start users.

        Args:
            user_id: User identifier.

        Returns:
            Minimal user profile.
        """
        return UserProfile(
            user_id=user_id,
            preferences=UserPreferences(),
            temporal_patterns=TemporalPattern(),
            is_cold_start=True,
            total_ratings=0,
        )

    def _build_profile(self, user_id: str, user_data: Dict) -> UserProfile:
        """
        Build comprehensive user profile.

        Args:
            user_id: User identifier.
            user_data: User's viewing data.

        Returns:
            Complete user profile.
        """
        movies_df = user_data["movies_df"]
        ratings_df = user_data["ratings_df"]

        # Extract preferences
        preferences = self._extract_preferences(movies_df)

        # Extract temporal patterns
        temporal_patterns = self._extract_temporal_patterns(ratings_df, movies_df)

        # Calculate profile embedding (weighted average of movie embeddings)
        profile_embedding = self._calculate_profile_embedding(ratings_df, user_id=user_id)

        # Build profile
        profile = UserProfile(
            user_id=user_id,
            preferences=preferences,
            temporal_patterns=temporal_patterns,
            profile_embedding=profile_embedding,
            total_ratings=user_data["total_ratings"],
            avg_rating_given=user_data["avg_rating"],
            rating_variance=user_data["rating_variance"],
            recent_movie_ids=[str(mid) for mid in ratings_df.nlargest(10, "timestamp")["movieId"].tolist()],
            recent_ratings=ratings_df.nlargest(10, "timestamp")["rating"].tolist(),
            is_cold_start=False,
            last_updated=datetime.now(),
        )

        profile.update_cold_start_status()

        return profile

    def _extract_preferences(self, movies_df: pd.DataFrame) -> UserPreferences:
        """
        Extract user preferences from viewing history.

        Args:
            movies_df: User's rated movies.

        Returns:
            User preferences.
        """
        # Extract genres
        all_genres = []
        for genres in movies_df["tmdb_genres"].dropna():
            if isinstance(genres, list):
                all_genres.extend(genres)

        genre_counts = Counter(all_genres)
        favorite_genres = [genre for genre, _ in genre_counts.most_common(5)]

        # Extract directors (weighted by rating — only count for highly-rated films)
        director_counts: Counter = Counter()
        for _, row in movies_df.iterrows():
            if pd.notna(row.get("director")) and row.get("director"):
                director_counts[row["director"]] += 1
        favorite_directors = [d for d, _ in director_counts.most_common(5)]

        # Extract favorite actors from highly-rated films (rating ≥ 4.0 in merged data)
        actor_counts: Counter = Counter()
        if "cast" in movies_df.columns:
            high_rated_ids = set()
            try:
                merged_data = movies_df  # cast is per movie, not per rating
                for _, row in merged_data.iterrows():
                    cast_list = row.get("cast", [])
                    if isinstance(cast_list, list):
                        for actor in cast_list[:3]:  # top-3 billed actors only
                            if actor:
                                actor_counts[actor] += 1
            except Exception:
                pass
        favorite_actors = [a for a, _ in actor_counts.most_common(8)]

        # Extract decades
        decades = []
        for year in movies_df["year"].dropna():
            if year > 1900:
                decades.append((int(year) // 10) * 10)
        decade_counts = Counter(decades)
        preferred_decades = [decade for decade, _ in decade_counts.most_common(3)]

        # Calculate exploration rate based on genre diversity.
        # Scale: 1 genre → 0.05, 10 genres → 0.25, 20+ genres → 0.50 (max).
        # Cap at 0.50 so even very diverse users still get ≥50% relevant recs.
        exploration_rate = min(len(genre_counts) / 20.0, 0.50)

        # Calculate nostalgia tendency (preference for older movies)
        current_year = datetime.now().year
        avg_year = movies_df["year"].mean()
        if pd.notna(avg_year):
            year_diff = current_year - avg_year
            nostalgia_tendency = min(year_diff / 30.0, 1.0)  # Normalize
        else:
            nostalgia_tendency = 0.5

        # Calculate risk tolerance (willingness to watch low-rated but interesting movies)
        low_rated_but_watched = len(movies_df[movies_df["vote_average"] < 6.0])
        risk_tolerance = min(low_rated_but_watched / max(len(movies_df), 1) + 0.3, 1.0)

        return UserPreferences(
            favorite_genres=favorite_genres,
            favorite_directors=favorite_directors,
            favorite_actors=favorite_actors,
            preferred_decades=preferred_decades,
            exploration_rate=exploration_rate,
            nostalgia_tendency=nostalgia_tendency,
            risk_tolerance=risk_tolerance,
        )

    def _extract_temporal_patterns(
        self, ratings_df: pd.DataFrame, movies_df: pd.DataFrame
    ) -> TemporalPattern:
        """
        Extract temporal viewing patterns.

        Args:
            ratings_df: User ratings with timestamps.
            movies_df: Rated movies with genres.

        Returns:
            Temporal patterns.
        """
        # Add day of week and hour
        ratings_df = ratings_df.copy()
        ratings_df["day_of_week"] = ratings_df["timestamp"].dt.day_name()
        ratings_df["hour"] = ratings_df["timestamp"].dt.hour

        # Merge with movies to get genres
        ratings_with_movies = ratings_df.merge(
            movies_df[["movieId", "tmdb_genres"]], on="movieId", how="left"
        )

        # Weekend vs weekday preferences
        weekend_ratings = ratings_with_movies[
            ratings_with_movies["day_of_week"].isin(["Saturday", "Sunday"])
        ]
        weekday_ratings = ratings_with_movies[
            ~ratings_with_movies["day_of_week"].isin(["Saturday", "Sunday"])
        ]

        weekend_genres = self._most_common_genre(weekend_ratings)
        weekday_genres = self._most_common_genre(weekday_ratings)

        # Time of day preferences
        evening_ratings = ratings_with_movies[
            (ratings_with_movies["hour"] >= 18) & (ratings_with_movies["hour"] <= 23)
        ]
        morning_ratings = ratings_with_movies[
            (ratings_with_movies["hour"] >= 6) & (ratings_with_movies["hour"] <= 12)
        ]

        evening_genre = self._most_common_genre(evening_ratings)
        morning_genre = self._most_common_genre(morning_ratings)

        # Peak viewing time
        peak_hour_counts = ratings_df["hour"].value_counts()
        peak_viewing_time = (
            self._hour_to_period(peak_hour_counts.index[0])
            if len(peak_hour_counts) > 0
            else None
        )

        # Peak viewing day
        peak_day_counts = ratings_df["day_of_week"].value_counts()
        peak_viewing_day = peak_day_counts.index[0] if len(peak_day_counts) > 0 else None

        return TemporalPattern(
            weekend_preference=weekend_genres,
            weekday_preference=weekday_genres,
            evening_preference=evening_genre,
            morning_preference=morning_genre,
            peak_viewing_time=peak_viewing_time,
            peak_viewing_day=peak_viewing_day,
        )

    def _most_common_genre(self, df: pd.DataFrame) -> Optional[str]:
        """Get most common genre from dataframe."""
        all_genres = []
        for genres in df["tmdb_genres"].dropna():
            if isinstance(genres, list):
                all_genres.extend(genres)

        if not all_genres:
            return None

        genre_counts = Counter(all_genres)
        return genre_counts.most_common(1)[0][0]

    def _hour_to_period(self, hour: int) -> str:
        """Convert hour to period of day."""
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 23:
            return "evening"
        else:
            return "night"

    def _calculate_profile_embedding(self, ratings_df: pd.DataFrame, user_id: str = None) -> Optional[List[float]]:
        """
        Calculate user profile embedding as weighted average of movie embeddings.

        Uses DB cache to avoid recomputing when rating count hasn't changed.

        Args:
            ratings_df: User ratings.
            user_id: User ID for cache lookup.

        Returns:
            Profile embedding vector or None.
        """
        try:
            from src.services.movie_service import get_movie_service
            from src.core.embeddings.text_embedder import get_text_embedder
            from src.services.user_service import get_user_service
            from config.settings import get_settings as _get_settings

            settings = _get_settings()
            use_multimodal = settings.use_multimodal_embeddings

            total_ratings = len(ratings_df)

            # Check cache first
            if user_id:
                user_service = get_user_service()
                cached = user_service.get_cached_embedding(user_id)
                if cached and cached["rating_count"] == total_ratings:
                    logger.info(f"Using cached embedding for {user_id} (ratings={total_ratings})")
                    return cached["embedding"]

            movie_service = get_movie_service()
            text_embedder = get_text_embedder()

            # Lazy-load hybrid embedder only when multimodal is enabled
            hybrid_embedder = None
            if use_multimodal:
                try:
                    from src.core.embeddings.hybrid_embedder import get_hybrid_embedder
                    hybrid_embedder = get_hybrid_embedder()
                    logger.info("Multimodal embeddings enabled (text + CLIP poster)")
                except Exception as e:
                    logger.warning(f"Could not load hybrid embedder — falling back to text-only: {e}")
                    use_multimodal = False

            logger.info(f"Computing profile embedding from {len(ratings_df)} ratings")

            # Batch fetch all movies in parallel (fixes N+1 sequential API calls)
            movie_ids = [int(r["movieId"]) for _, r in ratings_df.iterrows()]
            movies_batch = movie_service.get_movies_batch(movie_ids, max_workers=5)
            movie_lookup = {mid: movie for mid, movie in zip(movie_ids, movies_batch)}

            # Pass 1: collect texts + weights + poster URLs (no embedding yet)
            texts: list = []
            weights: list = []
            poster_urls: list = []

            for _, rating in ratings_df.iterrows():
                movie_id = rating["movieId"]
                movie = movie_lookup.get(int(movie_id))

                if not movie or not movie.metadata.overview:
                    continue

                text = f"{movie.metadata.title}. {movie.metadata.overview}"
                if movie.metadata.genres:
                    text += f" Genres: {', '.join(movie.metadata.genres)}"

                # Temporal decay: half-life ≈ 350 days — old favourites still matter.
                # Negative signal: ratings ≤ 2.5 get a small negative weight so the
                # profile embedding is pushed *away* from disliked content.
                raw_rating = rating["rating"]
                if raw_rating <= 2.5:
                    rating_weight = -0.3 * (1.0 - raw_rating / 5.0)
                else:
                    rating_weight = raw_rating / 5.0
                ts = rating.get("timestamp")
                days_ago = 0
                if ts is not None:
                    try:
                        days_ago = max(
                            0,
                            (datetime.now() - pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None)).days,
                        )
                    except Exception:
                        days_ago = 0
                weights.append(rating_weight * math.exp(-0.002 * days_ago))
                texts.append(text)
                # Store poster URL for multimodal (TMDB CDN)
                poster_path = movie.metadata.poster_path or ""
                poster_urls.append(
                    f"https://image.tmdb.org/t/p/w185{poster_path}" if poster_path else ""
                )

            if not texts:
                logger.warning("No movies with overviews found — profile will be cold-start")
                return None

            # Pass 2a: batch text encode (single forward pass for all texts)
            raw_text_embeddings = []
            try:
                raw_text_embeddings = list(text_embedder.embed_batch(texts))  # (n, dim)
            except Exception as e:
                logger.warning(f"Batch encode failed, falling back to per-movie: {e}")
                for text in texts:
                    try:
                        raw_text_embeddings.append(text_embedder.embed_text(text)[0])
                    except Exception:
                        raw_text_embeddings.append(None)

            # Pass 2b: optional CLIP poster fusion
            weighted_embeddings = []
            for i, (text_emb, w, poster_url) in enumerate(zip(raw_text_embeddings, weights, poster_urls)):
                if text_emb is None or len(text_emb) == 0:
                    continue
                if use_multimodal and hybrid_embedder and poster_url:
                    try:
                        final_emb = hybrid_embedder.embed_movie(
                            title=texts[i].split(".")[0],
                            overview=None,
                            poster_path=poster_url,
                        )
                    except Exception:
                        # CLIP fetch failed (e.g. no poster) — fall back to text-only
                        final_emb = np.array(text_emb)
                else:
                    final_emb = np.array(text_emb)
                weighted_embeddings.append(final_emb * w)

            if not weighted_embeddings:
                logger.warning("No embeddings generated — profile will be cold-start")
                return None

            # Weighted average
            profile_embedding = np.sum(weighted_embeddings, axis=0) / np.sum(weights)

            # Normalize
            profile_embedding = profile_embedding / np.linalg.norm(profile_embedding)

            logger.info(f"Generated profile embedding ({len(profile_embedding)}-dim) from {len(weighted_embeddings)} movies")

            embedding_list = profile_embedding.tolist()

            # Save to cache
            if user_id:
                try:
                    user_service = get_user_service()
                    user_service.save_embedding(user_id, embedding_list, total_ratings)
                except Exception as e:
                    logger.warning(f"Failed to cache embedding: {e}")

            return embedding_list

        except Exception as e:
            logger.error(f"Failed to calculate profile embedding: {e}", exc_info=True)
            return None


def get_profile_analyzer_agent() -> ProfileAnalyzerAgent:
    """Get configured Profile Analyzer agent."""
    return ProfileAnalyzerAgent()
