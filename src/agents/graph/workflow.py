"""LangGraph Workflow - Orchestrates multi-agent recommendation system."""

from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from src.agents.context_aware import get_context_aware_agent
from src.agents.content_intelligence import get_content_intelligence_agent
from src.agents.explanation import get_explanation_agent
from src.agents.graph.state import RecommendationState
from src.agents.graph.tools import cold_start_retrieval, retrieve_candidates
from src.agents.group_recommendation import get_group_recommendation_agent
from src.agents.profile_analyzer import get_profile_analyzer_agent
from src.agents.serendipity import get_serendipity_agent
from src.agents.supervisor import get_supervisor_agent
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Initialize all agents (singleton pattern)
_supervisor = None
_profile_analyzer = None
_content_intelligence = None
_context_aware = None
_serendipity = None
_explanation = None
_group_recommendation = None


def get_agents():
    """Get all agent instances (lazy initialization)."""
    global _supervisor, _profile_analyzer, _content_intelligence
    global _context_aware, _serendipity, _explanation, _group_recommendation

    if _supervisor is None:
        logger.info("Initializing all agents...")
        _supervisor = get_supervisor_agent()
        _profile_analyzer = get_profile_analyzer_agent()
        _content_intelligence = get_content_intelligence_agent()
        _context_aware = get_context_aware_agent()
        _serendipity = get_serendipity_agent()
        _explanation = get_explanation_agent()
        _group_recommendation = get_group_recommendation_agent()
        logger.info("All agents initialized")

    return {
        "supervisor": _supervisor,
        "profile_analyzer": _profile_analyzer,
        "content_intelligence": _content_intelligence,
        "context_aware": _context_aware,
        "serendipity": _serendipity,
        "explanation": _explanation,
        "group_recommendation": _group_recommendation,
    }


# Node functions (wrap agent.process)


def supervisor_node(state: RecommendationState) -> RecommendationState:
    """Supervisor node."""
    agents = get_agents()
    return agents["supervisor"].process(state)


def profile_analyzer_node(state: RecommendationState) -> RecommendationState:
    """Profile Analyzer node."""
    agents = get_agents()
    return agents["profile_analyzer"].process(state)


def content_intelligence_node(state: RecommendationState) -> RecommendationState:
    """Content Intelligence node."""
    agents = get_agents()
    return agents["content_intelligence"].process(state)


def context_aware_node(state: RecommendationState) -> RecommendationState:
    """Context-Aware node."""
    agents = get_agents()
    return agents["context_aware"].process(state)


def serendipity_node(state: RecommendationState) -> RecommendationState:
    """Serendipity node."""
    agents = get_agents()
    return agents["serendipity"].process(state)


def explanation_node(state: RecommendationState) -> RecommendationState:
    """Explanation node."""
    agents = get_agents()
    return agents["explanation"].process(state)


def group_recommendation_node(state: RecommendationState) -> RecommendationState:
    """Group Recommendation node."""
    agents = get_agents()
    return agents["group_recommendation"].process(state)


def retrieval_node(state: RecommendationState) -> RecommendationState:
    """
    Retrieval node (RAG).

    Prioritizes personalized recommendations when user has profile embedding.
    Only uses cold-start for truly new users.

    CRITICAL FIX: Simplified logic to properly detect personalized vs cold-start.
    """
    user_profile = state.get("user_profile")

    # SIMPLE LOGIC: Check if profile has embedding
    has_profile_embedding = (
        user_profile is not None
        and hasattr(user_profile, "profile_embedding")
        and user_profile.profile_embedding is not None
        and len(user_profile.profile_embedding) > 0
    )

    # Log for debugging
    if user_profile:
        logger.info(f"User profile exists: is_cold_start={getattr(user_profile, 'is_cold_start', 'N/A')}, "
                   f"total_ratings={getattr(user_profile, 'total_ratings', 'N/A')}, "
                   f"has_embedding={has_profile_embedding}")
    else:
        logger.info("No user profile found")

    if has_profile_embedding:
        logger.info("✅ Using PERSONALIZED retrieval (user has profile embedding from ratings)")
        return retrieve_candidates(state, k=50, use_hybrid=True)
    else:
        logger.info("❄️ Using COLD-START retrieval (no profile embedding available)")
        return cold_start_retrieval(state)


