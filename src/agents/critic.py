"""Adversarial Critic Agent - Validates recommendations by attempting to falsify them."""

from typing import Any, Dict, List, Tuple

from src.agents.base_agent import BaseAgent
from src.core.models import Movie
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Minimum quality: vote_avg threshold + minimum vote count to trust the signal
_QUALITY_FLOOR = 5.5
_QUALITY_MIN_VOTES = 200

# A movie needs to fail this many checks before being demoted
_FAIL_THRESHOLD = 2


class AdversarialCriticAgent(BaseAgent):
    """Agent that tries to falsify each top recommendation and removes weak ones."""

    def __init__(self):
        super().__init__(
            name="Adversarial Critic",
            description="Validates and stress-tests each recommendation; removes poor fits",
            temperature=0.2,
            use_fast_model=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry
    # ─────────────────────────────────────────────────────────────────────────

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self.log_processing("Adversarial critique of top candidates")

        candidates = state.get("diverse_candidates", [])
        if not candidates:
            return state

        user_profile = state.get("user_profile")

        # Run 4 algorithmic checks on every candidate
        verdicts: Dict[str, str] = {}
        flagged: List[Tuple[int, Movie, List[str]]] = []

        for rank, movie in enumerate(candidates):
            fails = self._run_checks(movie, user_profile, candidates)
            mid = str(movie.metadata.tmdb_id)
            if fails:
                flagged.append((rank, movie, fails))
                verdicts[mid] = f"flagged:{'; '.join(fails)}"
            else:
                verdicts[mid] = "pass"

        # Demote movies that failed >= FAIL_THRESHOLD checks
        demote_ids = {
            str(movie.metadata.tmdb_id)
            for _, movie, fails in flagged
            if len(fails) >= _FAIL_THRESHOLD
        }

        passing = [m for m in candidates if str(m.metadata.tmdb_id) not in demote_ids]
        demoted = [m for m in candidates if str(m.metadata.tmdb_id) in demote_ids]

        min_keep = max(5, len(candidates) // 2)
        if len(passing) < min_keep:
            logger.warning(
                f"Critic: only {len(passing)} passing movies — keeping demoted at back"
            )

        filtered = passing + demoted  # demoted always pushed to back

        demote_count = len(demote_ids)
        if demote_count:
            logger.info(
                f"Critic: demoted {demote_count} movies "
                f"({[m.metadata.title for m in demoted]})"
            )

        state["diverse_candidates"] = filtered
        state["critic_verdicts"] = verdicts
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Adversarial Critic: {len(candidates)} checked, {demote_count} demoted"
        ]
        return state

    # ─────────────────────────────────────────────────────────────────────────
    # Algorithmic checks
    # ─────────────────────────────────────────────────────────────────────────

    def _run_checks(
        self,
        movie: Movie,
        user_profile,
        all_candidates: List[Movie],
    ) -> List[str]:
        """Return list of failure reasons (empty = pass)."""
        fails: List[str] = []
        fails += self._check_quality(movie)
        fails += self._check_genre_mismatch(movie, user_profile)
        fails += self._check_disliked_creator(movie, user_profile)
        fails += self._check_filter_bubble(movie, all_candidates)
        return fails

    def _check_quality(self, movie: Movie) -> List[str]:
        """Flag movies with poor vote average when vote count is reliable."""
        vote_avg = movie.metadata.vote_average or 0.0
        vote_count = movie.metadata.vote_count or 0
        if vote_count >= _QUALITY_MIN_VOTES and vote_avg < _QUALITY_FLOOR:
            return [f"low_quality({vote_avg:.1f}/10 from {vote_count} votes)"]
        return []

    def _check_genre_mismatch(self, movie: Movie, user_profile) -> List[str]:
        """Flag when movie genres are entirely on the user's disliked list."""
        if not user_profile or not hasattr(user_profile, "preferences"):
            return []
        if getattr(user_profile, "is_cold_start", True):
            return []

        total_ratings = getattr(user_profile, "total_ratings", 0)
        if total_ratings < 15:
            return []

        fav_genres = set(user_profile.preferences.favorite_genres[:5] or [])
        disliked = set(user_profile.preferences.disliked_genres or [])
        movie_genres = set(movie.metadata.genres or [])

        if not fav_genres or not movie_genres:
            return []

        if movie_genres and movie_genres.issubset(disliked):
            return [f"all_genres_disliked({', '.join(movie_genres)})"]

        # Only flag zero-overlap for very experienced users (50+ ratings)
        if total_ratings >= 50 and not (fav_genres & movie_genres):
            return [
                f"genre_mismatch("
                f"user:{','.join(list(fav_genres)[:3])} "
                f"vs movie:{','.join(list(movie_genres)[:3])})"
            ]

        return []

    def _check_disliked_creator(self, movie: Movie, user_profile) -> List[str]:
        """Flag if movie's director is on the user's disliked directors list."""
        if not user_profile or not hasattr(user_profile, "preferences"):
            return []
        disliked_directors = getattr(user_profile.preferences, "disliked_directors", [])
        if not disliked_directors:
            return []
        movie_director = movie.metadata.director or ""
        if movie_director and movie_director in disliked_directors:
            return [f"disliked_director({movie_director})"]
        return []

    def _check_filter_bubble(
        self,
        movie: Movie,
        all_candidates: List[Movie],
    ) -> List[str]:
        """Flag movies ranked 4th/5th in top-5 when all 5 share the same primary genre."""
        top5 = all_candidates[:5]
        if movie not in top5:
            return []

        movie_genres = set(movie.metadata.genres or [])
        primary_genre = next(iter(movie_genres), None)
        if not primary_genre:
            return []

        same_genre_count = sum(
            1 for m in top5
            if m != movie and primary_genre in set(m.metadata.genres or [])
        )

        if same_genre_count >= 3:
            idx = all_candidates.index(movie)
            if idx >= 3:
                return [f"filter_bubble({primary_genre} in {same_genre_count+1}/5 of top-5)"]

        return []


def get_critic_agent() -> AdversarialCriticAgent:
    """Get configured Adversarial Critic agent."""
    return AdversarialCriticAgent()
