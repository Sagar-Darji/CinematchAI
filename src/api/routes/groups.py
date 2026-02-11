"""Group Recommendation API Routes."""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.request import GroupRecommendationRequest
from src.api.schemas.response import ErrorResponse, GroupRecommendationResponse
from src.services.recommendation_service import get_recommendation_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post(
    "/recommendations",
    response_model=GroupRecommendationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_group_recommendations(request: GroupRecommendationRequest):
    """
    Get movie recommendations for a group of users with fairness optimization.

    - **user_ids**: List of user IDs (min 2)
    - **context**: Optional shared context
    - **aggregation_strategy**: Strategy for combining preferences:
        - `multiplicative`: Balanced approach (default)
        - `least_misery`: Maximize minimum satisfaction
        - `average`: Simple averaging
    - **k**: Number of recommendations (default: 10, max: 50)

    Returns group recommendations with fairness score and per-user satisfaction.
    """
    logger.info(
        f"POST /groups/recommendations: {len(request.user_ids)} users, strategy={request.aggregation_strategy}"
    )

    if len(request.user_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 user IDs required for group recommendations",
        )

    try:
        service = get_recommendation_service()

        response = service.get_group_recommendations(
            user_ids=request.user_ids,
            context=request.context,
            aggregation_strategy=request.aggregation_strategy,
            k=request.k,
        )

        return response

    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get group recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate group recommendations",
        )