def aggregation_node(state: RecommendationState) -> RecommendationState:
    """Aggregation node (final step)."""
    agents = get_agents()
    return agents["supervisor"].aggregate_results(state)


# Routing function


def route_next(state: RecommendationState) -> str:
    """Determine next node to execute."""
    agents = get_agents()
    next_node = agents["supervisor"].route_next(state)
    logger.info(f"Routing to: {next_node}")
    return next_node


# Build the workflow graph


def build_recommendation_workflow() -> StateGraph:
    """
    Build the LangGraph workflow for recommendations.

    Returns:
        Compiled StateGraph ready for execution.
    """
    logger.info("Building recommendation workflow...")

    # Create graph
    workflow = StateGraph(RecommendationState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("profile_analyzer", profile_analyzer_node)
    workflow.add_node("content_intelligence", content_intelligence_node)
    workflow.add_node("context_aware", context_aware_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("serendipity", serendipity_node)
    workflow.add_node("explanation", explanation_node)
    workflow.add_node("group_recommendation", group_recommendation_node)
    workflow.add_node("aggregation", aggregation_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Add conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_next,
        {
            "profile_analyzer": "profile_analyzer",
            "content_intelligence": "content_intelligence",
            "context_aware": "context_aware",
            "retrieval": "retrieval",
            "serendipity": "serendipity",
            "explanation": "explanation",
            "group_recommendation": "group_recommendation",
            "end": "aggregation",
        },
    )

    # Add edges back to supervisor for routing
    workflow.add_edge("profile_analyzer", "supervisor")
    workflow.add_edge("content_intelligence", "supervisor")
    workflow.add_edge("context_aware", "supervisor")
    workflow.add_edge("retrieval", "supervisor")
    workflow.add_edge("serendipity", "supervisor")
    workflow.add_edge("explanation", "supervisor")
    workflow.add_edge("group_recommendation", "supervisor")

    # Final aggregation leads to END
    workflow.add_edge("aggregation", END)

    # Compile
    compiled_workflow = workflow.compile()

    logger.info("Recommendation workflow built successfully")

    return compiled_workflow


# Main execution function


def run_recommendation_workflow(
    user_id: str = None,
    user_ids: List[str] = None,
    context: Dict[str, Any] = None,
    is_cold_start: bool = False,
) -> Dict[str, Any]:
    """
    Run the complete recommendation workflow.

    Args:
        user_id: Single user ID (optional).
        user_ids: List of user IDs for group recommendations (optional).
        context: Context information (time, mood, companion, etc.).
        is_cold_start: Whether this is a new user with no history.

    Returns:
        Final state with recommendations.
    """
    logger.info("Starting recommendation workflow")

    # Build initial state
    initial_state = RecommendationState(
        user_id=user_id,
        user_ids=user_ids or ([user_id] if user_id else []),
        context=context or {},
        is_cold_start=is_cold_start,
        processing_steps=[],
    )

    # Build and run workflow
    workflow = build_recommendation_workflow()

    try:
        # Execute workflow (increase recursion limit for multi-agent pipeline)
        final_state = workflow.invoke(
            initial_state,
            {"recursion_limit": 50},
        )

        logger.info(
            f"Workflow completed. Generated {len(final_state.get('final_recommendations', []))} recommendations"
        )

        return final_state

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        return {
            "error": str(e),
            "final_recommendations": [],
        }


# Visualization helper


def visualize_workflow():
    """
    Visualize the workflow graph (for debugging/documentation).

    Returns:
        Graph visualization (requires graphviz).
    """
    workflow = build_recommendation_workflow()

    try:
        from langgraph.graph import Graph

        # Get Mermaid diagram
        mermaid = workflow.get_graph().draw_mermaid()
        print("Workflow Graph (Mermaid):")
        print(mermaid)

        return mermaid

    except Exception as e:
        logger.warning(f"Failed to visualize workflow: {e}")
        return None
