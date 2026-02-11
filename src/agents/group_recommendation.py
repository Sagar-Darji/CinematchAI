"""Group Recommendation Agent - Multi-user fairness and consensus."""

from typing import Any, Dict, List

import numpy as np

from src.agents.base_agent import BaseAgent
from src.core.models import Movie, UserProfile
from src.utils.logging import get_logger

logger = get_logger(__name__)


class GroupRecommendationAgent(BaseAgent):
    """Agent that handles multi-user group recommendations with fairness."""

    def __init__(self):
        """Initialize Group Recommendation agent."""
        super().__init__(
            name="Group Recommendation",
            description="Multi-user consensus and fairness optimization",
            temperature=0.4,  # Lower temperature for consistent fairness
            use_fast_model=False,  # Use main model for complex aggregation
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process group recommendation request.

        Args:
            state: Current state with user_ids and aggregation_strategy.

        Returns:
            Updated state with group recommendations and fairness metrics.
        """
        self.log_processing("Processing group recommendation")

        user_ids = state.get("user_ids", [])

        if len(user_ids) <= 1:
            # Not a group request, skip
            return state

        # Get individual user profiles
        user_profiles = state.get("user_profiles", {})

        # Get aggregation strategy
        aggregation_strategy = state.get("aggregation_strategy", "multiplicative")

        # Aggregate preferences
        group_preferences = self._aggregate_preferences(
            user_profiles, aggregation_strategy
        )

        # Detect conflicts
        conflict_areas = self._detect_conflicts(user_profiles)

        # Calculate fairness metrics
        fairness_metrics = self._calculate_fairness(
            state.get("candidate_movies", []), user_profiles
        )

        # Update state
        state["group_preferences"] = group_preferences
        state["conflict_areas"] = conflict_areas
        state["fairness_score"] = fairness_metrics.get("fairness_score", 0.0)
        state["satisfaction_distribution"] = fairness_metrics.get(
            "satisfaction_distribution", {}
        )
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Group Recommendation: Aggregated {len(user_ids)} users ({aggregation_strategy})"
        ]

        return state

    def _aggregate_preferences(
        self, user_profiles: Dict[str, UserProfile], strategy: str
    ) -> Dict[str, Any]:
        """
        Aggregate preferences from multiple users.

        Args:
            user_profiles: Dictionary of user profiles.
            strategy: Aggregation strategy.

        Returns:
            Aggregated group preferences.
        """
        if not user_profiles:
            return {}

        if strategy == "multiplicative":
            return self._multiplicative_aggregation(user_profiles)
        elif strategy == "least_misery":
            return self._least_misery_aggregation(user_profiles)
        elif strategy == "average":
            return self._average_aggregation(user_profiles)
        else:
            # Default to multiplicative
            return self._multiplicative_aggregation(user_profiles)

    def _multiplicative_aggregation(
        self, user_profiles: Dict[str, UserProfile]
    ) -> Dict[str, Any]:
        """
        Multiplicative aggregation (balanced approach).

        Multiplies individual scores, giving weight to all users.
        """
        all_genres = []

        for profile in user_profiles.values():
            if hasattr(profile, "preferences"):
                all_genres.extend(profile.preferences.favorite_genres or [])

        # Count genre frequencies
        from collections import Counter

        genre_counts = Counter(all_genres)

        # Genres liked by multiple users get higher weight
        group_genres = [
            genre
            for genre, count in genre_counts.most_common(10)
            if count >= len(user_profiles) * 0.3  # At least 30% agreement
        ]

        return {
            "favorite_genres": group_genres,
            "strategy": "multiplicative",
            "agreement_level": len(group_genres) / 10 if group_genres else 0,
        }

    def _least_misery_aggregation(
        self, user_profiles: Dict[str, UserProfile]
    ) -> Dict[str, Any]:
        """
        Least misery aggregation (ensure minimum satisfaction).

        Focuses on avoiding movies that any user would dislike.
        """
        # Find genres that NO user dislikes
        all_disliked = set()

        for profile in user_profiles.values():
            if hasattr(profile, "preferences"):
                all_disliked.update(profile.preferences.disliked_genres or [])

        # Find genres that at least some users like
        all_liked = []

        for profile in user_profiles.values():
            if hasattr(profile, "preferences"):
                all_liked.extend(profile.preferences.favorite_genres or [])

        from collections import Counter

        genre_counts = Counter(all_liked)

        # Remove universally disliked genres
        group_genres = [
            genre
            for genre, _ in genre_counts.most_common(10)
            if genre not in all_disliked
        ]

        return {
            "favorite_genres": group_genres,
            "strategy": "least_misery",
            "avoided_genres": list(all_disliked),
        }

    def _average_aggregation(
        self, user_profiles: Dict[str, UserProfile]
    ) -> Dict[str, Any]:
        """
        Average aggregation (simple averaging).

        Treats all users equally and averages preferences.
        """
        all_genres = []

        for profile in user_profiles.values():
            if hasattr(profile, "preferences"):
                all_genres.extend(profile.preferences.favorite_genres or [])

        from collections import Counter

        genre_counts = Counter(all_genres)
        group_genres = [genre for genre, _ in genre_counts.most_common(10)]

        return {
            "favorite_genres": group_genres,
            "strategy": "average",
        }

    def _detect_conflicts(
        self, user_profiles: Dict[str, UserProfile]
    ) -> List[str]:
        """
        Detect conflicting preferences in the group.

        Args:
            user_profiles: User profiles.

        Returns:
            List of conflict descriptions.
        """
        conflicts = []

        # Check for genre conflicts
        liked_by_user = {}
        disliked_by_user = {}

        for user_id, profile in user_profiles.items():
            if hasattr(profile, "preferences"):
                liked_by_user[user_id] = set(
                    profile.preferences.favorite_genres or []
                )
                disliked_by_user[user_id] = set(
                    profile.preferences.disliked_genres or []
                )

        # Find genres liked by one user but disliked by another
        for user1, liked1 in liked_by_user.items():
            for user2, disliked2 in disliked_by_user.items():
                if user1 != user2:
                    conflict_genres = liked1 & disliked2
                    if conflict_genres:
                        conflicts.append(
                            f"User {user1} likes {', '.join(list(conflict_genres)[:2])} "
                            f"but User {user2} dislikes it"
                        )

        return conflicts

    def _calculate_fairness(
        self, candidates: List[Movie], user_profiles: Dict[str, UserProfile]
    ) -> Dict[str, Any]:
        """
        Calculate fairness metrics for recommendations.

        Args:
            candidates: Candidate movies.
            user_profiles: User profiles.

        Returns:
            Fairness metrics.
        """
        if not candidates or not user_profiles:
            return {
                "fairness_score": 0.0,
                "satisfaction_distribution": {},
            }

        # Calculate satisfaction for each user
        satisfaction = {}

        for user_id, profile in user_profiles.items():
            user_satisfaction = self._calculate_user_satisfaction(
                candidates, profile
            )
            satisfaction[user_id] = user_satisfaction

        # Calculate fairness score (1 - variance in satisfaction)
        satisfaction_values = list(satisfaction.values())

        if satisfaction_values:
            mean_sat = np.mean(satisfaction_values)
            std_sat = np.std(satisfaction_values)

            # Fairness is high when standard deviation is low
            fairness_score = max(0, 1 - std_sat)
        else:
            fairness_score = 0.0

        return {
            "fairness_score": fairness_score,
            "satisfaction_distribution": satisfaction,
            "min_satisfaction": min(satisfaction_values) if satisfaction_values else 0,
            "max_satisfaction": max(satisfaction_values) if satisfaction_values else 0,
        }

    def _calculate_user_satisfaction(
        self, movies: List[Movie], profile: UserProfile
    ) -> float:
        """
        Calculate how satisfied a user would be with the movie list.

        Args:
            movies: List of movies.
            profile: User profile.

        Returns:
            Satisfaction score (0-1).
        """
        if not movies or not hasattr(profile, "preferences"):
            return 0.5

        favorite_genres = set(profile.preferences.favorite_genres or [])
        disliked_genres = set(profile.preferences.disliked_genres or [])

        matches = 0
        mismatches = 0

        for movie in movies:
            movie_genres = set(movie.metadata.genres or [])

            # Check for matches
            if favorite_genres & movie_genres:
                matches += 1

            # Check for mismatches
            if disliked_genres & movie_genres:
                mismatches += 1

        # Calculate satisfaction
        total = len(movies)
        satisfaction = (matches - mismatches) / total if total > 0 else 0.5

        # Normalize to 0-1
        satisfaction = max(0, min(1, (satisfaction + 1) / 2))

        return satisfaction


def get_group_recommendation_agent() -> GroupRecommendationAgent:
    """Get configured Group Recommendation agent."""
    return GroupRecommendationAgent()
