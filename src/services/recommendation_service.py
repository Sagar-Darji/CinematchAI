"""Recommendation Service - Business logic for recommendations."""

import hashlib
import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.agents.graph.workflow import run_recommendation_workflow
from src.api.schemas.response import (
    MovieResponse,
    RecommendationItemResponse,
    RecommendationResponse,
)
from src.core.models import Recommendation
from src.utils.logging import get_logger

logger = get_logger(__name__)

# In-memory store for async jobs: job_id → {status, steps, result, error}
_async_jobs: Dict[str, Dict[str, Any]] = {}
_async_jobs_lock = threading.Lock()

# Short-lived recommendation result cache: (user_id, context_hash) → (timestamp, response)
# TTL = 5 minutes — prevents redundant re-runs when user spams the button.
_REC_CACHE_TTL = 300  # seconds
_rec_cache: Dict[str, tuple] = {}  # key → (stored_at, RecommendationResponse)
_rec_cache_lock = threading.Lock()


def _rec_cache_key(user_id: str, context: Optional[Dict], k: int) -> str:
    payload = json.dumps({"u": user_id, "c": context or {}, "k": k}, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def _rec_cache_get(key: str):
    with _rec_cache_lock:
        entry = _rec_cache.get(key)
        if entry and (time.time() - entry[0]) < _REC_CACHE_TTL:
            return entry[1]
        if entry:
            del _rec_cache[key]
        return None


def _rec_cache_set(key: str, value):
    with _rec_cache_lock:
        _rec_cache[key] = (time.time(), value)


class RecommendationService:
    """Service for generating recommendations."""

    def get_recommendations(
        self,
        user_id: str,
        context: Optional[Dict[str, str]] = None,
        k: int = 10,
        use_hybrid: bool = True,
    ) -> RecommendationResponse:
        """
        Get personalized recommendations for a user.

        Args:
            user_id: User ID.
            context: Context information.
            k: Number of recommendations.
            use_hybrid: Use hybrid embeddings.

        Returns:
            Recommendation response.
        """
        logger.info(f"Getting recommendations for user_id={user_id}, k={k}")

        # Check 5-minute result cache first
        cache_key = _rec_cache_key(user_id, context, k)
        cached = _rec_cache_get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached recommendations for {user_id}")
            return cached

        try:
            # Run workflow
            final_state = run_recommendation_workflow(
                user_id=user_id,
                context=context,
                is_cold_start=False,
                k=k,
            )

            # Convert to response format
            recommendations = self._convert_recommendations(
                final_state.get("final_recommendations", [])
            )

            # Limit to k
            recommendations = recommendations[:k]

            response = RecommendationResponse(
                user_id=user_id,
                recommendations=recommendations,
                workflow_type=final_state.get("workflow_type", "single_user"),
                processing_steps=final_state.get("processing_steps", []),
                context_factors=final_state.get("context_factors"),
                trace_id=final_state.get("_trace_id"),
            )

            logger.info(f"Generated {len(recommendations)} recommendations")

            # Store in 5-minute result cache
            _rec_cache_set(cache_key, response)

            return response

        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            raise

    def get_group_recommendations(
        self,
        user_ids: List[str],
        context: Optional[Dict[str, str]] = None,
        aggregation_strategy: str = "multiplicative",
        k: int = 10,
    ) -> Dict[str, Any]:
        """
        Get recommendations for a group of users.

        Args:
            user_ids: List of user IDs.
            context: Context information.
            aggregation_strategy: Strategy for aggregating preferences.
            k: Number of recommendations.

        Returns:
            Group recommendation response.
        """
        logger.info(
            f"Getting group recommendations for {len(user_ids)} users, strategy={aggregation_strategy}"
        )

        try:
            # Run workflow with group mode
            final_state = run_recommendation_workflow(
                user_ids=user_ids,
                context=context or {},
            )

            # Add aggregation strategy to state (before workflow starts)
            # Note: This should ideally be passed in the workflow itself
            final_state["aggregation_strategy"] = aggregation_strategy

            # Convert to response format
            recommendations = self._convert_recommendations(
                final_state.get("final_recommendations", [])
            )[:k]

            response = {
                "user_ids": user_ids,
                "recommendations": recommendations,
                "aggregation_strategy": aggregation_strategy,
                "fairness_score": final_state.get("fairness_score", 0.0),
                "satisfaction_distribution": final_state.get(
                    "satisfaction_distribution", {}
                ),
                "conflict_areas": final_state.get("conflict_areas", []),
                "processing_steps": final_state.get("processing_steps", []),
            }

            logger.info(
                f"Generated {len(recommendations)} group recommendations with fairness={response['fairness_score']:.2f}"
            )

            return response

        except Exception as e:
            logger.error(f"Failed to get group recommendations: {e}")
            raise

    def _convert_recommendations(
        self, recommendations: List[Recommendation]
    ) -> List[RecommendationItemResponse]:
        """
        Convert internal Recommendation objects to API response format.

        Args:
            recommendations: List of Recommendation objects.

        Returns:
            List of RecommendationItemResponse objects.
        """
        response_items = []

        for rec in recommendations:
            movie_response = MovieResponse(
                tmdb_id=int(rec.movie.metadata.tmdb_id) if rec.movie.metadata.tmdb_id else 0,
                title=rec.movie.metadata.title,
                year=rec.movie.metadata.year,
                genres=rec.movie.metadata.genres or [],
                overview=rec.movie.metadata.overview or "",
                vote_average=rec.movie.metadata.vote_average,
                director=rec.movie.metadata.director,
                poster_path=rec.movie.metadata.poster_path,
            )

            # Extract explanation text from Explanation object or string
            if hasattr(rec.explanation, "primary_reason"):
                explanation_text = rec.explanation.primary_reason
            else:
                explanation_text = str(rec.explanation)

            item = RecommendationItemResponse(
                movie=movie_response,
                score=rec.score,
                rank=rec.rank,
                explanation=explanation_text,
                is_exploration=rec.is_exploration,
            )

            response_items.append(item)

        return response_items

    # ----------------------------------------------------------------
    # Async job API
    # ----------------------------------------------------------------

    def submit_async(
        self,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
        k: int = 10,
    ) -> str:
        """Submit a recommendation job asynchronously.

        Returns:
            job_id (UUID string) — poll with get_job_result(job_id).
        """
        job_id = str(uuid.uuid4())
        with _async_jobs_lock:
            _async_jobs[job_id] = {
                "status": "pending",
                "steps": [],
                "result": None,
                "error": None,
            }

        def _run():
            try:
                with _async_jobs_lock:
                    _async_jobs[job_id]["status"] = "running"

                def _progress(step_name: str, detail: str):
                    with _async_jobs_lock:
                        if job_id in _async_jobs:
                            _async_jobs[job_id]["steps"].append(
                                {"step": step_name, "detail": detail}
                            )

                final_state = run_recommendation_workflow(
                    user_id=user_id,
                    context=context,
                    is_cold_start=False,
                    k=k,
                    progress_callback=_progress,
                )
                recommendations = self._convert_recommendations(
                    final_state.get("final_recommendations", [])
                )[:k]
                result = RecommendationResponse(
                    user_id=user_id,
                    recommendations=recommendations,
                    workflow_type=final_state.get("workflow_type", "single_user"),
                    processing_steps=final_state.get("processing_steps", []),
                    context_factors=final_state.get("context_factors"),
                    trace_id=final_state.get("_trace_id"),
                )
                with _async_jobs_lock:
                    if job_id in _async_jobs:
                        _async_jobs[job_id]["status"] = "complete"
                        _async_jobs[job_id]["result"] = result
            except Exception as e:
                logger.error(f"Async job {job_id} failed: {e}")
                with _async_jobs_lock:
                    if job_id in _async_jobs:
                        _async_jobs[job_id]["status"] = "failed"
                        _async_jobs[job_id]["error"] = str(e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return job_id

    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Poll for the result of an async recommendation job.

        Returns:
            dict with keys: status, steps, result (RecommendationResponse), error
            or None if job_id is unknown.
        """
        with _async_jobs_lock:
            job = _async_jobs.get(job_id)
            if job is None:
                return None
            return dict(job)  # shallow copy to avoid holding the lock


# Singleton instance
_recommendation_service = None


def get_recommendation_service() -> RecommendationService:
    """Get recommendation service instance."""
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationService()
    return _recommendation_service
