"""Serendipity Agent - Balances exploration vs exploitation and ensures diversity."""

import random
from typing import Any, Dict, List

import numpy as np

from src.agents.base_agent import BaseAgent
from src.core.models import Movie
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SerendipityAgent(BaseAgent):
    """Agent that introduces diversity and serendipity into recommendations."""

    def __init__(self):
        """Initialize Serendipity agent."""
        super().__init__(
            name="Serendipity",
            description="Balances exploration vs exploitation, ensures diversity",
            temperature=0.7,  # Higher temperature for creative exploration
            use_fast_model=True,  # Use fast model for quick calculations
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply serendipity and diversity to candidate recommendations.

        Args:
            state: Current state with candidate_movies.

        Returns:
            Updated state with diverse_candidates and exploration_items.
        """
        self.log_processing("Applying serendipity and diversity")

        candidate_movies = state.get("candidate_movies", [])
        user_profile = state.get("user_profile")

        if not candidate_movies:
            logger.warning("No candidate movies to diversify")
            return state

        # Get exploration rate from user profile
        exploration_rate = self._get_exploration_rate(user_profile)

        # Calculate diversity
        diverse_candidates = self._apply_diversity(
            candidate_movies, exploration_rate
        )

        # Identify exploration items
        exploration_items = self._identify_exploration_items(
            diverse_candidates, user_profile
        )

        # Update state
        state["diverse_candidates"] = diverse_candidates
        state["exploration_items"] = exploration_items
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Serendipity: Applied diversity (exploration_rate={exploration_rate:.2f})"
        ]

        return state

    def _get_exploration_rate(self, user_profile) -> float:
        """
        Get exploration rate from user profile.

        Args:
            user_profile: User profile.

        Returns:
            Exploration rate (0-1).
        """
        if user_profile and hasattr(user_profile, "preferences"):
            return user_profile.preferences.exploration_rate

        # Default moderate exploration
        return 0.3

    def _apply_diversity(
        self, candidates: List[Movie], exploration_rate: float
    ) -> List[Movie]:
        """
        Apply diversity to candidate list.

        Args:
            candidates: Candidate movies.
            exploration_rate: How much to diversify (0-1).

        Returns:
            Diversified candidate list.
        """
        if len(candidates) <= 5:
            # Too few candidates to diversify
            return candidates

        # Split into safe (exploitation) and exploratory
        num_exploration = int(len(candidates) * exploration_rate)
        num_safe = len(candidates) - num_exploration

        # Safe picks: highest scoring candidates
        safe_picks = candidates[:num_safe]

        # Exploratory picks: diverse from later candidates
        exploratory_pool = candidates[num_safe:]
        exploratory_picks = self._select_diverse_items(
            exploratory_pool, num_exploration
        )

        # Combine and shuffle slightly
        all_picks = safe_picks + exploratory_picks

        return all_picks

    def _select_diverse_items(
        self, candidates: List[Movie], num_items: int
    ) -> List[Movie]:
        """
        Select diverse items using genre and year diversity.

        Args:
            candidates: Candidate pool.
            num_items: Number to select.

        Returns:
            Diverse selection.
        """
        if not candidates or num_items == 0:
            return []

        selected = []
        remaining = candidates.copy()

        # Start with a random pick
        if remaining:
            selected.append(remaining.pop(random.randint(0, len(remaining) - 1)))

        # Greedily select most diverse items
        while len(selected) < num_items and remaining:
            # Calculate diversity score for each remaining item
            diversity_scores = []

            for candidate in remaining:
                score = self._calculate_diversity_score(candidate, selected)
                diversity_scores.append(score)

            # Select most diverse
            max_idx = np.argmax(diversity_scores)
            selected.append(remaining.pop(max_idx))

        return selected

    def _calculate_diversity_score(
        self, candidate: Movie, selected: List[Movie]
    ) -> float:
        """
        Calculate how diverse a candidate is from selected items.

        Args:
            candidate: Candidate movie.
            selected: Already selected movies.

        Returns:
            Diversity score (higher = more diverse).
        """
        if not selected:
            return 1.0

        diversity_score = 0.0

        # Genre diversity
        candidate_genres = set(candidate.metadata.genres or [])

        for movie in selected:
            movie_genres = set(movie.metadata.genres or [])

            # Jaccard distance (1 - Jaccard similarity)
            if candidate_genres or movie_genres:
                intersection = len(candidate_genres & movie_genres)
                union = len(candidate_genres | movie_genres)
                genre_distance = 1 - (intersection / union if union > 0 else 0)
            else:
                genre_distance = 0.5

            diversity_score += genre_distance

        # Year diversity
        candidate_year = candidate.metadata.year or 2000

        for movie in selected:
            movie_year = movie.metadata.year or 2000
            year_diff = abs(candidate_year - movie_year)
            # Normalize to 0-1 (50 years = max diversity)
            year_diversity = min(year_diff / 50.0, 1.0)
            diversity_score += year_diversity

        # Average diversity
        diversity_score /= len(selected) * 2  # Divided by 2 factors

        return diversity_score

    def _identify_exploration_items(
        self, candidates: List[Movie], user_profile
    ) -> List[Movie]:
        """
        Identify which items are exploratory recommendations.

        Args:
            candidates: Candidate movies.
            user_profile: User profile.

        Returns:
            List of exploratory items.
        """
        if not user_profile or not hasattr(user_profile, "preferences"):
            return []

        exploration_items = []
        favorite_genres = set(user_profile.preferences.favorite_genres or [])

        for movie in candidates:
            movie_genres = set(movie.metadata.genres or [])

            # Check if movie is outside user's typical genres
            genre_overlap = len(favorite_genres & movie_genres)

            if genre_overlap == 0 and favorite_genres:
                # Completely new genre territory
                exploration_items.append(movie)
            elif len(movie_genres) > 0 and genre_overlap / len(movie_genres) < 0.3:
                # Mostly different genres
                exploration_items.append(movie)

        return exploration_items

    def calculate_intra_list_diversity(self, movies: List[Movie]) -> float:
        """
        Calculate intra-list diversity score.

        Args:
            movies: List of movies.

        Returns:
            Diversity score (0-1).
        """
        if len(movies) < 2:
            return 0.0

        total_diversity = 0.0
        comparisons = 0

        for i, movie1 in enumerate(movies):
            for movie2 in movies[i + 1 :]:
                diversity = self._calculate_diversity_score(movie2, [movie1])
                total_diversity += diversity
                comparisons += 1

        return total_diversity / comparisons if comparisons > 0 else 0.0


def get_serendipity_agent() -> SerendipityAgent:
    """Get configured Serendipity agent."""
    return SerendipityAgent()
