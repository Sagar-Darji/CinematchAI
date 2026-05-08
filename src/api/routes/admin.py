"""Admin API routes - System monitoring and user inspection."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_current_user
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


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

    A user can only read their own profile via this endpoint.
    """
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile",
        )
    from src.services.user_service import get_user_service
    from src.services.job_service import get_job_service

    user_service = get_user_service()
    job_service = get_job_service()

    # Get stored profile
    profile_data = user_service.get_user_profile(user_id)

    # Get ratings and resolve movie names
    ratings = user_service.get_user_ratings(user_id)

    # Resolve movie titles from TMDB (cached)
    try:
        from src.services.movie_service import get_movie_service
        movie_service = get_movie_service()
        for r in ratings[:20]:  # Only resolve the ones we'll return
            try:
                movie = movie_service.get_movie_by_id(tmdb_id=int(r["movie_id"]))
                if movie:
                    r["title"] = movie.metadata.title
                    r["year"] = movie.metadata.year
                else:
                    r["title"] = f"Unknown ({r['movie_id']})"
                    r["year"] = None
            except Exception:
                r["title"] = f"Movie {r['movie_id']}"
                r["year"] = None
    except Exception as e:
        logger.warning(f"Failed to resolve movie titles: {e}")

    # Get import/job history
    jobs = job_service.get_user_jobs(user_id, limit=10)

    # Check for running jobs
    running_jobs = [j for j in jobs if j["status"] in ("pending", "running")]

    # Build response
    result = {
        "user_id": user_id,
        "profile": profile_data,
        "total_ratings": len(ratings),
        "recent_ratings": ratings[:20],
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

    return result
