"""Serendipity Agent - Balances exploration vs exploitation and ensures diversity."""

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
        """Apply MMR (Maximal Marginal Relevance) diversity to candidates.

        MMR balances relevance and diversity:
            score(i) = λ * sim(i, query) − (1−λ) * max_sim(i, selected)

        λ = 1 - exploration_rate (higher exploration = more diversity weight).

        Args:
            candidates: Candidate movies ranked by relevance (best first).
            exploration_rate: How much to diversify (0–0.35).

        Returns:
            Re-ranked list with MMR diversity applied.
        """
        if len(candidates) <= 5:
            return candidates

        # λ controls relevance vs diversity trade-off
        # exploration_rate 0.35 → λ=0.65 (35% diversity weight)
        lam = 1.0 - exploration_rate

        selected: List[Movie] = []
        remaining = list(enumerate(candidates))  # (original_rank, movie)

        while remaining:
            best_idx = None
            best_score = float("-inf")

            for pool_idx, (orig_rank, movie) in enumerate(remaining):
                # Relevance: inversely proportional to original rank (rank 0 = best)
                relevance = 1.0 / (1.0 + orig_rank)

                # Redundancy: max similarity to already-selected movies
                if selected:
                    max_sim = max(
                        self._movie_similarity(movie, sel) for sel in selected
                    )
                else:
                    max_sim = 0.0

                mmr_score = lam * relevance - (1.0 - lam) * max_sim

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = pool_idx

            _, movie = remaining.pop(best_idx)
            selected.append(movie)

        return selected

    def _movie_similarity(self, a: Movie, b: Movie) -> float:
        """Estimate similarity between two movies via genre Jaccard + year proximity."""
        genres_a = set(a.metadata.genres or [])
        genres_b = set(b.metadata.genres or [])
        if genres_a or genres_b:
            union = len(genres_a | genres_b)
            intersection = len(genres_a & genres_b)
            genre_sim = intersection / union if union > 0 else 0.0
        else:
            genre_sim = 0.5

        year_a = a.metadata.year or 2000
        year_b = b.metadata.year or 2000
        year_sim = max(0.0, 1.0 - abs(year_a - year_b) / 50.0)

        return 0.6 * genre_sim + 0.4 * year_sim

    def _calculate_diversity_score(
        self, candidate: Movie, selected: List[Movie]
    ) -> float:
        """Calculate how diverse a candidate is from a list (1 - avg similarity)."""
        if not selected:
            return 1.0
        avg_sim = sum(self._movie_similarity(candidate, m) for m in selected) / len(selected)
        return 1.0 - avg_sim

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
