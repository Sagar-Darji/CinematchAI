"""AWS Lambda entry point — wraps FastAPI with Mangum ASGI adapter."""

import json

from mangum import Mangum

from src.api.main import app  # noqa: E402

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Lambda entry point.

    Handles five event types:
    1. HTTP (API Gateway) — forwarded to FastAPI via Mangum
    2. Background job (source='recommendation-worker') — runs recommendation workflow
    3. Background job (source='stats-worker') — recomputes a user's persisted stats
    4. Background job (source='letterboxd-chunk') — processes one chunk of a CSV import
    5. Background job (source='letterboxd-worker') — legacy monolithic Letterboxd import
       (kept for back-compat with in-flight jobs at deploy time; can be removed
       after the queue drains)
    """
    src = event.get("source")
    if src == "recommendation-worker":
        return _run_background_recommendation(event)
    if src == "stats-worker":
        return _run_background_stats(event)
    if src == "letterboxd-chunk":
        return _run_letterboxd_chunk(event)
    if src == "letterboxd-worker":
        return _run_background_letterboxd(event)
    return _mangum_handler(event, context)


def _run_background_recommendation(event: dict) -> dict:
    """Execute a recommendation workflow triggered by async Lambda self-invocation."""
    from src.services.recommendation_service import execute_recommendation_job

    job_id = event["job_id"]
    user_id = event["user_id"]
    rec_context = event.get("context")
    k = event.get("k", 10)

    execute_recommendation_job(job_id, user_id, rec_context, k)
    return {"status": "ok", "job_id": job_id}


def _run_background_stats(event: dict) -> dict:
    """Recompute persisted user stats triggered by async Lambda self-invocation."""
    from src.services.stats_service import get_stats_service

    user_id = event["user_id"]
    get_stats_service().compute(user_id)
    return {"status": "ok", "user_id": user_id}


def _run_background_letterboxd(event: dict) -> dict:
    """Legacy Letterboxd worker (monolithic, single Lambda invocation does
    the whole CSV). Kept for back-compat with in-flight jobs from before
    the chunked design landed; new jobs always use letterboxd-chunk."""
    from src.api.routes.users import _import_letterboxd_background

    job_id = event["job_id"]
    user_id = event["user_id"]
    csv_content = event["csv_content"]
    _import_letterboxd_background(job_id, user_id, csv_content)
    return {"status": "ok", "job_id": job_id}


def _run_letterboxd_chunk(event: dict) -> dict:
    """Process ONE chunk of a Letterboxd import. The worker reads the CSV
    from S3, processes its assigned slice, atomically advances the chunk
    pointer, and self-dispatches the next chunk. Each invocation finishes
    in 5-30 seconds (vs the monolithic worker's 5+ minutes that kept
    blowing past Lambda's 300s timeout)."""
    from src.api.routes.users import process_letterboxd_chunk

    job_id = event["job_id"]
    process_letterboxd_chunk(job_id)
    return {"status": "ok", "job_id": job_id}
