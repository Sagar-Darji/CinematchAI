"""Supervisor Agent - Orchestrates all specialized agents."""

from typing import Any, Dict, List, Literal

from src.agents.base_agent import BaseAgent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SupervisorAgent(BaseAgent):
    """Supervisor agent that routes requests and aggregates results."""

    def __init__(self):
        """Initialize Supervisor agent."""
        super().__init__(
            name="Supervisor",
            description="Routes requests and aggregates results from specialized agents",
            temperature=0.3,  # Low temperature for consistent routing
            use_fast_model=True,  # Use fast model for quick decisions
        )

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process supervisor logic (routing, aggregation).

        Args:
            state: Current workflow state.

        Returns:
            Updated state with supervisor decisions.
        """
        self.log_processing("Supervising workflow")

        # Determine workflow path
        workflow_type = self._determine_workflow_type(state)
        state["workflow_type"] = workflow_type

        # Add supervisor metadata
        state["supervisor_decisions"] = state.get("supervisor_decisions", [])
        state["supervisor_decisions"].append(
            f"Determined workflow: {workflow_type}"
        )

        return state

    def _determine_workflow_type(
        self, state: Dict[str, Any]
    ) -> Literal["single_user", "group", "cold_start"]:
        """
        Determine which workflow to execute.

        Args:
            state: Current state.

        Returns:
            Workflow type identifier.
        """
        user_ids = state.get("user_ids", [])
        user_profile = state.get("user_profile")
        is_cold_start = state.get("is_cold_start", False)

        # Cold start check
        if is_cold_start or (user_profile is None and len(user_ids) == 1):
            logger.info("Cold start workflow detected")
            return "cold_start"

        # Group check
        if len(user_ids) > 1:
            logger.info(f"Group workflow detected ({len(user_ids)} users)")
            return "group"

        # Default single user
        logger.info("Single user workflow detected")
        return "single_user"

    def route_next(
        self, state: Dict[str, Any]
    ) -> Literal[
        "profile_analyzer",
        "content_intelligence",
        "context_aware",
        "retrieval",
        "serendipity",
        "explanation",
        "group_recommendation",
        "end",
    ]:
        """
        Determine next agent to route to.

        Args:
            state: Current state.

        Returns:
            Next agent name or "end".
        """
        # Check processing steps to determine where we are
        processing_steps = state.get("processing_steps", [])

        # Profile analysis (first step for all workflows)
        if not any("Profile Analyzer" in step for step in processing_steps):
            return "profile_analyzer"

        # Context analysis
        if not any("Context-Aware" in step for step in processing_steps):
            return "context_aware"

        # Retrieval (get candidates) — only attempt once
        retrieval_attempted = any("Retrieval" in step or "Cold-Start" in step for step in processing_steps)
        if not state.get("candidate_movies") and not retrieval_attempted:
            return "retrieval"

        # If retrieval was attempted but returned nothing, skip to end
        if not state.get("candidate_movies") and retrieval_attempted:
            logger.warning("Retrieval returned no candidates, ending workflow")
            return "end"

        # Content intelligence (after we have candidates)
        if (
            state.get("candidate_movies")
            and not any("Content Intelligence" in step for step in processing_steps)
        ):
            return "content_intelligence"

        # Group recommendation (if multi-user)
        workflow_type = state.get("workflow_type", "single_user")
        if workflow_type == "group" and not any(
            "Group Recommendation" in step for step in processing_steps
        ):
            return "group_recommendation"

        # Serendipity
        if not state.get("diverse_candidates"):
            return "serendipity"

        # Explanation (final step)
        if not state.get("explanations"):
            return "explanation"

        # Done
        return "end"

    def aggregate_results(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate results from all agents into final recommendations.

        Args:
            state: Current state with all agent outputs.

        Returns:
            Updated state with final_recommendations.
        """
        self.log_processing("Aggregating final recommendations")

        # Get diverse candidates (after serendipity)
        diverse_candidates = state.get("diverse_candidates", [])

        if not diverse_candidates:
            logger.warning("No diverse candidates to aggregate")
            state["final_recommendations"] = []
            return state

        # Get explanations
        explanations = state.get("explanations", {})

        # Build final recommendations
        from src.core.models import Explanation, Recommendation

        final_recommendations = []

        num_recs = state.get("num_recommendations", 10)
        for idx, movie in enumerate(diverse_candidates[:num_recs], start=1):
            movie_id = str(movie.metadata.tmdb_id)
            explanation_text = explanations.get(movie_id, "Recommended based on your preferences.")

            # Wrap string explanation into Explanation object
            if isinstance(explanation_text, str):
                explanation = Explanation(
                    primary_reason=explanation_text,
                    supporting_factors=[],
                    confidence=0.8,
                )
            else:
                explanation = explanation_text

            recommendation = Recommendation(
                movie=movie,
                score=1.0 - (idx - 1) * 0.05,  # Decreasing score (1.0, 0.95, 0.90, ...)
                explanation=explanation,
                rank=idx,
                is_exploration=movie in state.get("exploration_items", []),
            )

            final_recommendations.append(recommendation)

        state["final_recommendations"] = final_recommendations

        # Log summary
        logger.info(f"Generated {len(final_recommendations)} final recommendations")

        # Add to processing steps
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Supervisor: Aggregated {len(final_recommendations)} recommendations"
        ]

        return state


def get_supervisor_agent() -> SupervisorAgent:
    """Get configured Supervisor agent."""
    return SupervisorAgent()
