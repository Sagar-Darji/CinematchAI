"""Watchlist API routes — per-user save-for-later list."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.services.watchlist_service import get_watchlist_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItemIn(BaseModel):
    tmdb_id: int = Field(..., ge=1)
    media_type: str = Field(..., pattern=r"^(movie|tv)$")
    title: str
    poster_path: Optional[str] = None
    year: Optional[int] = None


@router.get("", status_code=status.HTTP_200_OK)
async def list_watchlist(current_user: str = Depends(get_current_user)):
    """Return the current user's watchlist, ordered by recency."""
    items = get_watchlist_service().list(current_user)
    return {"items": items, "count": len(items)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    item: WatchlistItemIn,
    current_user: str = Depends(get_current_user),
):
    """Add a title to the current user's watchlist (or refresh added_at)."""
    try:
        get_watchlist_service().add(
            user_id=current_user,
            tmdb_id=item.tmdb_id,
            media_type=item.media_type,
            title=item.title,
            poster_path=item.poster_path,
            year=item.year,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}


@router.delete("/{media_type}/{tmdb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    media_type: str,
    tmdb_id: int,
    current_user: str = Depends(get_current_user),
):
    """Remove a title from the current user's watchlist."""
    if media_type not in ("movie", "tv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_type must be movie or tv",
        )
    get_watchlist_service().remove(current_user, tmdb_id, media_type)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_watchlist(current_user: str = Depends(get_current_user)):
    """Clear the entire watchlist for the current user."""
    get_watchlist_service().clear(current_user)
