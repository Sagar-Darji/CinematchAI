"""User Management API Routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.api.schemas.request import (
    FeedbackRequest,
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
    file: UploadFile = File(..., description="Letterboxd export .zip OR raw ratings.csv"),
    current_user: str = Depends(get_current_user),
):
    """Import a Letterboxd library (full ZIP or bare ratings.csv).

    For ZIP uploads we extract ratings.csv (required), then overlay
    diary.csv's `Watched Date` onto each rating's timestamp so the
    Profile's heatmap + 'films this year' reflect the actual watch
    dates. We also stage reviews.csv, watchlist.csv, watched.csv and
    likes/films.csv for the chunk worker to ingest after the ratings
    phase.

    For bare CSV uploads (back-compat) we treat the upload as ratings.csv
    only — the legacy single-file path.

    Returns 202 with a job_id. Poll GET /users/jobs/{job_id} for progress.
    """
    logger.info(
        f"POST /users/import/letterboxd: user_id={current_user} filename={file.filename!r} "
        f"content_type={file.content_type!r}"
    )

    try:
        import pandas as pd
        from io import StringIO
        from datetime import datetime as _dt

        raw = await file.read()
        if not raw:
            raise ValueError("Uploaded file is empty.")

        filename = (file.filename or "").lower()
        # Detect ZIP by magic bytes — content_type alone is unreliable from
        # browsers / curl. PK\x03\x04 is the ZIP local-file-header signature.
        is_zip = raw[:4] == b"PK\x03\x04" or filename.endswith(".zip")

        extras_payload: Optional[dict] = None
        if is_zip:
            from src.services.letterboxd_service import get_letterboxd_service
            extracted = get_letterboxd_service().extract_zip_export(raw)
            csv_text = extracted.get("merged_ratings_csv")
            if not csv_text:
                raise ValueError(
                    "ZIP did not contain ratings.csv. Make sure you uploaded the "
                    "Letterboxd export ZIP unmodified."
                )
            extras_payload = {
                "reviews":   extracted.get("reviews", []),
                "watchlist": extracted.get("watchlist", []),
                "watched":   extracted.get("watched", []),
                "likes":     extracted.get("likes", []),
                "diary_count": extracted.get("diary_count", 0),
            }
            logger.info(
                f"ZIP extracted: {extracted.get('ratings_count', 0)} ratings, "
                f"{extracted.get('diary_count', 0)} diary overlays, "
                f"{len(extras_payload['reviews'])} reviews, "
                f"{len(extras_payload['watchlist'])} watchlist, "
                f"{len(extras_payload['likes'])} likes"
            )
        else:
            # Bare CSV upload. Decode best-effort; reject if not UTF-8-ish.
            try:
                csv_text = raw.decode("utf-8")
            except UnicodeDecodeError:
                csv_text = raw.decode("latin-1", errors="replace")

        # Parse CSV to get total count
        df = pd.read_csv(StringIO(csv_text))
        rated_df = df[df["Rating"].notna()]
        total_movies = len(rated_df)
        if total_movies == 0:
            raise ValueError("CSV has no rated rows. Make sure you uploaded ratings.csv or the full Letterboxd ZIP.")

        # Single-flight guard: if a Letterboxd import for this user is
        # already in flight (or recently stuck), return its job_id and
        # re-dispatch a chunk worker so it resumes from where it stopped.
        # No new job, no duplicate workers, no TMDB rate-limit fights.
        job_service = get_job_service()
        recent = job_service.get_user_jobs(
            current_user, job_type=JobType.LETTERBOXD_IMPORT, limit=5
        )
        for j in recent:
            if j.get("status") in ("pending", "running"):
                started = j.get("created_at")
                if started:
                    try:
                        age = (_dt.utcnow() - _dt.fromisoformat(started.replace("Z", ""))).total_seconds()
                    except Exception:
                        age = 0
                    if age < 600:
                        logger.info(
                            f"Letterboxd import already running for user {current_user} "
                            f"(job {j['job_id']}, age {int(age)}s) — resuming existing job"
                        )
                        # Re-poke the worker so a stuck job picks up again
                        # from next_chunk_index. Lambda Event invokes are
                        # cheap (~30 ms); the chunk worker is idempotent and
                        # will exit immediately if the job is already done.
                        try:
                            _dispatch_letterboxd_chunk_worker(j["job_id"])
                        except Exception as e:
                            logger.warning(f"Resume self-invoke failed ({e}); will rely on existing worker")
                        return {
                            "job_id": j["job_id"],
                            "user_id": current_user,
                            "total_movies": j.get("total", total_movies),
                            "status": j.get("status", "running"),
                            "message": f"Resumed in-progress import. Poll GET /api/v1/users/jobs/{j['job_id']}.",
                            "poll_url": f"/api/v1/users/jobs/{j['job_id']}",
                        }

        # Stage the CSV in S3 so each chunk worker can stream just its slice
        # — keeps Lambda Event payloads tiny (under 1 KB) and lets workers
        # process any library size without blowing the 256 KB event limit.
        chunk_size = 50
        from src.services.import_staging_service import get_import_staging_service
        import uuid as _uuid
        # Pre-generate the job_id so the S3 key can use it. JobService will
        # accept it via create_job's return value.
        pre_job_id = str(_uuid.uuid4())
        try:
            staging = get_import_staging_service()
            s3_key = staging.put_csv(current_user, pre_job_id, csv_text)
            extras_s3_key: Optional[str] = None
            if extras_payload is not None:
                # Only stage extras when there's actually something to ingest
                # — empty sections waste an S3 round-trip on the worker side.
                if any(extras_payload.get(k) for k in ("reviews", "watchlist", "watched", "likes")):
                    extras_s3_key = staging.put_extras(current_user, pre_job_id, extras_payload)
        except Exception as e:
            logger.error(f"S3 staging upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not stage your CSV for processing. Please try again in a moment.",
            )

        job_id = job_service.create_job(
            job_type=JobType.LETTERBOXD_IMPORT,
            user_id=current_user,
            total=total_movies,
            s3_key=s3_key,
            chunk_size=chunk_size,
            extras_s3_key=extras_s3_key,
        )

        try:
            _dispatch_letterboxd_chunk_worker(job_id)
        except Exception as e:
            # Local dev or missing IAM: run the chunks in a daemon thread
            # instead of spinning a Lambda. Same code path, just in-process.
            logger.warning(f"Lambda self-invoke unavailable ({e}); running chunks in a thread")
            import threading
            threading.Thread(
                target=_run_chunk_loop_in_thread,
                args=(job_id,),
                daemon=True,
            ).start()

        logger.info(
            f"Created Letterboxd import job {job_id} for user {current_user} "
            f"({total_movies} movies, chunk_size={chunk_size}, s3_key={s3_key})"
        )

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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start Letterboxd import: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start import",
        )


def _dispatch_letterboxd_chunk_worker(job_id: str) -> None:
    """Fire-and-forget Lambda Event invocation that processes ONE chunk of
    a Letterboxd import. Payload is just `{source, job_id}` (< 1 KB) — the
    worker reads the CSV from S3 and the chunk position from the jobs
    table. Each chunk runs in well under the 300s Lambda ceiling; the
    chunk worker self-dispatches the next chunk on completion.

    Raises if not running on Lambda so the caller can fall back to the
    in-process daemon-thread loop for local dev.
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
    payload = {"source": "letterboxd-chunk", "job_id": job_id}
    client.invoke(
        FunctionName=lambda_name,
        InvocationType="Event",
        Payload=json.dumps(payload).encode(),
    )
    logger.info(f"Dispatched letterboxd-chunk for job {job_id}")


