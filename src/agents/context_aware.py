"""Context-Aware Agent - Analyzes viewing context and environment."""

from datetime import datetime
from typing import Any, Dict, Optional

from src.agents.base_agent import BaseAgent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ContextAwareAgent(BaseAgent):
    """Agent that analyzes viewing context and environmental factors."""

    def __init__(self):
        """Initialize Context-Aware agent."""
        super().__init__(
            name="Context-Aware",
            description="Analyzes temporal and environmental context",
            temperature=0.2,  # Low temperature for consistent context detection
            use_fast_model=True,  # Use fast model for simple context analysis
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze viewing context.

        Args:
            state: Current state with optional context hints.

        Returns:
            Updated state with context_factors and context_weights.
        """
        self.log_processing("Starting context analysis")

        # Get context hints from user
        context_input = state.get("context", {})

        # Detect current context
        context_factors = self._detect_context(context_input)

        # Calculate weights for different factors
        context_weights = self._calculate_context_weights(context_factors)

        # Update state
        state["context_factors"] = context_factors
        state["context_weights"] = context_weights
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Context-Aware: Analyzed viewing context"
        ]

        return state

    def _detect_context(self, context_input: Dict) -> Dict[str, Any]:
        """
        Detect current viewing context.

        Args:
            context_input: User-provided context hints.

        Returns:
            Complete context factors.
        """
        now = datetime.now()

        context = {
            # Temporal factors
            "time_of_day": self._get_time_of_day(
                context_input.get("time_of_day"), now
            ),
            "day_of_week": self._get_day_of_week(now),
            "is_weekend": now.weekday() >= 5,
            "season": self._get_season(now),
            "month": now.strftime("%B"),

            # User-provided context
            "mood": context_input.get("mood"),
            "companion": context_input.get("companion", "alone"),
            "occasion": context_input.get("occasion"),

            # Viewing situation
            "viewing_situation": self._infer_viewing_situation(
                context_input, now
            ),
        }

        return context

    def _get_time_of_day(
        self, provided: Optional[str], now: datetime
    ) -> str:
        """Get time of day (morning, afternoon, evening, night)."""
        if provided:
            return provided

        hour = now.hour
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 23:
            return "evening"
        else:
            return "night"

    def _get_day_of_week(self, now: datetime) -> str:
        """Get day of week."""
        return now.strftime("%A")

    def _get_season(self, now: datetime) -> str:
        """Get current season."""
        month = now.month

        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"

    def _infer_viewing_situation(
        self, context_input: Dict, now: datetime
    ) -> str:
        """
        Infer viewing situation from context.

        Args:
            context_input: User context.
            now: Current datetime.

        Returns:
            Viewing situation description.
        """
        companion = context_input.get("companion", "alone")
        time_of_day = self._get_time_of_day(None, now)
        is_weekend = now.weekday() >= 5

        # Build situation description
        situations = []

        if is_weekend and time_of_day == "evening":
            if companion == "friends":
                return "weekend_social_gathering"
            elif companion == "family":
                return "family_movie_night"
            else:
                return "weekend_relaxation"

        elif time_of_day == "night" and companion == "alone":
            return "late_night_solo"

        elif time_of_day == "afternoon" and is_weekend:
            return "lazy_weekend_afternoon"

        elif not is_weekend and time_of_day == "evening":
            if companion == "alone":
                return "weeknight_unwind"
            else:
                return "weeknight_date"

        else:
            return "casual_viewing"

    def _calculate_context_weights(
        self, context_factors: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate importance weights for different context factors.

        Args:
            context_factors: Detected context factors.

        Returns:
            Dictionary of weights (0-1) for each factor.
        """
        weights = {}

        # Time-based weights
        time_of_day = context_factors.get("time_of_day", "evening")
        if time_of_day == "morning":
            weights["lighthearted"] = 0.8
            weights["uplifting"] = 0.7
            weights["short_runtime"] = 0.6
        elif time_of_day == "afternoon":
            weights["lighthearted"] = 0.6
            weights["moderate_length"] = 0.7
        elif time_of_day == "evening":
            weights["engaging"] = 0.8
            weights["quality"] = 0.9
        else:  # night
            weights["atmospheric"] = 0.7
            weights["thought_provoking"] = 0.6

        # Companion-based weights
        companion = context_factors.get("companion", "alone")
        if companion == "family":
            weights["family_friendly"] = 1.0
            weights["crowd_pleaser"] = 0.8
        elif companion == "friends":
            weights["social"] = 0.9
            weights["entertaining"] = 0.8
        elif companion == "partner":
            weights["romantic"] = 0.7
            weights["quality"] = 0.8
        else:  # alone
            weights["personal_interest"] = 1.0
            weights["exploration"] = 0.6

        # Weekend vs weekday
        if context_factors.get("is_weekend"):
            weights["longer_runtime_ok"] = 0.7
            weights["immersive"] = 0.8
        else:
            weights["efficient_runtime"] = 0.7
            weights["relaxing"] = 0.6

        # Mood-based weights
        mood = context_factors.get("mood")
        if mood:
            mood_weights = self._mood_to_weights(mood)
            weights.update(mood_weights)

        return weights

    def _mood_to_weights(self, mood: str) -> Dict[str, float]:
        """Map mood to content weights."""
        mood = mood.lower()

        mood_map = {
            "happy": {"uplifting": 0.9, "comedy": 0.7},
            "sad": {"emotional": 0.8, "comforting": 0.7},
            "stressed": {"relaxing": 0.9, "escapist": 0.8},
            "bored": {"exciting": 0.9, "surprising": 0.8},
            "thoughtful": {"cerebral": 0.9, "thought_provoking": 0.8},
            "energetic": {"action": 0.9, "fast_paced": 0.8},
            "nostalgic": {"classic": 0.8, "comforting": 0.7},
            "adventurous": {"exploration": 0.9, "novel": 0.8},
        }

        return mood_map.get(mood, {})


def get_context_aware_agent() -> ContextAwareAgent:
    """Get configured Context-Aware agent."""
    return ContextAwareAgent()
