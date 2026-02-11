"""Profile Analyzer Agent - Analyzes user viewing history and builds profiles."""

import json
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
            settings = get_settings()

            # Load ratings
            ratings_df = pd.read_parquet(settings.processed_data_dir / "ratings.parquet")
            user_ratings = ratings_df[ratings_df["userId"] == int(user_id)]

            if len(user_ratings) == 0:
                return None

            # Load movies
            movies_df = pd.read_parquet(settings.processed_data_dir / "movies_enriched.parquet")

            # Merge ratings with movies
            user_movies = user_ratings.merge(movies_df, on="movieId", how="left")

            return {
                "total_ratings": len(user_ratings),
                "ratings_df": user_ratings,
                "movies_df": user_movies,
                "avg_rating": user_ratings["rating"].mean(),
                "rating_variance": user_ratings["rating"].var(),
            }

        except Exception as e:
            logger.error(f"Failed to load user data: {e}")
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
        profile_embedding = self._calculate_profile_embedding(ratings_df)

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

        # Extract directors
        director_counts = Counter(movies_df["director"].dropna())
        favorite_directors = [director for director, _ in director_counts.most_common(5)]

        # Extract decades
        decades = []
        for year in movies_df["year"].dropna():
            if year > 1900:
                decades.append((int(year) // 10) * 10)
        decade_counts = Counter(decades)
        preferred_decades = [decade for decade, _ in decade_counts.most_common(3)]

        # Calculate exploration rate (variance in genres/years)
        exploration_rate = min(len(genre_counts) / 20.0, 1.0)  # Normalize to 0-1

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

    def _calculate_profile_embedding(self, ratings_df: pd.DataFrame) -> Optional[List[float]]:
        """
        Calculate user profile embedding as weighted average of movie embeddings.

        Args:
            ratings_df: User ratings.

        Returns:
            Profile embedding vector or None.
        """
        try:
            settings = get_settings()
            embeddings_path = settings.embeddings_dir / "movie_hybrid_embeddings.npy"

            if not embeddings_path.exists():
                return None

            # Load embeddings
            embeddings = np.load(embeddings_path)

            # Load movies to map IDs to indices
            movies_df = pd.read_parquet(settings.processed_data_dir / "movies_enriched.parquet")
            movie_id_to_idx = {row["movieId"]: idx for idx, row in movies_df.iterrows()}

            # Calculate weighted average
            weighted_embeddings = []
            weights = []

            for _, rating in ratings_df.iterrows():
                movie_id = rating["movieId"]
                if movie_id in movie_id_to_idx:
                    idx = movie_id_to_idx[movie_id]
                    if idx < len(embeddings):
                        # Weight by rating (higher ratings = more influence)
                        weight = rating["rating"] / 5.0  # Normalize to 0-1
                        weighted_embeddings.append(embeddings[idx] * weight)
                        weights.append(weight)

            if not weighted_embeddings:
                return None

            # Calculate weighted average
            profile_embedding = np.sum(weighted_embeddings, axis=0) / np.sum(weights)

            # Normalize
            profile_embedding = profile_embedding / np.linalg.norm(profile_embedding)

            return profile_embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to calculate profile embedding: {e}")
            return None


def get_profile_analyzer_agent() -> ProfileAnalyzerAgent:
    """Get configured Profile Analyzer agent."""
    return ProfileAnalyzerAgent()
