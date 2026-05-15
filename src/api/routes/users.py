"""User Management API Routes."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.api.schemas.request import (
    FeedbackRequest,
    LetterboxdImportRequest,
    OnboardingRequest,
    UpdateContextRequest,
)
from src.api.schemas.response import (
    ErrorResponse,
    FavoriteItem,
    FavoritesResponse,
    FeedbackResponse,
    LetterboxdImportResponse,
    OnboardingResponse,
)
from src.services.job_service import JobStatus, JobType, get_job_service
from src.services.onboarding_service import get_onboarding_service
from src.services.user_service import get_user_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/onboard",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def onboard_user(
    request: OnboardingRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Onboard the current user (cold-start).

    - **ratings**: Initial ratings (movie_id -> rating). Min 5 required.
    - **preferences**: Optional explicit preferences (favorite_genres, etc.)

    The user_id is taken from the authenticated session, NOT the request body.
    Creates a user profile and returns initial recommendations.
    """
    logger.info(
        f"POST /users/onboard: user_id={current_user}, {len(request.ratings)} ratings"
    )

    try:
        service = get_onboarding_service()

        response = service.onboard_user(
            user_id=current_user,
            ratings=request.ratings,
            preferences=request.preferences,
        )

        return response

    except ValueError as e:
        logger.warning(f"Invalid onboarding request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to onboard user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to onboard user",
        )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Submit a rating for the current user.

    - **movie_id**: Movie TMDB ID
    - **rating**: Rating value (0.5 to 5.0)
    - **watched**: Whether user watched the movie (default: True)

    The user_id is taken from the authenticated session, NOT the request body.
    """
    logger.info(
        f"POST /users/feedback: user_id={current_user}, movie_id={request.movie_id}, rating={request.rating}"
    )

    try:
        user_service = get_user_service()

        user_service.add_rating(
            user_id=current_user,
            movie_id=request.movie_id,
            rating=request.rating,
            watched=request.watched,
        )

        response = FeedbackResponse(
            user_id=current_user,
            movie_id=request.movie_id,
            rating=request.rating,
            profile_updated=True,
            message="Rating saved successfully. Profile will be updated on next recommendation request.",
        )

        return response

    except ValueError as e:
        logger.warning(f"Invalid feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        )


@router.post(
    "/interaction",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={400: {"model": ErrorResponse}},
)
async def record_interaction(
    movie_id: str,
    action: str,
    current_user: str = Depends(get_current_user),
    user_id: str | None = None,  # accepted but ignored — auth source-of-truth is current_user
):
    """Record an implicit interaction signal (clicked / watched / dismissed).

    The user_id is taken from the authenticated session. The legacy `user_id`
    query parameter is accepted (for backward compatibility) but ignored.
    """
    _ = user_id  # explicitly unused
    if action not in ("clicked", "watched", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be one of: clicked, watched, dismissed",
        )
    try:
        get_user_service().record_feedback(user_id=current_user, movie_id=movie_id, action=action)
    except Exception as e:
        logger.warning(f"Interaction record failed (non-critical): {e}")


@router.get(
    "/onboarding-movies",
    status_code=status.HTTP_200_OK,
)
async def get_onboarding_movies(k: int = 20):
    """
    Get diverse popular movies for onboarding flow.

    - **k**: Number of movies (default: 20, max: 50)

    Returns a curated list of movies for new users to rate.
    """
    logger.info(f"GET /users/onboarding-movies: k={k}")

    if k > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum k=50",
        )

    try:
        service = get_onboarding_service()
        movies = service.get_onboarding_movies(k=k)

        return {"movies": movies, "count": len(movies)}

    except Exception as e:
        logger.error(f"Failed to get onboarding movies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get onboarding movies",
        )


@router.get(
    "/{user_id}/exists",
    status_code=status.HTTP_200_OK,
)
async def check_user_exists(user_id: str):
    """Check if user exists and has ratings."""
    user_service = get_user_service()
    ratings = user_service.get_user_ratings(user_id)
    
    return {
        "exists": len(ratings) > 0,
        "user_id": user_id,
        "total_ratings": len(ratings),
    }


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def get_user(user_id: str, current_user: str = Depends(get_current_user)):
    """Get basic user profile: rating count, genre breakdown, embedding status.

    Only the authenticated user can read their own profile.
    """
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile",
        )
    user_service = get_user_service()
    ratings = user_service.get_user_ratings(user_id)

    # Build genre counts from ratings
    genres: dict[str, int] = {}
    try:
        from src.services.movie_service import get_movie_service
        movie_service = get_movie_service()
        for r in ratings[:50]:
            try:
                movie = movie_service.get_movie_by_id(int(r["movie_id"]))
                if movie:
                    for g in movie.metadata.genres or []:
                        genres[g] = genres.get(g, 0) + 1
            except Exception:
                pass
    except Exception:
        pass

    profile_data = user_service.get_user_profile(user_id)
    has_embedding = bool(profile_data and isinstance(profile_data, dict) and profile_data.get("embedding"))

    return {
        "user_id": user_id,
        "total_ratings": len(ratings),
        "genres": genres,
        "embedding_ready": has_embedding,
        "is_cold_start": len(ratings) < 5,
        "avatar_url": user_service.get_avatar_url(user_id),
    }


@router.post("/{user_id}/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    user_id: str,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
):
    """Upload a profile picture. Resized to 256×256 JPEG and stored in S3;
    we persist a 7-day presigned URL on the user row."""
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own avatar",
        )
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    body = await file.read()
    from src.services.avatar_service import get_avatar_service
    try:
        url = get_avatar_service().upload(user_id=current_user, image_bytes=body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Avatar upload failed for {current_user}: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload avatar")

    get_user_service().set_avatar_url(current_user, url)
    return {"avatar_url": url}


@router.delete("/{user_id}/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    user_id: str,
    current_user: str = Depends(get_current_user),
):
    """Remove the user's avatar (S3 object + DB column)."""
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own avatar",
        )
    from src.services.avatar_service import get_avatar_service
    get_avatar_service().delete(current_user)
    get_user_service().set_avatar_url(current_user, None)


