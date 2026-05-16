"""AWS Lambda entry point — wraps FastAPI with Mangum ASGI adapter."""

from typing import Optional

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
    if src == "letterboxd-prep":
        return _run_letterboxd_prep(event)
    if src == "letterboxd-chunk":
        # Hand the Lambda budget through to the chunk worker so its
        # in-container loop knows when to hand off to a fresh
        # invocation instead of risking a hard timeout.
        try:
            remaining_ms = context.get_remaining_time_in_millis()
        except Exception:
            remaining_ms = None
        return _run_letterboxd_chunk(event, deadline_ms=remaining_ms)
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


def _run_letterboxd_prep(event: dict) -> dict:
    """Preprocess a Letterboxd import: download the raw ZIP/CSV from S3,
    run the heavy ZIP extraction + diary overlay + extras parsing, stage
    the merged ratings CSV + extras JSON, and finally update the job row
    with the total + s3 keys before dispatching the first chunk worker.

    This worker exists so the upload endpoint can return 202 in <2 seconds
    — the previous design did all of the above inside the request handler,
    which paid the Postgres-cold-start + pandas-parse cost on the request
    thread (165s in the worst case)."""
    from src.api.routes.users import process_letterboxd_prep

    job_id = event["job_id"]
    process_letterboxd_prep(job_id)
    return {"status": "ok", "job_id": job_id}


def _run_letterboxd_chunk(event: dict, deadline_ms: Optional[int] = None) -> dict:
    """Process Letterboxd-import chunks in a SINGLE Lambda invocation,
    looping until done or the Lambda budget is about to run out. Receives
    the context's remaining-time so it can self-dispatch a continuation
    invocation before a hard timeout.

    Old design fired one boto3.invoke per chunk; AWS's async-event queue
    silently throttled at ~14 self-invokes and every large import froze
    around the 700-row mark. New design loops in-container."""
    from src.api.routes.users import process_letterboxd_chunk

    job_id = event["job_id"]
    process_letterboxd_chunk(job_id, deadline_ms=deadline_ms)
    return {"status": "ok", "job_id": job_id}
