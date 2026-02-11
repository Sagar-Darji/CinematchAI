"""LangGraph state definitions for multi-agent workflow."""

from typing import Dict, List, Optional, TypedDict

from src.core.models import Movie, Recommendation, UserProfile


class RecommendationState(TypedDict, total=False):
    """Shared state for recommendation workflow."""

    # Input
    user_id: str
    context: Dict  # Time of day, mood, companion, etc.
    num_recommendations: int

    # User analysis (Profile Analyzer output)
    user_profile: Optional[UserProfile]
    user_embedding: Optional[List[float]]

    # Content analysis (Content Intelligence output)
    content_features: Optional[Dict]  # Micro-genres, themes, etc.

    # Context analysis (Context-Aware output)
    context_factors: Optional[Dict]  # Temporal, environmental factors
    context_weights: Optional[Dict]  # Weights for different factors

    # Retrieval (RAG output)
    candidate_movies: List[Movie]
    candidate_scores: List[float]

    # Diversity (Serendipity output)
    diverse_candidates: List[Movie]
    exploration_items: List[Movie]

    # Explanations (Explanation Agent output)
    explanations: Dict[str, str]  # movie_id -> explanation

    # Final output
    final_recommendations: List[Recommendation]

    # Metadata
    processing_steps: List[str]
    errors: List[str]
    agent_timings: Dict[str, float]


class GroupRecommendationState(TypedDict, total=False):
    """State for group recommendation workflow."""

    # Input
    user_ids: List[str]
    context: Dict
    num_recommendations: int
    aggregation_strategy: str  # multiplicative, least_misery, etc.

    # Individual profiles
    user_profiles: Dict[str, UserProfile]

    # Group analysis
    group_preferences: Dict
    conflict_areas: List[str]

    # Recommendations
    candidate_movies: List[Movie]
    final_recommendations: List[Recommendation]

    # Fairness metrics
    fairness_score: float
    satisfaction_distribution: Dict[str, float]

    # Metadata
    processing_steps: List[str]
    errors: List[str]
