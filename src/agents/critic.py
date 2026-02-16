"""Adversarial Critic Agent - Validates recommendations by attempting to falsify them."""

import re
from typing import Any, Dict, List, Optional, Tuple

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
            use_fast_model=True,  # fast 8B for quick verdicts
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

        # Score each candidate with up to 4 algorithmic checks
        verdicts: Dict[str, str] = {}
        flagged: List[Tuple[int, Movie, List[str]]] = []   # (original_rank, movie, reasons)

        for rank, movie in enumerate(candidates):
            fails = self._run_checks(movie, user_profile, candidates)
            mid = str(movie.metadata.tmdb_id)
            if fails:
                flagged.append((rank, movie, fails))
                verdicts[mid] = f"flagged:{'; '.join(fails)}"
            else:
                verdicts[mid] = "pass"

        # For borderline movies (exactly 1 flag) try an LLM double-check
        # Only do this for the top-10 candidates to keep latency low
        if user_profile and self._llm_available():
            for rank, movie, fails in flagged:
                if rank < 10 and len(fails) == 1:
                    mid = str(movie.metadata.tmdb_id)
                    llm_verdict = self._llm_verify(movie, user_profile, fails[0])
                    if llm_verdict == "pass":
                        verdicts[mid] = "pass"
                        flagged[flagged.index((rank, movie, fails))] = (rank, movie, [])
                        logger.info(f"Critic: LLM overrode flag for '{movie.metadata.title}'")
                    else:
                        verdicts[mid] = f"flagged:{fails[0]}|llm_confirmed"

        # Build hard-fail set: movies that failed >= FAIL_THRESHOLD checks
        demote_ids = {
            str(movie.metadata.tmdb_id)
            for _, movie, fails in flagged
            if len(fails) >= _FAIL_THRESHOLD
        }

        # Separate passing and demoted movies; keep original order within each group
        passing = [m for m in candidates if str(m.metadata.tmdb_id) not in demote_ids]
        demoted = [m for m in candidates if str(m.metadata.tmdb_id) in demote_ids]

        # Only remove if we still have enough passing movies
        min_keep = max(5, len(candidates) // 2)
        if len(passing) >= min_keep:
            filtered = passing + demoted  # demoted pushed to back
        else:
            # Not enough passing → keep all, just reorder
            filtered = passing + demoted
            logger.warning(
                f"Critic: only {len(passing)} passing movies — keeping demoted at back"
            )

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
    # Algorithmic checks (no LLM needed)
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
        fails += self._check_filter_bubble(movie, all_candidates, user_profile)

        return fails

    def _check_quality(self, movie: Movie) -> List[str]:
        """Flag movies with poor vote average (only when vote count is reliable)."""
        vote_avg = movie.metadata.vote_average or 0.0
        vote_count = movie.metadata.vote_count or 0

        if vote_count >= _QUALITY_MIN_VOTES and vote_avg < _QUALITY_FLOOR:
            return [f"low_quality({vote_avg:.1f}/10 from {vote_count} votes)"]
        return []

    def _check_genre_mismatch(self, movie: Movie, user_profile) -> List[str]:
        """Flag when movie has zero overlap with user's top genres (experienced users only)."""
        if not user_profile or not hasattr(user_profile, "preferences"):
            return []
        if getattr(user_profile, "is_cold_start", True):
            return []

        total_ratings = getattr(user_profile, "total_ratings", 0)
        if total_ratings < 15:  # need enough history to trust genre preference
            return []

        fav_genres = set(user_profile.preferences.favorite_genres[:5] or [])
        disliked = set(user_profile.preferences.disliked_genres or [])
        movie_genres = set(movie.metadata.genres or [])

        if not fav_genres or not movie_genres:
            return []

        # Fail if: no overlap with top genres AND all movie genres are in disliked
        all_disliked = movie_genres and movie_genres.issubset(disliked)
        if all_disliked:
            return [f"all_genres_disliked({', '.join(movie_genres)})"]

        # Fail if: zero overlap with top-5 fav genres AND movie is not exploration
        # Only flag if user is very experienced (50+ ratings) to be conservative
        if total_ratings >= 50 and not (fav_genres & movie_genres):
            return [f"genre_mismatch(user:{','.join(list(fav_genres)[:3])} vs movie:{','.join(list(movie_genres)[:3])})"]

        return []

    def _check_disliked_creator(self, movie: Movie, user_profile) -> List[str]:
        """Flag if movie's director/cast overlaps with directors the user consistently rates low."""
        if not user_profile or not hasattr(user_profile, "preferences"):
            return []

        # We need access to user ratings to detect disliked creators.
        # Use the pattern: if a director appears in disliked_genres equivalent for directors.
        # Currently we don't store disliked_directors — skip this check gracefully.
        # This check becomes active once disliked_directors is populated.
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
        user_profile,
    ) -> List[str]:
        """Flag if the top-5 is overly homogeneous and this movie contributes to that."""
        top5 = all_candidates[:5]
        if movie not in top5:
            return []  # only check top-5 for bubble

        movie_genres = set(movie.metadata.genres or [])
        if not movie_genres:
            return []

        # Count how many of the top-5 share the primary genre
        primary_genre = next(iter(movie_genres), None)
        if not primary_genre:
            return []

        same_genre_count = sum(
            1 for m in top5
            if m != movie and primary_genre in set(m.metadata.genres or [])
        )

        # If 4 out of 5 movies share the same primary genre, flag one
        if same_genre_count >= 3:
            # Only flag movies ranked 4th or 5th in top-5 (preserve the best matches)
            idx = all_candidates.index(movie)
            if idx >= 3:
                return [f"filter_bubble({primary_genre} in {same_genre_count+1}/5 of top-5)"]

        return []

    # ─────────────────────────────────────────────────────────────────────────
    # LLM verification (borderline cases only)
    # ─────────────────────────────────────────────────────────────────────────

    def _llm_available(self) -> bool:
        """Check if LLM is configured for verification calls."""
        try:
            from config.settings import get_settings
            s = get_settings()
            return bool(s.groq_api_key)
        except Exception:
            return False

    def _llm_verify(self, movie: Movie, user_profile, flag_reason: str) -> str:
        """Quick LLM double-check for a borderline movie. Returns 'pass' or 'fail'."""
        fav_genres = getattr(user_profile.preferences, "favorite_genres", [])[:4]
        fav_directors = getattr(user_profile.preferences, "favorite_directors", [])[:3]
        fav_actors = getattr(user_profile.preferences, "favorite_actors", [])[:3]

        movie_genres = movie.metadata.genres or []
        movie_title = movie.metadata.title or "Unknown"
        movie_year = movie.metadata.year or "?"
        vote_avg = movie.metadata.vote_average or 0.0

        prompt = (
            f"User profile: favorite genres={fav_genres}, "
            f"directors={fav_directors}, actors={fav_actors}.\n"
            f"Flagged recommendation: '{movie_title}' ({movie_year}), "
            f"genres={movie_genres}, rating={vote_avg:.1f}/10.\n"
            f"Flag reason: {flag_reason}\n\n"
            f"Should this movie still be recommended despite the flag? "
            f"Reply with exactly one word: YES or NO, then a dash, then a brief reason "
            f"(max 15 words). Example: YES - strong director match overrides genre mismatch."
        )

        try:
            raw = self.generate_response(
                prompt=prompt,
                system_prompt="You are a movie recommendation quality checker. Be concise.",
                max_tokens=60,
            )
            raw = raw.strip()
            if re.match(r"^YES", raw, re.IGNORECASE):
                return "pass"
        except Exception as e:
            logger.warning(f"Critic LLM verify failed: {e}")

        return "fail"


def get_critic_agent() -> AdversarialCriticAgent:
    """Get configured Adversarial Critic agent."""
    return AdversarialCriticAgent()