def process_letterboxd_chunk(job_id: str) -> None:
    """Process ONE chunk of a Letterboxd import, then either:
      - self-dispatch the next chunk (more rows remain), or
      - mark the job complete + kick off the stats recompute.

    Idempotent: if the job is already completed/failed, returns immediately.
    Safe to invoke twice for the same job_id concurrently — both will
    advance `next_chunk_index` past the row they processed.
    """
    from src.services.letterboxd_service import get_letterboxd_service
    from src.services.import_staging_service import get_import_staging_service

    job_service = get_job_service()
    job = job_service.get_job_status(job_id)
    if not job:
        logger.warning(f"chunk worker: job {job_id} not found, exiting")
        return
    if job["status"] in ("completed", "failed", "cancelled"):
        logger.info(f"chunk worker: job {job_id} already {job['status']}, no-op")
        return

    user_id = job["user_id"]
    s3_key = job.get("s3_key")
    chunk_size = job.get("chunk_size") or 50
    start = job.get("next_chunk_index") or 0
    total = job.get("total") or 0

    if not s3_key:
        logger.error(f"chunk worker: job {job_id} has no s3_key, marking failed")
        job_service.update_job_status(job_id, JobStatus.FAILED, error_message="Missing s3_key")
        return

    # Mark as running on first chunk so the UI flips from "pending" promptly.
    if job["status"] == "pending":
        job_service.update_job_status(job_id, JobStatus.RUNNING, progress=0)

    # Pull the CSV once per chunk. ~80 KB for an 800-row library, no big
    # deal; for larger libraries we could Range-read but it's not worth
    # the complexity yet.
    try:
        csv_content = get_import_staging_service().get_csv(s3_key)
    except Exception as e:
        logger.error(f"chunk worker: S3 fetch failed for job {job_id}: {e}")
        job_service.update_job_status(
            job_id, JobStatus.FAILED, error_message="Could not read staged CSV from S3"
        )
        return

    end = min(start + chunk_size, total) if total else start + chunk_size

    try:
        stats = get_letterboxd_service().import_chunk(
            user_id=user_id,
            csv_content=csv_content,
            start_row=start,
            end_row=end,
            skip_if_unchanged=True,
        )
    except Exception as e:
        logger.exception(f"chunk worker: chunk {start}-{end} for job {job_id} failed: {e}")
        # Don't mark the whole job FAILED on a single chunk error — the
        # next dispatch will retry. Only fail terminally if the same chunk
        # has failed twice in a row (would need DB tracking; skip for now).
        return

    processed = stats.get("processed", 0)
    if processed == 0:
        # Nothing left to process — wrap up.
        _mark_letterboxd_complete(job_id, user_id, s3_key, job.get("extras_s3_key"))
        return

    new_next = start + processed
    progress = int(min(100, (new_next / total) * 100)) if total else 0
    job_service.advance_chunk(job_id, new_next, progress)
    logger.info(
        f"chunk worker: job {job_id} chunk {start}-{end} done "
        f"({stats['imported']} ok / {stats['failed']} miss); next_chunk_index={new_next}/{total}"
    )

    if new_next >= total:
        _mark_letterboxd_complete(job_id, user_id, s3_key, job.get("extras_s3_key"))
        return

    # Self-chain. If this self-invoke fails (e.g. IAM blip), the job stays
    # at status=running with the advanced next_chunk_index — the next user
    # upload will trip the single-flight guard and re-dispatch from here.
    try:
        _dispatch_letterboxd_chunk_worker(job_id)
    except Exception as e:
        logger.warning(f"chunk worker: self-chain failed for job {job_id}: {e}")


