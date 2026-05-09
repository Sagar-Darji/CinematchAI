"""Reviews API routes — per-user star ratings + free-text reviews of titles."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.api.schemas.response import ReviewItem, ReviewsResponse
from src.services.review_service import get_review_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewIn(BaseModel):
    tmdb_id: int = Field(..., ge=1)
    media_type: str = Field(..., pattern=r"^(movie|tv)$")
    rating: Optional[float] = Field(default=None, ge=0.5, le=5.0)
    review_text: Optional[str] = Field(default=None, max_length=5000)


@router.post("", response_model=ReviewItem, status_code=status.HTTP_201_CREATED)
async def upsert_review(
    review: ReviewIn,
    current_user: str = Depends(get_current_user),
):
    """Create or update the current user's review of a title.

    At least one of `rating` or `review_text` must be set. rating is on a
    0.5–5.0 half-star scale.
    """
    try:
        result = get_review_service().upsert(
            user_id=current_user,
            tmdb_id=review.tmdb_id,
            media_type=review.media_type,
            rating=review.rating,
            review_text=review.review_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.get("/user/{user_id}", response_model=ReviewsResponse)
async def list_user_reviews(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: str = Depends(get_current_user),
):
    """Return the reviews authored by `user_id`. Currently only the user can
    read their own reviews — when public profiles ship, this will relax."""
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own reviews",
        )
    items = get_review_service().list_by_user(user_id, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@router.get("/movie/{tmdb_id}", response_model=Optional[ReviewItem])
async def get_my_review(
    tmdb_id: int,
    media_type: str = Query(default="movie", pattern=r"^(movie|tv)$"),
    current_user: str = Depends(get_current_user),
):
    """Return the current user's own review of a title (or null if none)."""
    return get_review_service().get(current_user, tmdb_id, media_type)


@router.delete("/{media_type}/{tmdb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    media_type: str,
    tmdb_id: int,
    current_user: str = Depends(get_current_user),
):
    """Delete the current user's review of a title."""
    if media_type not in ("movie", "tv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_type must be movie or tv",
        )
    get_review_service().delete(current_user, tmdb_id, media_type)