@router.get("/{user_id}/stats", status_code=status.HTTP_200_OK)
async def get_user_stats(user_id: str, current_user: str = Depends(get_current_user)):
    """Persisted analytics for the Profile page.

    Pure DB read — no compute, no TMDB resolves. If the row is missing or
    stale we kick off a background recompute via Lambda self-invoke and
    return whatever's currently stored (or a placeholder if nothing yet).

    Throttled: we never dispatch a worker more than once per
    STATS_TRIGGER_THROTTLE_SEC per user. Polling the endpoint at 4s
    intervals previously triggered a thundering-herd of overlapping
    workers all racing to write the same row.
    """
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own stats",
        )
    from src.services.stats_service import (
        get_stats_service,
        invoke_stats_worker,
        should_throttle_trigger,
        mark_trigger,
    )

    svc = get_stats_service()
    row = svc.get(user_id)
    if row is None:
        # First request — kick off compute (subject to throttle), return
        # placeholder.
        if not should_throttle_trigger(user_id):
            mark_trigger(user_id)
            invoke_stats_worker(user_id)
        return {
            "user_id": user_id,
            "computing": True,
            "stats": None,
            "computed_at": None,
        }

    if row.get("stale") and not should_throttle_trigger(user_id):
        mark_trigger(user_id)
        invoke_stats_worker(user_id)

    return {
        "user_id": user_id,
        "computing": bool(row.get("stale")),
        "stats": row,
        "computed_at": row.get("computed_at"),
    }


@router.post("/{user_id}/stats/recompute", status_code=status.HTTP_202_ACCEPTED)
async def recompute_user_stats(user_id: str, current_user: str = Depends(get_current_user)):
    """Mark stats as stale and dispatch a fresh compute job. Returns 202."""
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only recompute your own stats",
        )
    from src.services.stats_service import get_stats_service, invoke_stats_worker

    get_stats_service().mark_stale(user_id)
    invoke_stats_worker(user_id)
    return {"status": "queued", "user_id": user_id}


