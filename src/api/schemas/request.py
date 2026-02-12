"""API Request Schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    """Request for single-user recommendations."""

    user_id: str = Field(..., description="User ID")
    context: Optional[Dict[str, str]] = Field(
        default=None,
        description="Context information (time_of_day, mood, companion, occasion)",
    )
    k: int = Field(default=10, ge=1, le=50, description="Number of recommendations")
    use_hybrid: bool = Field(
        default=True, description="Use hybrid (text+image) embeddings"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user123",
                    "context": {
                        "time_of_day": "evening",
                        "mood": "relaxed",
                        "companion": "alone",
                    },
                    "k": 10,
                    "use_hybrid": True,
                }
            ]
        }
    }


class GroupRecommendationRequest(BaseModel):
    """Request for group recommendations."""

    user_ids: List[str] = Field(..., min_length=2, description="List of user IDs")
    context: Optional[Dict[str, str]] = Field(
        default=None, description="Shared context information"
    )
    aggregation_strategy: str = Field(
        default="multiplicative",
        description="Aggregation strategy: multiplicative, least_misery, average",
    )
    k: int = Field(default=10, ge=1, le=50, description="Number of recommendations")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_ids": ["user1", "user2", "user3"],
                    "context": {"companion": "friends", "occasion": "movie_night"},
                    "aggregation_strategy": "multiplicative",
                    "k": 10,
                }
            ]
        }
    }


class OnboardingRequest(BaseModel):
    """Request for user onboarding (cold-start)."""

    user_id: str = Field(..., description="New user ID")
    ratings: Dict[str, float] = Field(
        ...,
        description="Initial ratings (movie_id -> rating). At least 5 ratings required.",
        min_length=5,
    )
    preferences: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Optional explicit preferences (favorite_genres, disliked_genres, etc.)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "new_user_456",
                    "ratings": {
                        "550": 5.0,  # Fight Club
                        "680": 4.5,  # Pulp Fiction
                        "13": 4.0,  # Forrest Gump
                        "155": 3.5,  # The Dark Knight
                        "278": 5.0,  # The Shawshank Redemption
                    },
                    "preferences": {
                        "favorite_genres": ["Drama", "Thriller"],
                        "disliked_genres": ["Horror"],
                    },
                }
            ]
        }
    }


class FeedbackRequest(BaseModel):
    """Request to submit user feedback (rating)."""

    user_id: str = Field(..., description="User ID")
    movie_id: str = Field(..., description="Movie TMDB ID")
    rating: float = Field(..., ge=0.5, le=5.0, description="Rating (0.5 to 5.0)")
    watched: bool = Field(default=True, description="Whether the user watched the movie")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user123",
                    "movie_id": "550",
                    "rating": 4.5,
                    "watched": True,
                }
            ]
        }
    }


class UpdateContextRequest(BaseModel):
    """Request to update user context."""

    user_id: str = Field(..., description="User ID")
    context: Dict[str, str] = Field(..., description="Updated context information")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user123",
                    "context": {
                        "time_of_day": "night",
                        "mood": "adventurous",
                        "companion": "partner",
                    },
                }
            ]
        }
    }


class LetterboxdImportRequest(BaseModel):
    """Request to import Letterboxd CSV export."""

    user_id: str = Field(..., description="User ID")
    csv_content: str = Field(..., description="Letterboxd CSV export file content")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user123",
                    "csv_content": "Date,Name,Year,Letterboxd URI,Rating\n2024-01-15,Inception,2010,https://letterboxd.com/film/inception/,4.5\n...",
                }
            ]
        }
    }
