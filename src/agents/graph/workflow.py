"""LangGraph Workflow - Orchestrates multi-agent recommendation system."""

import time
from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import END, StateGraph

from src.agents.context_aware import get_context_aware_agent
from src.agents.content_intelligence import get_content_intelligence_agent
from src.agents.critic import get_critic_agent
from src.agents.explanation import get_explanation_agent
from src.agents.graph.state import RecommendationState
from src.agents.graph.tools import retrieve_candidates_hybrid
from src.agents.group_recommendation import get_group_recommendation_agent
from src.agents.profile_analyzer import get_profile_analyzer_agent
from src.agents.serendipity import get_serendipity_agent
from src.agents.supervisor import get_supervisor_agent
from src.services.trace_service import get_trace_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Initialize all agents (singleton pattern)
_supervisor = None
_profile_analyzer = None
_content_intelligence = None
_context_aware = None
_serendipity = None
_critic = None
_explanation = None
_group_recommendation = None


def get_agents():
    """Get all agent instances (lazy initialization)."""
    global _supervisor, _profile_analyzer, _content_intelligence
    global _context_aware, _serendipity, _critic, _explanation, _group_recommendation

    if _supervisor is None:
        logger.info("Initializing all agents...")
        _supervisor = get_supervisor_agent()
        _profile_analyzer = get_profile_analyzer_agent()
        _content_intelligence = get_content_intelligence_agent()
        _context_aware = get_context_aware_agent()
        _serendipity = get_serendipity_agent()
        _critic = get_critic_agent()
        _explanation = get_explanation_agent()
        _group_recommendation = get_group_recommendation_agent()
        logger.info("All agents initialized")

    return {
        "supervisor": _supervisor,
        "profile_analyzer": _profile_analyzer,
        "content_intelligence": _content_intelligence,
        "context_aware": _context_aware,
        "serendipity": _serendipity,
        "critic": _critic,
        "explanation": _explanation,
        "group_recommendation": _group_recommendation,
    }


# Node functions (wrap agent.process with tracing)


def _add_trace_step(state, agent_name, start_time, summary, details=None):
    """Helper to add a trace step and emit a progress event."""
    trace_id = state.get("_trace_id")
    if trace_id:
        duration_ms = (time.time() - start_time) * 1000
        try:
            get_trace_service().add_step(
                trace_id=trace_id,
                agent_name=agent_name,
                duration_ms=duration_ms,
                summary=summary,
                details=details or {},
            )
        except Exception as e:
            logger.warning(f"Failed to add trace step: {e}")

    # Emit progress event for async streaming / UI trace display
    cb = state.get("_progress_callback")
    if cb:
        try:
            cb(agent_name, summary)
        except Exception:
            pass


def supervisor_node(state: RecommendationState) -> RecommendationState:
    """Supervisor node."""
    agents = get_agents()
    return agents["supervisor"].process(state)


def profile_analyzer_node(state: RecommendationState) -> RecommendationState:
    """Profile Analyzer node."""
    start = time.time()
    agents = get_agents()
    result = agents["profile_analyzer"].process(state)

    profile = result.get("user_profile")
    details = {}
    if profile:
        details["total_ratings"] = getattr(profile, "total_ratings", 0)
        details["has_embedding"] = (
            getattr(profile, "profile_embedding", None) is not None
            and len(getattr(profile, "profile_embedding", []) or []) > 0
        )
        details["is_cold_start"] = getattr(profile, "is_cold_start", True)

    summary = f"Analyzed user profile ({details.get('total_ratings', 0)} ratings)"
    _add_trace_step(result, "Profile Analyzer", start, summary, details)
    return result


def content_intelligence_node(state: RecommendationState) -> RecommendationState:
    """Content Intelligence node."""
    start = time.time()
    agents = get_agents()
    result = agents["content_intelligence"].process(state)

    candidates_before = len(state.get("candidate_movies", []))
    candidates_after = len(result.get("candidate_movies", []))
    details = {
        "analyzed_count": candidates_before,
        "reranked_count": candidates_after,
    }
    summary = f"Analyzed {candidates_before} candidates, reranked to {candidates_after}"
    _add_trace_step(result, "Content Intelligence", start, summary, details)
    return result


def context_aware_node(state: RecommendationState) -> RecommendationState:
    """Context-Aware node."""
    start = time.time()
    agents = get_agents()
    result = agents["context_aware"].process(state)

    context = result.get("context_factors", {})
    details = {"context_factors": list(context.keys()) if context else []}
    summary = f"Processed context ({len(details['context_factors'])} factors)"
    _add_trace_step(result, "Context-Aware", start, summary, details)
    return result


def serendipity_node(state: RecommendationState) -> RecommendationState:
    """Serendipity node."""
    start = time.time()
    agents = get_agents()
    result = agents["serendipity"].process(state)

    diverse_count = len(result.get("diverse_candidates", []))
    exploration_count = len(result.get("exploration_items", []))
    details = {"diverse_count": diverse_count, "exploration_count": exploration_count}
    summary = f"Selected {diverse_count} diverse candidates, {exploration_count} exploration items"
    _add_trace_step(result, "Serendipity", start, summary, details)
    return result


def critic_node(state: RecommendationState) -> RecommendationState:
    """Adversarial Critic node — validates and stress-tests top candidates."""
    start = time.time()
    agents = get_agents()
    result = agents["critic"].process(state)

    verdicts = result.get("critic_verdicts", {})
    demoted = sum(1 for v in verdicts.values() if v.startswith("flagged"))
    details = {"total_checked": len(verdicts), "demoted": demoted}
    summary = f"Checked {len(verdicts)} candidates, demoted {demoted}"
    _add_trace_step(result, "Adversarial Critic", start, summary, details)
    return result


