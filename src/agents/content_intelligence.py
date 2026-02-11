"""Content Intelligence Agent - Deep movie content analysis."""

import json
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import get_settings
from src.agents.base_agent import BaseAgent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ContentIntelligenceAgent(BaseAgent):
    """Agent that performs deep content analysis of movies."""

    def __init__(self):
        """Initialize Content Intelligence agent."""
        super().__init__(
            name="Content Intelligence",
            description="Deep movie content analysis and micro-genre extraction",
            temperature=0.5,  # Moderate creativity for content analysis
            use_fast_model=False,  # Use main model for better analysis
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze movie content features.

        Args:
            state: Current state with candidate_movies or movie data.

        Returns:
            Updated state with content_features.
        """
        self.log_processing("Starting content analysis")

        # Get movies to analyze
        candidate_movies = state.get("candidate_movies", [])

        if not candidate_movies:
            # If no candidates yet, analyze based on user profile
            self.log_processing("No candidate movies yet, skipping content analysis")
            state["content_features"] = {}
            return state

        # Analyze content for candidates
        content_features = {}

        for movie in candidate_movies[:10]:  # Analyze top 10 candidates
            movie_id = str(movie.metadata.tmdb_id)
            features = self._analyze_movie_content(movie)
            content_features[movie_id] = features

        state["content_features"] = content_features
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Content Intelligence: Analyzed {len(content_features)} movies"
        ]

        return state

    def _analyze_movie_content(self, movie) -> Dict[str, Any]:
        """
        Perform deep content analysis on a single movie.

        Args:
            movie: Movie object.

        Returns:
            Content features dictionary.
        """
        metadata = movie.metadata

        # Extract basic features
        features = {
            "title": metadata.title,
            "genres": metadata.genres,
            "themes": self._extract_themes(metadata),
            "micro_genres": self._extract_micro_genres(metadata),
            "tone": self._analyze_tone(metadata),
            "pacing": self._estimate_pacing(metadata),
            "complexity": self._estimate_complexity(metadata),
        }

        return features

    def _extract_themes(self, metadata) -> List[str]:
        """
        Extract thematic elements from movie.

        Args:
            metadata: Movie metadata.

        Returns:
            List of themes.
        """
        themes = []

        # Use LLM for theme extraction from overview
        if metadata.overview:
            prompt = f"""Analyze this movie plot and extract 3-5 core themes.

Movie: {metadata.title}
Plot: {metadata.overview}

Themes should be single words or short phrases like: "redemption", "coming-of-age", "revenge", "family bonds", etc.

Return only the themes as a comma-separated list."""

            try:
                response = self.generate_response(
                    prompt=prompt,
                    system_prompt="You are a film analyst expert at identifying themes.",
                    max_tokens=100,
                )

                # Parse response
                themes = [t.strip() for t in response.split(",") if t.strip()]

            except Exception as e:
                logger.warning(f"Failed to extract themes via LLM: {e}")
                # Fallback to genre-based themes
                themes = self._genre_to_themes(metadata.genres)

        return themes[:5]  # Limit to 5

    def _extract_micro_genres(self, metadata) -> List[str]:
        """
        Extract micro-genres (specific sub-categories).

        Args:
            metadata: Movie metadata.

        Returns:
            List of micro-genres.
        """
        micro_genres = []

        # Combine genres with themes for micro-genre creation
        if metadata.overview and metadata.genres:
            prompt = f"""Create 2-3 specific micro-genres for this movie.

Movie: {metadata.title}
Genres: {', '.join(metadata.genres)}
Plot: {metadata.overview[:300]}

Micro-genres should be creative combinations like:
- "heist-with-twist"
- "slow-burn-thriller"
- "female-led-action"
- "cerebral-sci-fi"
- "dark-comedy-crime"

Return only the micro-genres as a comma-separated list."""

            try:
                response = self.generate_response(
                    prompt=prompt,
                    system_prompt="You are a creative film cataloger.",
                    max_tokens=80,
                )

                micro_genres = [mg.strip() for mg in response.split(",") if mg.strip()]

            except Exception as e:
                logger.warning(f"Failed to extract micro-genres via LLM: {e}")
                # Fallback to genre combinations
                micro_genres = self._combine_genres(metadata.genres)

        return micro_genres[:3]

    def _analyze_tone(self, metadata) -> str:
        """
        Analyze overall tone of the movie.

        Args:
            metadata: Movie metadata.

        Returns:
            Tone description (light, dark, whimsical, serious, etc.).
        """
        # Simple heuristic based on genres
        genres = [g.lower() for g in metadata.genres]

        if "comedy" in genres:
            return "light"
        elif "horror" in genres or "thriller" in genres:
            return "dark"
        elif "drama" in genres:
            return "serious"
        elif "animation" in genres or "family" in genres:
            return "whimsical"
        elif "action" in genres:
            return "intense"
        else:
            return "balanced"

    def _estimate_pacing(self, metadata) -> str:
        """
        Estimate pacing of the movie.

        Args:
            metadata: Movie metadata.

        Returns:
            Pacing category (fast, moderate, slow).
        """
        genres = [g.lower() for g in metadata.genres]

        # Fast pacing
        if any(g in genres for g in ["action", "thriller", "horror"]):
            return "fast"

        # Slow pacing
        elif any(g in genres for g in ["drama", "documentary"]):
            return "slow"

        # Moderate
        else:
            return "moderate"

    def _estimate_complexity(self, metadata) -> str:
        """
        Estimate narrative complexity.

        Args:
            metadata: Movie metadata.

        Returns:
            Complexity level (simple, moderate, complex).
        """
        genres = [g.lower() for g in metadata.genres]

        # Complex
        if any(g in genres for g in ["mystery", "thriller", "science fiction"]):
            return "complex"

        # Simple
        elif any(g in genres for g in ["comedy", "family", "animation"]):
            return "simple"

        # Moderate
        else:
            return "moderate"

    def _genre_to_themes(self, genres: List[str]) -> List[str]:
        """Map genres to common themes (fallback)."""
        theme_map = {
            "Action": ["heroism", "conflict"],
            "Drama": ["human-nature", "relationships"],
            "Comedy": ["humor", "satire"],
            "Horror": ["fear", "survival"],
            "Romance": ["love", "relationships"],
            "Science Fiction": ["technology", "future"],
            "Thriller": ["suspense", "mystery"],
        }

        themes = []
        for genre in genres:
            if genre in theme_map:
                themes.extend(theme_map[genre])

        return list(set(themes))

    def _combine_genres(self, genres: List[str]) -> List[str]:
        """Combine genres into micro-genres (fallback)."""
        if len(genres) >= 2:
            return [f"{genres[0].lower()}-{genres[1].lower()}"]
        elif len(genres) == 1:
            return [f"{genres[0].lower()}-film"]
        return []


def get_content_intelligence_agent() -> ContentIntelligenceAgent:
    """Get configured Content Intelligence agent."""
    return ContentIntelligenceAgent()
