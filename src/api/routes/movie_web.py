"""Movie Web API Route — GET /api/v1/movie-web/{movie_name}."""

from fastapi import APIRouter, HTTPException, Query, status

from src.services.movie_web_service import get_movie_web_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/movie-web", tags=["movie-web"])


@router.get(
    "/{movie_name}",
    status_code=status.HTTP_200_OK,
    summary="Get movie similarity graph",
    description=(
        "Returns a similarity graph centred on the given movie. "
        "Uses TMDB multi-signal candidate retrieval + LLM Cinematic Fingerprint re-scoring. "
        "Results are cached for 24 hours."
    ),
)
async def get_movie_web(
    movie_name: str,
    max_nodes: int = Query(
        default=35,
        ge=5,
        le=40,
        description="Maximum number of similar-movie nodes to return (5–40).",
    ),
):
    """Build and return the CineWeb similarity graph for *movie_name*."""
    logger.info(f"GET /movie-web/{movie_name}?max_nodes={max_nodes}")

    try:
        service = get_movie_web_service()
        result = service.get_movie_web(movie_name=movie_name, max_nodes=max_nodes)
    except Exception as exc:
        logger.error(f"Movie web generation failed for '{movie_name}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate movie similarity graph.",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie '{movie_name}' not found. Try a different title.",
        )

    return result
