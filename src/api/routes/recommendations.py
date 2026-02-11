"""Recommendation API Routes."""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.request import RecommendationRequest
from src.api.schemas.response import ErrorResponse, RecommendationResponse
from src.services.recommendation_service import get_recommendation_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "/",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_recommendations(request: RecommendationRequest):
    """
    Get personalized movie recommendations for a single user.

    - **user_id**: User identifier
    - **context**: Optional context (time_of_day, mood, companion, etc.)
    - **k**: Number of recommendations (default: 10, max: 50)
    - **use_hybrid**: Use hybrid text+image embeddings (default: True)

    Returns a list of personalized movie recommendations with explanations.
    """
    logger.info(f"POST /recommendations: user_id={request.user_id}, k={request.k}")

    try:
        service = get_recommendation_service()

        response = service.get_recommendations(
            user_id=request.user_id,
            context=request.context,
            k=request.k,
            use_hybrid=request.use_hybrid,
        )

        return response

    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations",
        )
