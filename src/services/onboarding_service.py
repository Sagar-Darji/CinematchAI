"""Onboarding Service - Handles cold-start users."""

from typing import Dict, List, Optional

from src.agents.graph.workflow import run_recommendation_workflow
from src.api.schemas.response import OnboardingResponse, RecommendationItemResponse
from src.services.recommendation_service import RecommendationService
from src.services.user_service import get_user_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OnboardingService:
    """Service for onboarding new users (cold-start problem)."""

    def __init__(self):
        """Initialize onboarding service."""
        self.user_service = get_user_service()
        self.rec_service = RecommendationService()

    def onboard_user(
        self,
        user_id: str,
        ratings: Dict[str, float],
        preferences: Optional[Dict[str, List[str]]] = None,
    ) -> OnboardingResponse:
        """
        Onboard a new user with initial ratings.

        Args:
            user_id: New user ID.
            ratings: Initial ratings (movie_id -> rating). Min 5 ratings.
            preferences: Optional explicit preferences.

        Returns:
            Onboarding response with initial recommendations.
        """
        logger.info(
            f"Onboarding user_id={user_id} with {len(ratings)} initial ratings"
        )

        if len(ratings) < 5:
            raise ValueError("At least 5 ratings required for onboarding")

        try:
            # Save ratings to database
            for movie_id, rating in ratings.items():
                self.user_service.add_rating(
                    user_id=user_id,
                    movie_id=movie_id,
                    rating=rating,
                    watched=True,
                )

            # Create initial user profile using ProfileAnalyzer
            # (This will be done by the workflow when we call recommendations)

            # Save explicit preferences if provided
            if preferences:
                # In production, you'd store these in the user profile
                logger.info(f"Received explicit preferences: {preferences}")

            # Generate initial recommendations
            logger.info("Generating initial recommendations for new user")

            recommendation_response = self.rec_service.get_recommendations(
                user_id=user_id,
                context=None,
                k=10,
                use_hybrid=True,
            )

            response = OnboardingResponse(
                user_id=user_id,
                profile_created=True,
                initial_recommendations=recommendation_response.recommendations,
                message=f"Successfully onboarded user {user_id} with {len(ratings)} ratings. Generated {len(recommendation_response.recommendations)} initial recommendations.",
            )

            logger.info(f"Onboarding completed for user_id={user_id}")

            return response

        except Exception as e:
            logger.error(f"Failed to onboard user: {e}")
            raise

    def get_onboarding_movies(self, k: int = 20) -> List[Dict]:
        """
        Get diverse popular movies for onboarding flow.

        Args:
            k: Number of movies to return.

        Returns:
            List of movie dictionaries for rating.
        """
        logger.info(f"Getting {k} onboarding movies")

        # In production, you'd retrieve a curated list of popular,
        # diverse movies from different genres
        # For now, return a placeholder

        # This could use cold_start_retrieval from tools.py
        try:
            from src.agents.graph.tools import cold_start_retrieval

            state = {}
            state = cold_start_retrieval(state)

            candidate_movies = state.get("candidate_movies", [])

            onboarding_movies = []
            for movie in candidate_movies[:k]:
                onboarding_movies.append(
                    {
                        "tmdb_id": movie.metadata.tmdb_id,
                        "title": movie.metadata.title,
                        "year": movie.metadata.year,
                        "genres": movie.metadata.genres,
                        "overview": movie.metadata.overview,
                        "poster_path": movie.metadata.poster_path,
                        "vote_average": movie.metadata.vote_average,
                    }
                )

            logger.info(f"Retrieved {len(onboarding_movies)} onboarding movies")

            return onboarding_movies

        except Exception as e:
            logger.error(f"Failed to get onboarding movies: {e}")
            return []


# Singleton instance
_onboarding_service = None


def get_onboarding_service() -> OnboardingService:
    """Get onboarding service instance."""
    global _onboarding_service
    if _onboarding_service is None:
        _onboarding_service = OnboardingService()
    return _onboarding_service
