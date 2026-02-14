"""Explanation Agent - Generates natural language explanations for recommendations."""

from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent
from src.core.models import Explanation, Movie
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ExplanationAgent(BaseAgent):
    """Agent that generates natural language explanations for recommendations."""

    def __init__(self):
        """Initialize Explanation agent."""
        super().__init__(
            name="Explanation",
            description="Generates natural language explanations",
            temperature=0.6,  # Moderate creativity for natural explanations
            use_fast_model=False,  # Use main model for quality explanations
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate explanations for recommendations via a single batched LLM call.

        Args:
            state: Current state with diverse_candidates and user_profile.

        Returns:
            Updated state with explanations.
        """
        self.log_processing("Generating explanations")

        diverse_candidates = state.get("diverse_candidates", [])
        user_profile = state.get("user_profile")
        context_factors = state.get("context_factors", {})
        exploration_items = state.get("exploration_items", [])

        if not diverse_candidates:
            logger.warning("No candidates to explain")
            return state

        top_movies = diverse_candidates[:10]
        exploration_ids = {str(m.metadata.tmdb_id) for m in exploration_items}

        # Try batched generation first (1 LLM call instead of 10)
        explanations = self._generate_explanations_batch(
            top_movies, user_profile, context_factors, exploration_ids,
        )

        # Fallback: fill any missing with template explanations
        for movie in top_movies:
            movie_id = str(movie.metadata.tmdb_id)
            if movie_id not in explanations or not explanations[movie_id]:
                explanations[movie_id] = self._template_explanation(
                    movie, user_profile, movie_id in exploration_ids,
                )

        state["explanations"] = explanations
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Explanation: Generated {len(explanations)} explanations (batched)"
        ]

        return state

    def _generate_explanations_batch(
        self,
        movies: List[Movie],
        user_profile,
        context_factors: Dict,
        exploration_ids: set,
    ) -> Dict[str, str]:
        """Generate explanations for all movies in a single LLM call."""
        # Build user context once
        user_context = []
        if user_profile and hasattr(user_profile, "preferences"):
            prefs = user_profile.preferences
            if prefs.favorite_genres:
                user_context.append(f"Loves: {', '.join(prefs.favorite_genres[:3])}")
            if prefs.favorite_directors:
                user_context.append(f"Fav directors: {', '.join(prefs.favorite_directors[:2])}")
        user_str = ". ".join(user_context) if user_context else "New user"

        context_parts = []
        if context_factors:
            if context_factors.get("time_of_day"):
                context_parts.append(f"{context_factors['time_of_day']} viewing")
            if context_factors.get("companion") and context_factors["companion"] != "alone":
                context_parts.append(f"watching with {context_factors['companion']}")
            if context_factors.get("mood"):
                context_parts.append(f"feeling {context_factors['mood']}")
        context_str = ", ".join(context_parts) if context_parts else "none"

        # Build movie list
        movie_lines = []
        for i, movie in enumerate(movies, 1):
            m = movie.metadata
            explore_note = " [EXPLORATORY]" if str(m.tmdb_id) in exploration_ids else ""
            movie_lines.append(
                f"{i}. [{m.tmdb_id}] \"{m.title}\" ({m.year}) — "
                f"{', '.join(m.genres or ['Unknown'])} — "
                f"Dir: {m.director or 'Unknown'} — "
                f"Rating: {m.vote_average or 'N/A'}/10{explore_note}"
            )

        prompt = f"""Generate a personalized 2-3 sentence explanation for EACH movie below.

User: {user_str}
Context: {context_str}

Movies:
{chr(10).join(movie_lines)}

For each movie, write a concise explanation of why it's recommended. For [EXPLORATORY] movies, mention it's a fresh discovery.

Format your response EXACTLY as:
[TMDB_ID]: explanation text
[TMDB_ID]: explanation text
..."""

        try:
            response = self.generate_response(
                prompt=prompt,
                system_prompt=(
                    "You are a friendly movie recommender. Write concise, specific "
                    "explanations (2-3 sentences each). Mention concrete details about "
                    "each movie. Format each line as [TMDB_ID]: explanation."
                ),
                max_tokens=1500,
            )

            # Parse response
            explanations = {}
            for line in response.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Match patterns like [12345]: text or 12345: text
                if "]:" in line:
                    bracket_start = line.find("[")
                    bracket_end = line.find("]:")
                    if bracket_start >= 0 and bracket_end > bracket_start:
                        tmdb_id = line[bracket_start + 1:bracket_end].strip()
                        text = line[bracket_end + 2:].strip()
                        if tmdb_id and text:
                            explanations[tmdb_id] = text

            logger.info(f"Batch explanations: parsed {len(explanations)}/{len(movies)}")
            return explanations

        except Exception as e:
            logger.warning(f"Batch explanation failed: {e}, using templates")
            return {}

    def _generate_explanation(
        self,
        movie: Movie,
        user_profile,
        context_factors: Dict,
        is_exploration: bool,
    ) -> str:
        """
        Generate natural language explanation for a recommendation.

        Args:
            movie: Movie to explain.
            user_profile: User profile.
            context_factors: Context information.
            is_exploration: Whether this is an exploratory recommendation.

        Returns:
            Natural language explanation.
        """
        # Build explanation prompt
        prompt = self._build_explanation_prompt(
            movie, user_profile, context_factors, is_exploration
        )

        try:
            # Generate explanation using LLM
            explanation = self.generate_response(
                prompt=prompt,
                system_prompt=(
                    "You are a friendly movie recommender explaining why a movie "
                    "is a good match. Be concise (2-3 sentences), specific, and "
                    "personable. Mention concrete details, not generic statements."
                ),
                max_tokens=150,
            )

            return explanation.strip()

        except Exception as e:
            logger.warning(f"Failed to generate LLM explanation: {e}")
            # Fallback to template-based explanation
            return self._template_explanation(
                movie, user_profile, is_exploration
            )

    def _build_explanation_prompt(
        self,
        movie: Movie,
        user_profile,
        context_factors: Dict,
        is_exploration: bool,
    ) -> str:
        """Build prompt for explanation generation."""
        metadata = movie.metadata

        # Extract user context
        user_context = []
        if user_profile and hasattr(user_profile, "preferences"):
            prefs = user_profile.preferences
            if prefs.favorite_genres:
                user_context.append(
                    f"User loves {', '.join(prefs.favorite_genres[:3])}"
                )
            if prefs.favorite_directors:
                user_context.append(
                    f"Favorite directors: {', '.join(prefs.favorite_directors[:2])}"
                )

        user_context_str = ". ".join(user_context) if user_context else "New user"

        # Extract context
        context_str = ""
        if context_factors:
            time_of_day = context_factors.get("time_of_day")
            companion = context_factors.get("companion")
            mood = context_factors.get("mood")

            context_parts = []
            if time_of_day:
                context_parts.append(f"{time_of_day} viewing")
            if companion and companion != "alone":
                context_parts.append(f"watching with {companion}")
            if mood:
                context_parts.append(f"feeling {mood}")

            context_str = ", ".join(context_parts) if context_parts else ""

        # Build prompt
        prompt = f"""Explain why "{metadata.title}" is recommended.

Movie: {metadata.title} ({metadata.year})
Genres: {', '.join(metadata.genres or ['Unknown'])}
Director: {metadata.director or 'Unknown'}
Rating: {metadata.vote_average or 'N/A'}/10

User context: {user_context_str}
{f'Viewing context: {context_str}' if context_str else ''}
{f'Note: This is an exploratory recommendation outside usual preferences.' if is_exploration else ''}

Explain in 2-3 sentences why this movie is recommended. Be specific and mention concrete details."""

        return prompt

    def _template_explanation(
        self, movie: Movie, user_profile, is_exploration: bool
    ) -> str:
        """Generate template-based explanation (fallback)."""
        metadata = movie.metadata

        # Base explanation
        parts = [f"Based on the {', '.join(metadata.genres[:2])} genres"]

        # Add user-specific reasons
        if user_profile and hasattr(user_profile, "preferences"):
            prefs = user_profile.preferences

            # Check genre match
            user_genres = set(prefs.favorite_genres or [])
            movie_genres = set(metadata.genres or [])
            common_genres = user_genres & movie_genres

            if common_genres:
                parts.append(
                    f"you enjoy ({', '.join(list(common_genres)[:2])})"
                )

            # Check director match
            if (
                prefs.favorite_directors
                and metadata.director in prefs.favorite_directors
            ):
                parts.append(f"from one of your favorite directors")

        # Add rating
        if metadata.vote_average and metadata.vote_average > 7.0:
            parts.append(
                f"with a strong {metadata.vote_average:.1f}/10 rating"
            )

        # Exploration note
        if is_exploration:
            parts.append(
                "This is a bit different from your usual preferences, "
                "but you might discover something new!"
            )

        explanation = ", ".join(parts) + "."

        return explanation


def get_explanation_agent() -> ExplanationAgent:
    """Get configured Explanation agent."""
    return ExplanationAgent()