def _mark_letterboxd_complete(
    job_id: str,
    user_id: str,
    s3_key: Optional[str],
    extras_s3_key: Optional[str] = None,
) -> None:
    """Wrap up a finished import: process ZIP extras (reviews/watchlist/
    likes/watched), mark COMPLETED, store result, fire stats recompute,
    delete the staged CSV + extras from S3."""
    job_service = get_job_service()

    # ── Extras pass — only when the upload was a full ZIP ───────────────
    if extras_s3_key:
        try:
            _process_letterboxd_extras(user_id, extras_s3_key)
        except Exception as exc:
            # Extras are nice-to-have, never block the ratings phase from
            # being marked complete. Logging the failure is enough.
            logger.warning(f"chunk worker: extras pass failed for job {job_id}: {exc}")

    job_service.update_job_status(job_id, JobStatus.COMPLETED, progress=100)
    job_service.update_job_result(job_id, {"status": "completed", "user_id": user_id})
    logger.info(f"chunk worker: job {job_id} COMPLETED")
    # Tell the stats job to recompute on next profile load.
    try:
        from src.services.stats_service import get_stats_service, invoke_stats_worker
        get_stats_service().mark_stale(user_id)
        invoke_stats_worker(user_id)
    except Exception as e:
        logger.warning(f"chunk worker: stats recompute trigger failed: {e}")
    # Best-effort cleanup of the staged CSV + extras — the 7-day S3
    # lifecycle rule is the backstop.
    from src.services.import_staging_service import get_import_staging_service
    staging = get_import_staging_service()
    for cleanup_key in (s3_key, extras_s3_key):
        if not cleanup_key:
            continue
        try:
            staging.delete(cleanup_key)
        except Exception as e:
            logger.warning(f"chunk worker: S3 cleanup failed for {cleanup_key}: {e}")


