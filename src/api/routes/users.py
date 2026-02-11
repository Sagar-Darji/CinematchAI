"""User Management API Routes."""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.request import (
    FeedbackRequest,
    OnboardingRequest,
    UpdateContextRequest,
)
from src.api.schemas.response import (
    ErrorResponse,
    FeedbackResponse,
    OnboardingResponse,
)
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