@router.get(
    "/{user_id}/ratings",
    status_code=status.HTTP_200_OK,
)
async def list_user_ratings(
    user_id: str,
    media_type: str = "all",
    sort: str = "date_desc",
    page: int = 1,
    limit: int = 24,
    q: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """Paginated, sortable list of a user's ratings — Films + Series tabs.

    Args:
        media_type: "movie" | "tv" | "all".
        sort: date_desc | date_asc | rating_desc | rating_asc | title_asc.
        page: 1-based page index.
        limit: page size (max 60).

    Drives the Profile page's Films / Series tabs. Reuses the cached admin
    profile response (30 min TTL) so repeated paging is instant — only the
    first request after the cache expires does the DB + TMDB resolve.
    """
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own ratings",
        )
    if media_type not in ("all", "movie", "tv"):
        raise HTTPException(status_code=400, detail="media_type must be all|movie|tv")
    if sort not in ("date_desc", "date_asc", "rating_desc", "rating_asc", "title_asc"):
        raise HTTPException(status_code=400, detail="invalid sort")
    if page < 1 or limit < 1 or limit > 60:
        raise HTTPException(status_code=400, detail="invalid pagination")

    # Reuse the admin profile cache so we don't pay for the DB query +
    # TMDB resolve on every page change. Pull the resolved ratings from
    # there (the admin endpoint's loop populates title / media_type /
    # poster_path on each rating dict).
    from src.api.routes.admin import _admin_profile_cache, _admin_cache_key
    cached = _admin_profile_cache.get(_admin_cache_key(user_id))
    if cached and "recent_ratings" in cached:
        ratings = list(cached["recent_ratings"])
    else:
        # Fall back to building it inline — same logic as the admin
        # endpoint, just inlined to avoid an HTTP self-call.
        from src.services.user_service import get_user_service
        from src.services.movie_service import get_movie_service
        all_ratings = get_user_service().get_user_ratings(user_id)
        head = all_ratings[:200]
        try:
            ids = [int(r["movie_id"]) for r in head]
            movies = get_movie_service().get_media_auto_batch(ids, max_workers=10)
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
        except Exception as exc:
            logger.warning(f"Failed to resolve ratings for {user_id}: {exc}")
        ratings = head

    # Filter
    if media_type != "all":
        ratings = [r for r in ratings if r.get("media_type") == media_type]

    # Search — case-insensitive substring on title.
    if q:
        needle = q.strip().lower()
        if needle:
            ratings = [
                r for r in ratings
                if needle in (r.get("title") or "").lower()
            ]

    # Sort
    if sort == "date_desc":
        ratings.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    elif sort == "date_asc":
        ratings.sort(key=lambda r: r.get("timestamp") or "")
    elif sort == "rating_desc":
        ratings.sort(key=lambda r: (r.get("rating") or 0), reverse=True)
    elif sort == "rating_asc":
        ratings.sort(key=lambda r: (r.get("rating") or 0))
    elif sort == "title_asc":
        ratings.sort(key=lambda r: (r.get("title") or "").lower())

    total = len(ratings)
    start = (page - 1) * limit
    end = start + limit
    items = ratings[start:end]
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": end < total,
    }


class SetFavoritesRequest(BaseModel):
    items: List[FavoriteItem] = Field(default_factory=list, max_length=4)


@router.get(
    "/{user_id}/favorites",
    response_model=FavoritesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_favorites(user_id: str, current_user: str = Depends(get_current_user)):
    """Return the user's pinned favorites (up to 4 movies/TV shows)."""
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own favorites",
        )
    items = get_user_service().get_favorites(user_id)
    return {"items": items}


@router.put(
    "/{user_id}/favorites",
    response_model=FavoritesResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def set_favorites(
    user_id: str,
    request: SetFavoritesRequest,
    current_user: str = Depends(get_current_user),
):
    """Replace the user's pinned favorites list. Max 4 items."""
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own favorites",
        )
    try:
        items = get_user_service().set_favorites(
            user_id, [item.model_dump() for item in request.items]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"items": items}


