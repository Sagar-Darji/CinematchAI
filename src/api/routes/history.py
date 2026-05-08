"""Watch history API routes — per-user 'continue watching' state."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.services.history_service import get_history_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/history", tags=["history"])


class HistoryItemIn(BaseModel):
    tmdb_id: int = Field(..., ge=1)
    media_type: str = Field(..., pattern=r"^(movie|tv)$")
    title: str
    poster_path: Optional[str] = None
    year: Optional[int] = None
    last_season: Optional[int] = Field(default=None, ge=1)
    last_episode: Optional[int] = Field(default=None, ge=1)


@router.get("", status_code=status.HTTP_200_OK)
async def list_history(
    limit: int = Query(default=60, ge=1, le=200),
    current_user: str = Depends(get_current_user),
):
    """Return the current user's watch history, most-recent first."""
    items = get_history_service().list(current_user, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def record_history(
    item: HistoryItemIn,
    current_user: str = Depends(get_current_user),
):
    """Record (upsert) a watch event. For TV, last_season/last_episode are
    persisted so the player can resume at the right episode."""
    try:
        get_history_service().record(
            user_id=current_user,
            tmdb_id=item.tmdb_id,
            media_type=item.media_type,
            title=item.title,
            poster_path=item.poster_path,
            year=item.year,
            last_season=item.last_season,
            last_episode=item.last_episode,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}


@router.delete("/{media_type}/{tmdb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_history(
    media_type: str,
    tmdb_id: int,
    current_user: str = Depends(get_current_user),
):
    """Remove a single title from history."""
    if media_type not in ("movie", "tv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_type must be movie or tv",
        )
    get_history_service().remove(current_user, tmdb_id, media_type)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(current_user: str = Depends(get_current_user)):
    """Clear the current user's watch history entirely."""
    get_history_service().clear(current_user)
