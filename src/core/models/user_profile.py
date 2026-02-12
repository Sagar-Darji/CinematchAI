"""User profile data models."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TemporalPattern(BaseModel):
    """User's temporal viewing patterns."""

    weekend_preference: Optional[str] = Field(None, description="Preferred genre on weekends")
    weekday_preference: Optional[str] = Field(None, description="Preferred genre on weekdays")
    evening_preference: Optional[str] = Field(None, description="Preferred genre in evenings")
    morning_preference: Optional[str] = Field(None, description="Preferred genre in mornings")

    peak_viewing_time: Optional[str] = Field(None, description="Most active viewing time")
    peak_viewing_day: Optional[str] = Field(None, description="Most active viewing day")

    seasonal_preferences: Dict[str, str] = Field(
        default_factory=dict, description="Genre preferences by season"
    )


class UserPreferences(BaseModel):
    """User's content preferences."""

    favorite_genres: List[str] = Field(default_factory=list, description="Top genres")
    disliked_genres: List[str] = Field(default_factory=list, description="Avoided genres")

    favorite_directors: List[str] = Field(default_factory=list, description="Favorite directors")
    favorite_actors: List[str] = Field(default_factory=list, description="Favorite actors")

    preferred_decades: List[int] = Field(default_factory=list, description="Preferred decades")
    preferred_runtime_range: Optional[tuple[int, int]] = Field(
        None, description="Preferred runtime range (min, max)"
    )

    min_rating: Optional[float] = Field(None, description="Minimum acceptable rating")

    # Computed preferences
    exploration_rate: float = Field(
        default=0.3, description="Openness to new/different content (0-1)"
    )
    nostalgia_tendency: float = Field(
        default=0.5, description="Preference for older movies (0-1)"
    )
    risk_tolerance: float = Field(
        default=0.5, description="Willingness to try low-rated but interesting movies (0-1)"
    )


class UserProfile(BaseModel):
    """Complete user profile."""

    user_id: str = Field(..., description="Unique user identifier")

    # Preferences
    preferences: UserPreferences = Field(
        default_factory=UserPreferences, description="User preferences"
    )

    # Temporal patterns
    temporal_patterns: TemporalPattern = Field(
        default_factory=TemporalPattern, description="Temporal viewing patterns"
    )

    # Embeddings
    profile_embedding: Optional[List[float]] = Field(
        None, description="Aggregated user profile embedding"
    )

    # Viewing history stats
    total_ratings: int = Field(default=0, description="Total number of ratings")
    avg_rating_given: Optional[float] = Field(None, description="Average rating given by user")
    rating_variance: Optional[float] = Field(
        None, description="Variance in ratings (pickiness indicator)"
    )

    # Recently watched (for preference drift detection)
    recent_movie_ids: List[str] = Field(
        default_factory=list, description="Recently watched movie IDs"
    )
    recent_ratings: List[float] = Field(default_factory=list, description="Recent ratings")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, description="Profile creation time")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update time")

    # Cold-start indicator
    is_cold_start: bool = Field(default=True, description="Whether user is new (< 10 ratings)")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def update_cold_start_status(self) -> None:
        """Update cold-start status based on total ratings."""
        self.is_cold_start = self.total_ratings < 10