@router.put(
    "/{user_id}/context",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def update_context(
    user_id: str,
    request: UpdateContextRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Update user's current context.

    Only the authenticated user can update their own context.
    """
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own context",
        )

    logger.info(f"PUT /users/{user_id}/context: {request.context}")

    try:
        user_service = get_user_service()

        user_service.update_context(
            user_id=current_user,
            context=request.context,
        )

        return {"message": "Context updated successfully", "user_id": user_id}

    except Exception as e:
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update context",
        )


@router.post(
    "/import/letterboxd",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def import_letterboxd(
    request: LetterboxdImportRequest,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user),
):
    """
    Import user ratings from Letterboxd CSV export (ASYNC).

    - **user_id**: User identifier
    - **csv_content**: Letterboxd CSV export file content

    **Returns immediately (202 Accepted) with job_id.**
    Use GET /users/jobs/{job_id} to check progress.

    **Production-grade async processing:**
    - Immediate response (no timeout)
    - Progress tracking
    - Handles 100s of ratings without blocking
    """
    logger.info(f"POST /users/import/letterboxd: user_id={current_user}")

    try:
        import pandas as pd
        from io import StringIO

        # Parse CSV to get total count
        df = pd.read_csv(StringIO(request.csv_content))
        rated_df = df[df["Rating"].notna()]
        total_movies = len(rated_df)

        # Create job
        job_service = get_job_service()
        job_id = job_service.create_job(
            job_type=JobType.LETTERBOXD_IMPORT,
            user_id=current_user,
            total=total_movies,
        )

        # Dispatch the import to a separate Lambda container (event-style
        # self-invoke). Previously this used FastAPI BackgroundTasks, which
        # holds the request Lambda for the entire ~3-minute import — every
        # subsequent client request to the same warm container then hit the
        # API Gateway 30s integration timeout and returned 503 "Service
        # Unavailable". Self-invoke gives the worker its own container so
        # the request handler returns in <200ms.
        from src.api.routes.users import _dispatch_letterboxd_worker  # local helper, see below
        try:
            _dispatch_letterboxd_worker(job_id, current_user, request.csv_content)
        except Exception as e:
            # Local dev or missing IAM: fall back to FastAPI BackgroundTasks so
            # imports still work outside Lambda.
            logger.warning(f"Lambda self-invoke unavailable ({e}); falling back to BackgroundTasks")
            background_tasks.add_task(
                _import_letterboxd_background,
                job_id=job_id,
                user_id=current_user,
                csv_content=request.csv_content,
            )

        logger.info(f"Created Letterboxd import job {job_id} for user {current_user} ({total_movies} movies)")

        return {
            "job_id": job_id,
            "user_id": current_user,
            "total_movies": total_movies,
            "status": "pending",
            "message": f"Import started. Poll GET /api/v1/users/jobs/{job_id} for status.",
            "poll_url": f"/api/v1/users/jobs/{job_id}",
        }

    except ValueError as e:
        logger.warning(f"Invalid Letterboxd CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to start Letterboxd import: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start import",
        )


def _dispatch_letterboxd_worker(job_id: str, user_id: str, csv_content: str) -> None:
    """Fire-and-forget Lambda Event invocation that runs the import on a
    fresh container. Raises if AWS credentials / LAMBDA_DEPLOYMENT aren't
    set so the caller can fall back to in-process execution for local dev.
    """
    import json
    import os

    if not os.environ.get("LAMBDA_DEPLOYMENT"):
        raise RuntimeError("Not running on Lambda — skipping self-invoke")

    import boto3
    lambda_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get(
        "LAMBDA_FUNCTION_NAME", "cinematch-api"
    )
    client = boto3.client("lambda", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    payload = {
        "source": "letterboxd-worker",
        "job_id": job_id,
        "user_id": user_id,
        "csv_content": csv_content,
    }
    client.invoke(
        FunctionName=lambda_name,
        InvocationType="Event",
        Payload=json.dumps(payload).encode(),
    )
    logger.info(f"Dispatched letterboxd-worker for job {job_id}")


def _import_letterboxd_background(job_id: str, user_id: str, csv_content: str):
    """Background task for Letterboxd import."""
    from src.services.letterboxd_service import get_letterboxd_service

    job_service = get_job_service()

    try:
        # Update status to running
        job_service.update_job_status(job_id, JobStatus.RUNNING, progress=0)

        logger.info(f"🎬 Starting Letterboxd import for job {job_id}")

        # Run import with progress callback
        service = get_letterboxd_service()

        def progress_callback(current: int, total: int):
            """Progress callback for job tracking."""
            progress = int((current / total) * 100)
            job_service.update_job_status(job_id, JobStatus.RUNNING, progress=progress)
            logger.info(f"Job {job_id}: {current}/{total} ({progress}%)")

        result = service.import_from_csv(
            user_id=user_id,
            csv_content=csv_content,
            progress_callback=progress_callback,
        )

        # CRITICAL: Force profile regeneration after import
        logger.info(f"🔄 Triggering profile regeneration for user {user_id}")
        try:
            from src.agents.graph.workflow import run_recommendation_workflow

            # Run workflow once to generate profile (discard recommendations)
            run_recommendation_workflow(
                user_id=user_id,
                context={},
                is_cold_start=False,
            )
            logger.info(f"✅ Profile regenerated for user {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ Profile regeneration failed (non-critical): {e}")

        # Persisted analytics — mark stale and dispatch a background
        # recompute so the Profile page picks up the import.
        try:
            from src.services.stats_service import get_stats_service, invoke_stats_worker
            get_stats_service().mark_stale(user_id)
            invoke_stats_worker(user_id)
        except Exception as e:
            logger.warning(f"⚠️ Stats recompute dispatch failed (non-critical): {e}")

        # Update result
        job_service.update_job_result(job_id, result)
        job_service.update_job_status(job_id, JobStatus.COMPLETED, progress=100)

        logger.info(
            f"✅ Completed Letterboxd import for job {job_id}: "
            f"{result['imported_count']}/{result['total_movies']} imported "
            f"({result['success_rate']*100:.1f}% success rate)"
        )

    except Exception as e:
        logger.error(f"❌ Failed Letterboxd import for job {job_id}: {e}", exc_info=True)
        job_service.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e),
        )


@router.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
)
async def get_job_status(job_id: str, current_user: str = Depends(get_current_user)):
    """
    Get job status by ID. Only the job's owner may poll it.

    Returns job status, progress (0-100), and result (if completed).
    Poll this endpoint every 2-3 seconds to track progress.
    """
    logger.debug(f"GET /users/jobs/{job_id}")

    job_service = get_job_service()
    job = job_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Only the owner can read their job. Treat 'no owner recorded' as legacy/public.
    job_user = job.get("user_id") if isinstance(job, dict) else None
    if job_user and job_user != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own jobs",
        )

    return job
