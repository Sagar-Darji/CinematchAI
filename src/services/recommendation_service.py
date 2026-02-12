"""Recommendation Service - Business logic for recommendations."""

from typing import Any, Dict, List, Optional

from src.agents.graph.workflow import run_recommendation_workflow
from src.api.schemas.response import (
    MovieResponse,
    RecommendationItemResponse,
    RecommendationResponse,
)
from src.core.models import Recommendation
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RecommendationService:
    """Service for generating recommendations."""

    def get_recommendations(
        self,
        user_id: str,
        context: Optional[Dict[str, str]] = None,
        k: int = 10,
        use_hybrid: bool = True,
    ) -> RecommendationResponse:
        """
        Get personalized recommendations for a user.

        Args:
            user_id: User ID.
            context: Context information.
            k: Number of recommendations.
            use_hybrid: Use hybrid embeddings.

        Returns:
            Recommendation response.
        """
        logger.info(f"Getting recommendations for user_id={user_id}, k={k}")

        try:
            # Run workflow
            final_state = run_recommendation_workflow(
                user_id=user_id,
                context=context,
                is_cold_start=False,
            )

            # Convert to response format
            recommendations = self._convert_recommendations(
                final_state.get("final_recommendations", [])
            )

            # Limit to k
            recommendations = recommendations[:k]

            response = RecommendationResponse(
                user_id=user_id,
                recommendations=recommendations,
                workflow_type=final_state.get("workflow_type", "single_user"),
                processing_steps=final_state.get("processing_steps", []),
                context_factors=final_state.get("context_factors"),
            )

            logger.info(f"Generated {len(recommendations)} recommendations")

            return response

        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            raise

    def get_group_recommendations(
        self,
        user_ids: List[str],
        context: Optional[Dict[str, str]] = None,
        aggregation_strategy: str = "multiplicative",
        k: int = 10,
    ) -> Dict[str, Any]:
        """
        Get recommendations for a group of users.

        Args:
            user_ids: List of user IDs.
            context: Context information.
            aggregation_strategy: Strategy for aggregating preferences.
            k: Number of recommendations.

        Returns:
            Group recommendation response.
        """
        logger.info(
            f"Getting group recommendations for {len(user_ids)} users, strategy={aggregation_strategy}"
        )

        try:
            # Run workflow with group mode
            final_state = run_recommendation_workflow(
                user_ids=user_ids,
                context=context or {},
            )

            # Add aggregation strategy to state (before workflow starts)
            # Note: This should ideally be passed in the workflow itself
            final_state["aggregation_strategy"] = aggregation_strategy

            # Convert to response format
            recommendations = self._convert_recommendations(
                final_state.get("final_recommendations", [])
            )[:k]

            response = {
                "user_ids": user_ids,
                "recommendations": recommendations,
                "aggregation_strategy": aggregation_strategy,
                "fairness_score": final_state.get("fairness_score", 0.0),
                "satisfaction_distribution": final_state.get(
                    "satisfaction_distribution", {}
                ),
                "conflict_areas": final_state.get("conflict_areas", []),
                "processing_steps": final_state.get("processing_steps", []),
            }

            logger.info(
                f"Generated {len(recommendations)} group recommendations with fairness={response['fairness_score']:.2f}"
            )

            return response

        except Exception as e:
            logger.error(f"Failed to get group recommendations: {e}")
            raise

    def _convert_recommendations(
        self, recommendations: List[Recommendation]
    ) -> List[RecommendationItemResponse]:
        """
        Convert internal Recommendation objects to API response format.

        Args:
            recommendations: List of Recommendation objects.

        Returns:
            List of RecommendationItemResponse objects.
        """
        response_items = []

        for rec in recommendations:
            movie_response = MovieResponse(
                tmdb_id=int(rec.movie.metadata.tmdb_id) if rec.movie.metadata.tmdb_id else 0,
                title=rec.movie.metadata.title,
                year=rec.movie.metadata.year,
                genres=rec.movie.metadata.genres or [],
                overview=rec.movie.metadata.overview or "",
                vote_average=rec.movie.metadata.vote_average,
                director=rec.movie.metadata.director,
                poster_path=rec.movie.metadata.poster_path,
            )

            # Extract explanation text from Explanation object or string
            if hasattr(rec.explanation, "primary_reason"):
                explanation_text = rec.explanation.primary_reason
            else:
                explanation_text = str(rec.explanation)

            item = RecommendationItemResponse(
                movie=movie_response,
                score=rec.score,
                rank=rec.rank,
                explanation=explanation_text,
                is_exploration=rec.is_exploration,
            )

            response_items.append(item)

        return response_items


# Singleton instance
_recommendation_service = None


def get_recommendation_service() -> RecommendationService:
    """Get recommendation service instance."""
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationService()
    return _recommendation_service
