"""API Response Schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MovieResponse(BaseModel):
    """Movie information in API response."""

    tmdb_id: int
    title: str
    year: Optional[int]
    genres: List[str]
    overview: str
    vote_average: Optional[float]
    director: Optional[str]
    poster_path: Optional[str]


class RecommendationItemResponse(BaseModel):
    """Single recommendation item."""

    movie: MovieResponse
    score: float = Field(..., ge=0.0, le=1.0, description="Recommendation score")
    rank: int = Field(..., ge=1, description="Rank in recommendation list")
    explanation: str = Field(..., description="Natural language explanation")
    is_exploration: bool = Field(
        default=False, description="Whether this is an exploratory recommendation"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class RecommendationResponse(BaseModel):
    """Response for recommendation requests."""

    user_id: str
    recommendations: List[RecommendationItemResponse]
    workflow_type: str = Field(
        ..., description="Workflow type: single_user, group, cold_start"
    )
    processing_steps: List[str] = Field(
        default=[], description="Processing steps taken"
    )
    context_factors: Optional[Dict[str, Any]] = Field(
        default=None, description="Detected context factors"
    )
    trace_id: Optional[str] = Field(
        default=None, description="Pipeline trace ID for admin monitoring"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user123",
                    "recommendations": [
                        {
                            "movie": {
                                "tmdb_id": 550,
                                "title": "Fight Club",
                                "year": 1999,
                                "genres": ["Drama"],
                                "overview": "A ticking-time-bomb insomniac...",
                                "vote_average": 8.4,
                                "director": "David Fincher",
                                "poster_path": "/path.jpg",
                            },
                            "score": 0.95,
                            "rank": 1,
                            "explanation": "Based on your love for psychological thrillers...",
                            "is_exploration": False,
                        }
                    ],
                    "workflow_type": "single_user",
                    "processing_steps": [
                        "Profile Analyzer: Analyzed 150 ratings",
                        "Context-Aware: Analyzed viewing context",
                    ],
                }
            ]
        }
    }


class GroupRecommendationResponse(BaseModel):
    """Response for group recommendations."""

    user_ids: List[str]
    recommendations: List[RecommendationItemResponse]
    aggregation_strategy: str
    fairness_score: float = Field(
        ..., ge=0.0, le=1.0, description="Fairness score (0-1)"
    )
    satisfaction_distribution: Dict[str, float] = Field(
        default={}, description="Per-user satisfaction scores"
    )
    conflict_areas: List[str] = Field(
        default=[], description="Detected conflicts in preferences"
    )
    processing_steps: List[str] = Field(default=[])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_ids": ["user1", "user2", "user3"],
                    "recommendations": [],
                    "aggregation_strategy": "multiplicative",
                    "fairness_score": 0.87,
                    "satisfaction_distribution": {
                        "user1": 0.85,
                        "user2": 0.90,
                        "user3": 0.86,
                    },
                    "conflict_areas": [
                        "User user1 likes Horror but User user2 dislikes it"
                    ],
                }
            ]
        }
    }


class OnboardingResponse(BaseModel):
    """Response for onboarding request."""

    user_id: str
    profile_created: bool
    initial_recommendations: List[RecommendationItemResponse]
    message: str = Field(..., description="Success or error message")


class FeedbackResponse(BaseModel):
    """Response for feedback submission."""

    user_id: str
    movie_id: str
    rating: float
    profile_updated: bool
    message: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status: healthy, degraded, unhealthy")
    version: str = Field(default="1.0.0")
    agents_loaded: bool = Field(..., description="Whether agents are initialized")
    vectordb_connected: bool = Field(..., description="Whether vector DB is accessible")
    details: Optional[Dict[str, Any]] = Field(default=None)


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")


class LetterboxdImportResponse(BaseModel):
    """Response for Letterboxd import."""

    user_id: str
    total_movies: int = Field(..., description="Total movies found in CSV")
    imported_count: int = Field(..., description="Successfully imported ratings")
    failed_count: int = Field(..., description="Failed to import (not found in TMDB)")
    success_rate: float = Field(..., description="Import success rate (0-1)")
    message: str
