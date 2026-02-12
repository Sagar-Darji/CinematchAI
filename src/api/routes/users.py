"""User Management API Routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from src.api.schemas.request import (
    FeedbackRequest,
    LetterboxdImportRequest,
    OnboardingRequest,
    UpdateContextRequest,
)
from src.api.schemas.response import (
    ErrorResponse,
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
async def onboard_user(request: OnboardingRequest):
    """
    Onboard a new user (cold-start).

    - **user_id**: New user identifier
    - **ratings**: Initial ratings (movie_id -> rating). Min 5 required.
    - **preferences**: Optional explicit preferences (favorite_genres, etc.)

    Creates a user profile and returns initial recommendations.
    """
    logger.info(
        f"POST /users/onboard: user_id={request.user_id}, {len(request.ratings)} ratings"
    )

    try:
        service = get_onboarding_service()

        response = service.onboard_user(
            user_id=request.user_id,
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
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback (rating).

    - **user_id**: User identifier
    - **movie_id**: Movie TMDB ID
    - **rating**: Rating value (0.5 to 5.0)
    - **watched**: Whether user watched the movie (default: True)

    Updates user profile with new rating.
    """
    logger.info(
        f"POST /users/feedback: user_id={request.user_id}, movie_id={request.movie_id}, rating={request.rating}"
    )

    try:
        user_service = get_user_service()

        user_service.add_rating(
            user_id=request.user_id,
            movie_id=request.movie_id,
            rating=request.rating,
            watched=request.watched,
        )

        response = FeedbackResponse(
            user_id=request.user_id,
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


@router.put(
    "/{user_id}/context",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def update_context(user_id: str, request: UpdateContextRequest):
    """
    Update user's current context.

    - **user_id**: User identifier (path parameter)
    - **context**: Updated context (time_of_day, mood, companion, etc.)

    Updates user's context for future recommendations.
    """
    logger.info(f"PUT /users/{user_id}/context: {request.context}")

    try:
        user_service = get_user_service()

        user_service.update_context(
            user_id=request.user_id,
            context=request.context,
        )

        return {"message": "Context updated successfully", "user_id": user_id}

    except Exception as e:
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update context",
        )


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
    logger.info(f"POST /users/import/letterboxd: user_id={request.user_id}")

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
            user_id=request.user_id,
            total=total_movies,
        )

        # Run import in background
        background_tasks.add_task(
            _import_letterboxd_background,
            job_id=job_id,
            user_id=request.user_id,
            csv_content=request.csv_content,
        )

        logger.info(f"Created Letterboxd import job {job_id} for user {request.user_id} ({total_movies} movies)")

        return {
            "job_id": job_id,
            "user_id": request.user_id,
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
async def get_job_status(job_id: str):
    """
    Get job status by ID.

    - **job_id**: Job identifier

    Returns job status, progress (0-100), and result (if completed).

    **Poll this endpoint every 2-3 seconds to track progress.**
    """
    logger.debug(f"GET /users/jobs/{job_id}")

    job_service = get_job_service()
    job = job_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return job
