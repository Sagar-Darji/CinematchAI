"""Profile API — the new endpoints powering the rewritten Profile page.

Four endpoints expose the precomputed `user_stats.profile_payload` blob
plus paginated live queries for the parts the blob intentionally doesn't
hold (recently-watched diary, Films/Series library grids).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_current_user
from src.services.profile_service import get_profile_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


def _require_self(current_user: str, user_id: str) -> None:
    if current_user != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile",
        )


@router.get("/core/{user_id}", status_code=status.HTTP_200_OK)
async def get_profile_core(
    user_id: str,
    current_user: str = Depends(get_current_user),
):
    """Header-only payload — fast first paint. Returns identity (avatar,
    username, banner, stat chips, rotating captions), favorites, live
    film count, and computed_at + is_stale flags. Always 200 (even for
    cold-start users) so the page can render an empty-state CTA without
    hitting an error branch."""
    _require_self(current_user, user_id)
    return get_profile_service().get_core(user_id)


@router.get("/analytics/{user_id}", status_code=status.HTTP_200_OK)
async def get_profile_analytics(
    user_id: str,
    current_user: str = Depends(get_current_user),
):
    """The precomputed Profile artifact — overview + diary blob. Returns
    `{status: "missing"|"pending"|"ok", payload, computed_at}` so the
    frontend can branch without an error path."""
    _require_self(current_user, user_id)
    return get_profile_service().get_analytics(user_id)


@router.get("/diary/{user_id}", status_code=status.HTTP_200_OK)
async def get_profile_diary(
    user_id: str,
    cursor: Optional[str] = Query(default=None, description="Timestamp of the last item on the previous page (ISO)"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: str = Depends(get_current_user),
):
    """Paginated recently-watched timeline. Cursor-based: send back the
    `next_cursor` from the previous response to keep paging. Excludes
    implicit-feedback rows."""
    _require_self(current_user, user_id)
    return get_profile_service().get_diary(user_id, cursor=cursor, limit=limit)


@router.get("/library/{user_id}", status_code=status.HTTP_200_OK)
async def get_profile_library(
    user_id: str,
    media_type: str = Query(default="movie", pattern=r"^(movie|tv)$"),
    sort: str = Query(default="date_watched", pattern=r"^(rating|date_watched|title|year)$"),
    genres: Optional[str] = Query(default=None, description="Comma-separated genre names"),
    decades: Optional[str] = Query(default=None, description="Comma-separated decade integers, e.g. 2010,2020"),
    q: Optional[str] = Query(default=None, description="Title search query (substring, case-insensitive)"),
    cursor: Optional[int] = Query(default=None, ge=0, description="Offset into the result set"),
    limit: int = Query(default=60, ge=1, le=200),
    current_user: str = Depends(get_current_user),
):
    """Films / Series tab data. Server-side sort + filter + search so
    we don't ship the whole library to the browser."""
    _require_self(current_user, user_id)
    genre_list: Optional[List[str]] = (
        [g.strip() for g in genres.split(",") if g.strip()] if genres else None
    )
    decade_list: Optional[List[int]] = None
    if decades:
        try:
            decade_list = [int(d.strip()) for d in decades.split(",") if d.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="decades must be comma-separated integers",
            )
    return get_profile_service().get_library(
        user_id=user_id,
        media_type=media_type,
        sort=sort,
        genres=genre_list,
        decades=decade_list,
        q=q,
        cursor=cursor,
        limit=limit,
    )


@router.post("/{user_id}/recompute", status_code=status.HTTP_202_ACCEPTED)
async def recompute_profile(
    user_id: str,
    current_user: str = Depends(get_current_user),
):
    """Manual 'Regenerate analytics' button on Settings. Marks the blob
    stale + dispatches a fresh compute. Throttled to once per 90s per
    user (see should_throttle_trigger)."""
    _require_self(current_user, user_id)
    get_profile_service().recompute(user_id)
    return {"status": "scheduled", "user_id": user_id}
