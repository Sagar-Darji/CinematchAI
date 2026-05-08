"""Recommendation API Routes."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from src.api.deps import get_current_user
from src.api.rate_limit import limiter
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
async def get_recommendations(
    request: RecommendationRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Get personalized movie recommendations for the current user.

    - **context**: Optional context (time_of_day, mood, companion, etc.)
    - **k**: Number of recommendations (default: 10, max: 50)
    - **use_hybrid**: Use hybrid text+image embeddings (default: True)

    The user_id is taken from the authenticated session, NOT the request body.
    """
    logger.info(f"POST /recommendations: user_id={current_user}, k={request.k}")

    try:
        service = get_recommendation_service()

        response = service.get_recommendations(
            user_id=current_user,
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


@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/hour")
async def submit_async_recommendations(
    request: Request,
    body: RecommendationRequest,
    current_user: str = Depends(get_current_user),
):
    """Submit a recommendation job for the current user asynchronously.

    Returns immediately with a job_id. Poll GET /recommendations/result/{job_id}
    or stream GET /recommendations/stream/{job_id} for live progress.

    The user_id is taken from the authenticated session, NOT the request body.
    """
    service = get_recommendation_service()
    job_id = service.submit_async(
        user_id=current_user,
        context=body.context,
        k=body.k,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/result/{job_id}")
async def get_async_result(job_id: str):
    """Poll for the result of an async recommendation job.

    Returns status, steps_so_far, and result (when complete).
    """
    service = get_recommendation_service()
    job = service.get_job_result(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "steps": job["steps"],
        "result": job["result"],
        "error": job["error"],
    }


@router.get("/stream/{job_id}")
async def stream_recommendations(job_id: str):
    """Server-Sent Events stream for a running recommendation job.

    Emits one SSE event per completed agent step, then a final 'done' event.
    """
    import asyncio
    import time as _time

    service = get_recommendation_service()

    async def _event_generator():
        seen_steps = 0
        deadline = _time.time() + 120  # 2-minute max stream

        while _time.time() < deadline:
            job = service.get_job_result(job_id)
            if job is None:
                yield f"data: {json.dumps({'error': 'job not found'})}\n\n"
                return

            # Emit any new steps
            steps = job["steps"]
            while seen_steps < len(steps):
                step = steps[seen_steps]
                yield f"data: {json.dumps({'type': 'step', 'step': step['step'], 'detail': step['detail']})}\n\n"
                seen_steps += 1

            if job["status"] == "complete":
                yield f"data: {json.dumps({'type': 'done', 'status': 'complete'})}\n\n"
                return
            elif job["status"] == "failed":
                yield f"data: {json.dumps({'type': 'error', 'error': job['error']})}\n\n"
                return

            await asyncio.sleep(0.3)

        yield f"data: {json.dumps({'type': 'error', 'error': 'timeout'})}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
