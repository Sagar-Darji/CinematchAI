"""Recommendation data models."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .movie import Movie


class Explanation(BaseModel):
    """Explanation for a recommendation."""

    primary_reason: str = Field(..., description="Main reason for recommendation")
    supporting_factors: List[str] = Field(
        default_factory=list, description="Additional supporting factors"
    )
    diversity_note: Optional[str] = Field(
        None, description="Note about diversity/exploration (if applicable)"
    )
    counterfactual: Optional[str] = Field(
        None, description="Why not another movie? (counterfactual explanation)"
    )
    confidence: float = Field(..., description="Confidence in recommendation (0-1)")

    # Breakdown of scores
    content_score: Optional[float] = Field(None, description="Content-based similarity score")
    collaborative_score: Optional[float] = Field(None, description="Collaborative filtering score")
    context_score: Optional[float] = Field(None, description="Context relevance score")
    novelty_score: Optional[float] = Field(None, description="Novelty/serendipity score")


class Recommendation(BaseModel):
    """Single movie recommendation."""

    movie: Movie = Field(..., description="Recommended movie")
    score: float = Field(..., description="Overall recommendation score (0-1)")
    predicted_rating: Optional[float] = Field(None, description="Predicted user rating (0-5)")
    rank: int = Field(..., description="Rank in recommendation list (1-indexed)")

    explanation: Explanation = Field(..., description="Explanation for recommendation")

    # Metadata
    similarity_to_favorites: Optional[float] = Field(
        None, description="Similarity to user's favorite movies"
    )
    is_exploration: bool = Field(
        default=False, description="Whether this is an exploratory recommendation"
    )


class RecommendationResponse(BaseModel):
    """Complete recommendation response."""

    user_id: str = Field(..., description="User ID")
    recommendations: List[Recommendation] = Field(..., description="List of recommendations")

    # Metadata
    num_recommendations: int = Field(..., description="Number of recommendations returned")
    diversity_score: float = Field(..., description="Overall diversity of recommendations (0-1)")
    avg_novelty: float = Field(..., description="Average novelty score (0-1)")

    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    agents_used: List[str] = Field(
        default_factory=list, description="Agents involved in generation"
    )

    # Context used
    context: Optional[Dict] = Field(None, description="Context used for recommendations")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class GroupRecommendation(BaseModel):
    """Recommendation for a group of users."""

    group_id: str = Field(..., description="Group identifier")
    user_ids: List[str] = Field(..., description="User IDs in group")

    recommendations: List[Recommendation] = Field(..., description="Group recommendations")

    # Fairness metrics
    fairness_score: float = Field(..., description="Overall fairness score (0-1)")
    satisfaction_distribution: Dict[str, float] = Field(
        ..., description="Satisfaction score per user (0-1)"
    )
    min_satisfaction: float = Field(..., description="Minimum user satisfaction (0-1)")

    # Aggregation info
    aggregation_strategy: str = Field(..., description="Strategy used (multiplicative, least_misery, etc.)")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
