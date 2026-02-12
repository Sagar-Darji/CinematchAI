"""Movie data models."""

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MovieMetadata(BaseModel):
    """Movie metadata from TMDB."""

    tmdb_id: str = Field(..., description="TMDB movie ID")
    imdb_id: Optional[str] = Field(None, description="IMDB movie ID")
    title: str = Field(..., description="Movie title")
    original_title: Optional[str] = Field(None, description="Original title")
    overview: Optional[str] = Field(None, description="Plot overview")
    tagline: Optional[str] = Field(None, description="Movie tagline")

    release_date: Optional[date] = Field(None, description="Release date")
    year: Optional[int] = Field(None, description="Release year")

    genres: List[str] = Field(default_factory=list, description="Genre list")
    runtime: Optional[int] = Field(None, description="Runtime in minutes")

    # Cast and crew
    director: Optional[str] = Field(None, description="Director name")
    cast: List[str] = Field(default_factory=list, description="Main cast members")

    # Ratings
    vote_average: Optional[float] = Field(None, description="Average rating (0-10)")
    vote_count: Optional[int] = Field(None, description="Number of votes")
    popularity: Optional[float] = Field(None, description="Popularity score")

    # Media
    poster_path: Optional[str] = Field(None, description="Path to poster image")
    backdrop_path: Optional[str] = Field(None, description="Path to backdrop image")

    # Language
    original_language: Optional[str] = Field(None, description="Original language code")
    spoken_languages: List[str] = Field(default_factory=list, description="Spoken languages")

    # Additional metadata
    budget: Optional[int] = Field(None, description="Production budget")
    revenue: Optional[int] = Field(None, description="Box office revenue")
    status: Optional[str] = Field(None, description="Release status")


class Movie(BaseModel):
    """Complete movie representation with embeddings and enrichments."""

    movie_id: str = Field(..., description="Internal movie ID (MovieLens ID)")
    metadata: MovieMetadata = Field(..., description="TMDB metadata")

    # Embeddings
    text_embedding: Optional[List[float]] = Field(None, description="Text embedding vector")
    image_embedding: Optional[List[float]] = Field(None, description="Image embedding vector")
    hybrid_embedding: Optional[List[float]] = Field(None, description="Hybrid embedding vector")

    # Enriched content
    micro_genres: List[str] = Field(default_factory=list, description="Extracted micro-genres")
    themes: List[str] = Field(default_factory=list, description="Extracted themes")
    mood: Optional[str] = Field(None, description="Overall mood/tone")
    sentiment_score: Optional[float] = Field(
        None, description="Sentiment score from reviews (-1 to 1)"
    )

    # Statistics from MovieLens
    avg_rating: Optional[float] = Field(None, description="Average MovieLens rating")
    rating_count: Optional[int] = Field(None, description="Number of MovieLens ratings")
    tags: List[str] = Field(default_factory=list, description="User-generated tags")

    # Computed features
    popularity_rank: Optional[int] = Field(None, description="Popularity ranking")
    controversy_score: Optional[float] = Field(
        None, description="Rating variance (0-1, higher = more controversial)"
    )

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class MovieContext(BaseModel):
    """Context information for movie selection."""

    time_of_day: Optional[str] = Field(None, description="Time of day (morning, afternoon, evening, night)")
    day_of_week: Optional[str] = Field(None, description="Day of week")
    season: Optional[str] = Field(None, description="Season (spring, summer, fall, winter)")
    weather: Optional[str] = Field(None, description="Weather condition")
    companion: Optional[str] = Field(
        None, description="Viewing companion (alone, partner, family, friends)"
    )
    mood: Optional[str] = Field(None, description="User's current mood")
    occasion: Optional[str] = Field(None, description="Special occasion")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
