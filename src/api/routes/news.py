"""CineDigest API routes — movie news aggregator."""

from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from src.services import news_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

CategoryFilter = Literal["all", "bollywood", "hollywood", "trailer", "casting", "leak", "ott", "general"]
LangFilter = Literal["all", "hindi", "english"]


@router.get("/digest", status_code=status.HTTP_200_OK)
async def get_digest(
    category: CategoryFilter = Query("all", description="Filter by category"),
    lang: LangFilter = Query("all", description="Filter by language"),
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Return paginated movie news digest, newest first."""
    items = news_service.get_digest(
        category=category if category != "all" else None,
        lang=lang if lang != "all" else None,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": len(items),
        "last_refresh": news_service.get_last_refresh(),
    }


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
async def trigger_refresh(background_tasks: BackgroundTasks):
    """Manually trigger a news refresh (runs in background)."""
    background_tasks.add_task(_do_refresh)
    return {"status": "refresh_started"}


def _do_refresh() -> None:
    try:
        n = news_service.refresh_news()
        news_service._mark_refresh()
        logger.info("Manual CineDigest refresh: %d new items", n)
    except Exception as exc:
        logger.error("Manual refresh failed: %s", exc)
