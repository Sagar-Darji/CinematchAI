"""Admin API routes - System monitoring and user inspection."""

import os
from typing import Optional

from diskcache import Cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_current_user
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Cache the resolved admin profile per user. /tmp on Lambda, ./data otherwise.
# 30 min TTL so a fresh rating shows up within reasonable time without a
# manual invalidation; UserService.add_rating / record_feedback also clear
# the cache (see below) for instant updates after explicit user actions.
_admin_cache_dir = "/tmp/admin_profile" if os.environ.get("LAMBDA_TASK_ROOT") else "./data/cache/admin_profile"
_admin_profile_cache = Cache(_admin_cache_dir)
_ADMIN_PROFILE_TTL = 30 * 60  # 30 min


def _admin_cache_key(user_id: str) -> str:
    return f"admin:{user_id}:v1"


def invalidate_admin_profile_cache(user_id: str) -> None:
    """Drop the cached admin profile for a user. Called from UserService when
    ratings change so the Profile page reflects new data immediately."""
    try:
        _admin_profile_cache.delete(_admin_cache_key(user_id))
    except Exception:
        pass


@router.get("/stats")
async def get_system_stats():
    """Get system-wide statistics: ChromaDB count, users, ratings, trace stats."""
    from src.services.user_service import get_user_service
    from src.services.trace_service import get_trace_service

    user_service = get_user_service()
    trace_service = get_trace_service()

    # ChromaDB document count
    chromadb_count = 0
    try:
        from src.core.vectordb.chroma_client import get_chroma_client
        chroma = get_chroma_client()
        chroma.get_collection()  # loads the default collection
        chromadb_count = chroma.count()
    except Exception as e:
        logger.warning(f"Failed to get ChromaDB count: {e}")

    # User and rating counts
    total_users = user_service.count_users()
    total_ratings = user_service.count_ratings()

    # Trace stats
    trace_stats = trace_service.get_stats()

    return {
        "chromadb_count": chromadb_count,
        "total_users": total_users,
        "total_ratings": total_ratings,
        "trace_stats": trace_stats,
    }


@router.get("/traces")
async def get_traces(
    limit: int = Query(default=20, ge=1, le=100),
    user_id: Optional[str] = Query(default=None),
):
    """Get recent pipeline traces, optionally filtered by user_id."""
    from src.services.trace_service import get_trace_service

    trace_service = get_trace_service()

    if user_id:
        traces = trace_service.get_user_traces(user_id, limit=limit)
    else:
        traces = trace_service.get_recent_traces(limit=limit)

    return {"traces": traces, "count": len(traces)}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a single trace by ID."""
    from src.services.trace_service import get_trace_service

    trace = get_trace_service().get_trace(trace_id)
    if not trace:
        return {"error": "Trace not found"}
    return trace


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str, current_user: str = Depends(get_current_user)):
    """Get real user profile data: ratings, preferences, import history.

    A user can only read their own profile via this endpoint. Cached for
    30 min per user; invalidated when the user adds a rating.
    """
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile",
        )

    # Cache hit — skip the DB query + 200 TMDB resolves entirely.
    cached = _admin_profile_cache.get(_admin_cache_key(user_id))
    if cached:
        return cached

    from src.services.user_service import get_user_service
    from src.services.job_service import get_job_service

    user_service = get_user_service()
    job_service = get_job_service()

    # Get stored profile
    profile_data = user_service.get_user_profile(user_id)

    # Get ratings (most recent first) and resolve movie titles in parallel
    # so users with large imported libraries (e.g. ~800 Letterboxd ratings)
    # don't time out the endpoint while the Lambda /tmp TMDB cache warms.
    ratings = user_service.get_user_ratings(user_id)
    LIMIT = 200
    head = ratings[:LIMIT]

    try:
        from src.services.movie_service import get_movie_service
        movie_service = get_movie_service()
        ids = [int(r["movie_id"]) for r in head]
        # Parallel batch fetch with TV fallback — Letterboxd ratings are all
        # movies, but recommendation feedback can be for either. media_type
        # is captured per rating so the Films / Series tabs can split them.
        movies = movie_service.get_media_auto_batch(ids, max_workers=10)
        for r, movie in zip(head, movies):
            if movie:
                r["title"] = movie.metadata.title
                r["year"] = movie.metadata.year
                r["media_type"] = movie.metadata.media_type or "movie"
                r["poster_path"] = movie.metadata.poster_path
            else:
                r["title"] = f"Movie {r['movie_id']}"
                r["year"] = None
                r["media_type"] = "movie"
                r["poster_path"] = None
    except Exception as e:
        logger.warning(f"Failed to resolve movie titles: {e}")
        # Soft-fail: return ratings without titles rather than 500-ing.
        for r in head:
            r.setdefault("title", f"Movie {r['movie_id']}")
            r.setdefault("year", None)
            r.setdefault("media_type", "movie")
            r.setdefault("poster_path", None)

    # Get import/job history
    jobs = job_service.get_user_jobs(user_id, limit=10)

    # Check for running jobs
    running_jobs = [j for j in jobs if j["status"] in ("pending", "running")]

    # Build response
    result = {
        "user_id": user_id,
        "profile": profile_data,
        "total_ratings": len(ratings),
        "recent_ratings": head,
        "jobs": jobs,
        "has_running_job": len(running_jobs) > 0,
        "profile_status": "active" if profile_data else "none",
    }

    # Extract preferences if profile exists
    if profile_data and isinstance(profile_data, dict):
        result["preferences"] = profile_data.get("preferences", {})
        result["temporal_patterns"] = profile_data.get("temporal_patterns", {})
        result["is_cold_start"] = profile_data.get("is_cold_start", True)
        result["avg_rating_given"] = profile_data.get("avg_rating_given")
    else:
        result["preferences"] = {}
        result["temporal_patterns"] = {}
        result["is_cold_start"] = True
        result["avg_rating_given"] = None

    _admin_profile_cache.set(
        _admin_cache_key(user_id), result, expire=_ADMIN_PROFILE_TTL
    )
    return result