def _process_letterboxd_extras(user_id: str, extras_s3_key: str) -> None:
    """Pull the extras JSON for a finished import and write it to the
    relevant services: reviews → review_service, watchlist → watchlist_service,
    likes → favorites (capped at 4, only if the user has none set).

    Each item carries a `name` + `year` + `uri`; we resolve to a TMDB id
    using the same diskcache the chunk worker warmed during the ratings
    phase, so most lookups are sub-millisecond. Unresolved items are
    skipped with a debug log — they're surfaced again on the next import.
    """
    from src.services.import_staging_service import get_import_staging_service
    from src.services.letterboxd_service import get_letterboxd_service
    from src.services.review_service import get_review_service
    from src.services.watchlist_service import get_watchlist_service
    from src.services.movie_service import get_movie_service

    extras = get_import_staging_service().get_extras(extras_s3_key)
    lb = get_letterboxd_service()

    def _resolve(item: dict) -> Optional[int]:
        try:
            return lb._search_tmdb_movie(item.get("name") or "", item.get("year"))
        except Exception as exc:
            logger.debug(f"extras: TMDB resolve failed for {item.get('name')!r}: {exc}")
            return None

    # Reviews — only those with a non-empty review_text were emitted by the
    # ZIP extractor, so no filter needed.
    reviews = extras.get("reviews") or []
    if reviews:
        rsvc = get_review_service()
        ok = 0
        for r in reviews:
            tid = _resolve(r)
            if not tid:
                continue
            try:
                rsvc.upsert(
                    user_id=user_id,
                    tmdb_id=tid,
                    media_type="movie",  # Letterboxd is films only
                    rating=r.get("rating"),
                    review_text=r.get("review_text"),
                )
                ok += 1
            except Exception as exc:
                logger.debug(f"extras: review upsert failed ({r.get('name')!r}): {exc}")
        logger.info(f"extras: imported {ok}/{len(reviews)} reviews")

    # Watchlist
    watchlist = extras.get("watchlist") or []
    if watchlist:
        wsvc = get_watchlist_service()
        movie_svc = get_movie_service()
        ok = 0
        for w in watchlist:
            tid = _resolve(w)
            if not tid:
                continue
            try:
                media = movie_svc.get_media_auto(str(tid))
                md = getattr(media, "metadata", None) if media else None
                title = getattr(md, "title", None) or w.get("name") or "Untitled"
                poster = getattr(md, "poster_path", None)
                year = getattr(md, "year", None) or w.get("year")
                wsvc.add(
                    user_id=user_id,
                    tmdb_id=tid,
                    media_type="movie",
                    title=title,
                    poster_path=poster,
                    year=year,
                )
                ok += 1
            except Exception as exc:
                logger.debug(f"extras: watchlist add failed ({w.get('name')!r}): {exc}")
        logger.info(f"extras: imported {ok}/{len(watchlist)} watchlist entries")

    # Likes → favorites (capped at 4, only when user has no existing favs).
    likes = extras.get("likes") or []
    if likes:
        usvc = get_user_service()
        try:
            existing = usvc.get_favorites(user_id)
        except Exception:
            existing = []
        if not existing:
            movie_svc = get_movie_service()
            picked: List[dict] = []
            for lk in likes:
                if len(picked) >= 4:
                    break
                tid = _resolve(lk)
                if not tid:
                    continue
                try:
                    media = movie_svc.get_media_auto(str(tid))
                    md = getattr(media, "metadata", None) if media else None
                    picked.append({
                        "tmdb_id": int(tid),
                        "media_type": "movie",
                        "title": getattr(md, "title", None) or lk.get("name") or "Untitled",
                        "poster_path": getattr(md, "poster_path", None),
                    })
                except Exception:
                    picked.append({
                        "tmdb_id": int(tid),
                        "media_type": "movie",
                        "title": lk.get("name") or "Untitled",
                        "poster_path": None,
                    })
            if picked:
                try:
                    usvc.set_favorites(user_id, picked)
                    logger.info(f"extras: set {len(picked)} favorites from Letterboxd likes")
                except Exception as exc:
                    logger.debug(f"extras: set_favorites failed: {exc}")


def _run_chunk_loop_in_thread(job_id: str) -> None:
    """Local-dev fallback: run the chunk loop sequentially in a daemon
    thread so imports work without Lambda. Loops until status terminal."""
    while True:
        try:
            job = get_job_service().get_job_status(job_id)
        except Exception:
            return
        if not job or job["status"] in ("completed", "failed", "cancelled"):
            return
        try:
            process_letterboxd_chunk(job_id)
        except Exception as e:
            logger.warning(f"local chunk loop: {e}")
            return


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