def explanation_node(state: RecommendationState) -> RecommendationState:
    """Explanation node."""
    start = time.time()
    agents = get_agents()
    result = agents["explanation"].process(state)

    explanation_count = len(result.get("explanations", {}))
    details = {"explanation_count": explanation_count}
    summary = f"Generated {explanation_count} explanations"
    _add_trace_step(result, "Explanation", start, summary, details)
    return result


def group_recommendation_node(state: RecommendationState) -> RecommendationState:
    """Group Recommendation node."""
    agents = get_agents()
    return agents["group_recommendation"].process(state)


def retrieval_node(state: RecommendationState) -> RecommendationState:
    """
    Retrieval node (RAG) — Hybrid: Cloud Vector DB + Smart TMDB Discovery.

    Uses retrieve_candidates_hybrid for both personalized and cold-start users.
    The hybrid function handles dynamic split and fallback internally.
    """
    start = time.time()
    user_profile = state.get("user_profile")

    has_profile_embedding = (
        user_profile is not None
        and hasattr(user_profile, "profile_embedding")
        and user_profile.profile_embedding is not None
        and len(user_profile.profile_embedding) > 0
    )

    if user_profile:
        logger.info(f"User profile exists: is_cold_start={getattr(user_profile, 'is_cold_start', 'N/A')}, "
                   f"total_ratings={getattr(user_profile, 'total_ratings', 'N/A')}, "
                   f"has_embedding={has_profile_embedding}")
    else:
        logger.info("No user profile found")

    # Hybrid retrieval handles both personalized and cold-start
    result = retrieve_candidates_hybrid(state, k=50, use_hybrid=True)

    if has_profile_embedding:
        source = "hybrid_cloud_tmdb"
    else:
        source = "hybrid_tmdb_cold_start"

    candidate_count = len(result.get("candidate_movies", []))
    details = {"source": source, "candidate_count": candidate_count}
    summary = f"Retrieved {candidate_count} candidates via {source}"
    _add_trace_step(result, "Retrieval", start, summary, details)

    result["_retrieval_source"] = source

    return result


def aggregation_node(state: RecommendationState) -> RecommendationState:
    """Aggregation node (final step)."""
    start = time.time()
    agents = get_agents()
    result = agents["supervisor"].aggregate_results(state)

    final_count = len(result.get("final_recommendations", []))
    details = {"final_count": final_count}
    summary = f"Aggregated {final_count} final recommendations"
    _add_trace_step(result, "Aggregation", start, summary, details)
    return result


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
    workflow.add_node("critic", critic_node)
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
            "critic": "critic",
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
    workflow.add_edge("critic", "supervisor")
    workflow.add_edge("explanation", "supervisor")
    workflow.add_edge("group_recommendation", "supervisor")

    # Final aggregation leads to END
    workflow.add_edge("aggregation", END)

    # Compile
    compiled_workflow = workflow.compile()

    logger.info("Recommendation workflow built successfully")

    return compiled_workflow


# Cached compiled workflow (singleton)
_compiled_workflow = None


def _get_cached_workflow():
    """Get or build the compiled workflow (singleton)."""
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_recommendation_workflow()
    return _compiled_workflow


# Main execution function


def run_recommendation_workflow(
    user_id: str = None,
    user_ids: List[str] = None,
    context: Dict[str, Any] = None,
    is_cold_start: bool = False,
    k: int = 10,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """Run the complete recommendation workflow.

    Args:
        user_id: Single user ID (optional).
        user_ids: List of user IDs for group recommendations (optional).
        context: Context information (time, mood, companion, etc.).
        is_cold_start: Whether this is a new user with no history.
        progress_callback: Optional callable(step_name, detail) called after
            each agent node completes — used for live streaming trace display.

    Returns:
        Final state with recommendations.
    """
    logger.info("Starting recommendation workflow")

    # Start trace
    trace_service = get_trace_service()
    trace_id = trace_service.start_trace(user_id or "group", context)

    # Build initial state
    initial_state = RecommendationState(
        user_id=user_id,
        user_ids=user_ids or ([user_id] if user_id else []),
        context=context or {},
        is_cold_start=is_cold_start,
        num_recommendations=k,
        processing_steps=[],
        _trace_id=trace_id,
        _progress_callback=progress_callback,
    )

    # Build and run workflow (cached singleton)
    workflow = _get_cached_workflow()

    try:
        # Execute workflow (increase recursion limit for multi-agent pipeline)
        final_state = workflow.invoke(
            initial_state,
            {"recursion_limit": 50},
        )

        final_count = len(final_state.get("final_recommendations", []))
        retrieval_source = final_state.get("_retrieval_source", "unknown")

        # Parse retrieval source from processing_steps if not in state
        if retrieval_source == "unknown":
            for step in final_state.get("processing_steps", []):
                if "PERSONALIZED" in step.upper() or "chromadb" in step.lower():
                    retrieval_source = "chromadb_personalized"
                    break
                elif "COLD-START" in step.upper() or "tmdb" in step.lower():
                    retrieval_source = "tmdb_cold_start"
                    break

        # Complete trace
        trace_service.complete_trace(
            trace_id=trace_id,
            retrieval_source=retrieval_source,
            candidate_count=len(final_state.get("candidate_movies", [])),
            final_count=final_count,
        )

        # Store trace_id in final state for API response
        final_state["_trace_id"] = trace_id

        logger.info(
            f"Workflow completed. Generated {final_count} recommendations"
        )

        return final_state

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        trace_service.fail_trace(trace_id, str(e))
        return {
            "error": str(e),
            "final_recommendations": [],
            "_trace_id": trace_id,
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
