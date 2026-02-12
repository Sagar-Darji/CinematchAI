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

    # Mood-to-tone mapping: which tones fit which moods
    MOOD_TONE_AFFINITY = {
        "happy": {"light": 1.0, "whimsical": 0.8, "balanced": 0.4, "intense": 0.2, "serious": 0.1, "dark": 0.0},
        "sad": {"serious": 0.8, "balanced": 0.6, "light": 0.5, "whimsical": 0.4, "dark": 0.3, "intense": 0.2},
        "stressed": {"light": 0.9, "whimsical": 0.8, "balanced": 0.5, "serious": 0.2, "intense": 0.0, "dark": 0.0},
        "bored": {"intense": 0.9, "dark": 0.7, "balanced": 0.5, "serious": 0.4, "light": 0.3, "whimsical": 0.3},
        "thoughtful": {"serious": 0.9, "dark": 0.7, "balanced": 0.6, "intense": 0.4, "light": 0.2, "whimsical": 0.2},
        "energetic": {"intense": 0.9, "light": 0.6, "balanced": 0.5, "dark": 0.4, "whimsical": 0.3, "serious": 0.2},
        "nostalgic": {"balanced": 0.8, "light": 0.7, "serious": 0.6, "whimsical": 0.6, "dark": 0.3, "intense": 0.3},
        "adventurous": {"intense": 0.8, "balanced": 0.7, "dark": 0.6, "whimsical": 0.5, "light": 0.4, "serious": 0.3},
    }

    # Genres that are NOT family-friendly
    NON_FAMILY_GENRES = {"horror", "thriller", "crime", "war"}

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze movie content features, then score and rerank candidates.

        Args:
            state: Current state with candidate_movies or movie data.

        Returns:
            Updated state with content_features and reranked candidate_movies.
        """
        self.log_processing("Starting content analysis")

        candidate_movies = state.get("candidate_movies", [])

        if not candidate_movies:
            self.log_processing("No candidate movies yet, skipping content analysis")
            state["content_features"] = {}
            return state

        # Run cheap heuristic analysis (tone/pacing/complexity) for ALL candidates,
        # and deep LLM analysis (themes/micro-genres) for top 10 only.
        content_features = {}

        for i, movie in enumerate(candidate_movies):
            movie_id = str(movie.metadata.tmdb_id)
            if i < 10:
                features = self._analyze_movie_content(movie)
            else:
                features = self._analyze_movie_content_fast(movie)
            content_features[movie_id] = features

        state["content_features"] = content_features

        # Score and rerank candidates using preferences + context
        user_profile = state.get("user_profile")
        context_factors = state.get("context_factors", {})
        context = state.get("context", {})

        scored_movies = self._score_and_rerank(
            candidate_movies, content_features, user_profile, context_factors, context
        )

        original_count = len(candidate_movies)
        state["candidate_movies"] = scored_movies
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Content Intelligence: Analyzed {len(content_features)} movies, "
            f"reranked to {len(scored_movies)} (from {original_count})"
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

    def _analyze_movie_content_fast(self, movie) -> Dict[str, Any]:
        """
        Fast content analysis using only heuristics (no LLM calls).

        Args:
            movie: Movie object.

        Returns:
            Content features dictionary.
        """
        metadata = movie.metadata

        features = {
            "title": metadata.title,
            "genres": metadata.genres,
            "themes": self._genre_to_themes(metadata.genres),
            "micro_genres": self._combine_genres(metadata.genres),
            "tone": self._analyze_tone(metadata),
            "pacing": self._estimate_pacing(metadata),
            "complexity": self._estimate_complexity(metadata),
        }

        return features

    def _score_and_rerank(
        self,
        candidates: List,
        content_features: Dict[str, Dict],
        user_profile,
        context_factors: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List:
        """
        Score candidates by relevance and filter out mismatches.

        Args:
            candidates: List of Movie objects.
            content_features: Analyzed features per movie_id.
            user_profile: User profile (may be None for cold-start).
            context_factors: Detected context (mood, companion, etc.).
            context: Raw user context (language, year_min, year_max, NL context).

        Returns:
            Reranked and filtered list of Movie objects.
        """
        mood = context_factors.get("mood")
        companion = context_factors.get("companion", "alone")
        nl_context = (
            context.get("natural_language_context", "")
            or context_factors.get("natural_language_context", "")
            or ""
        ).lower()
        year_min = context.get("year_min") or context_factors.get("year_min")
        year_max = context.get("year_max") or context_factors.get("year_max")
        language = context.get("language") or context_factors.get("language")

        # Get user genre preferences
        fav_genres = set()
        disliked_genres = set()
        if user_profile and hasattr(user_profile, "preferences"):
            fav_genres = {g.lower() for g in (user_profile.preferences.favorite_genres or [])}
            disliked_genres = {g.lower() for g in (user_profile.preferences.disliked_genres or [])}

        # NL context keywords for matching against themes/micro-genres
        nl_keywords = [w for w in nl_context.split() if len(w) > 2] if nl_context else []

        scored = []
        for movie in candidates:
            movie_id = str(movie.metadata.tmdb_id)
            features = content_features.get(movie_id, {})
            movie_genres = {g.lower() for g in (features.get("genres") or movie.metadata.genres or [])}
            tone = features.get("tone", "balanced")

            # --- Hard filters: remove clearly wrong movies ---

            # Year filter enforcement (catch anything that slipped through DB filter)
            movie_year = movie.metadata.year
            if year_min and movie_year and movie_year < int(year_min):
                continue
            if year_max and movie_year and movie_year > int(year_max):
                continue

            # Language post-filter
            if language and movie.metadata.original_language:
                if movie.metadata.original_language != language:
                    continue

            # --- Soft scoring ---
            score = 0.5  # Base score

            # 1. Genre match with user preferences (±0.25)
            if fav_genres:
                genre_overlap = len(movie_genres & fav_genres)
                score += min(genre_overlap * 0.1, 0.25)
            if disliked_genres and (movie_genres & disliked_genres):
                score -= 0.2

            # 2. Tone-mood affinity (±0.15)
            if mood and mood.lower() in self.MOOD_TONE_AFFINITY:
                affinity = self.MOOD_TONE_AFFINITY[mood.lower()].get(tone, 0.4)
                score += (affinity - 0.4) * 0.3  # Range: -0.12 to +0.18

            # 3. Companion appropriateness (±0.2)
            if companion == "family":
                if movie_genres & self.NON_FAMILY_GENRES:
                    score -= 0.25  # Penalize non-family content
                if "family" in movie_genres or "animation" in movie_genres:
                    score += 0.15
            elif companion == "partner":
                if "romance" in movie_genres:
                    score += 0.1

            # 4. Natural language context keyword matching (±0.15)
            if nl_keywords:
                themes = [t.lower() for t in (features.get("themes") or [])]
                micro_genres = [mg.lower() for mg in (features.get("micro_genres") or [])]
                overview = (movie.metadata.overview or "").lower()
                searchable = " ".join(themes + micro_genres) + " " + " ".join(movie_genres) + " " + overview

                keyword_hits = sum(1 for kw in nl_keywords if kw in searchable)
                score += min(keyword_hits * 0.05, 0.15)

            scored.append((score, movie))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        reranked = [movie for _, movie in scored]

        logger.info(
            f"Content reranking: {len(candidates)} → {len(reranked)} candidates "
            f"(mood={mood}, companion={companion}, language={language})"
        )

        return reranked

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
