"""AWS Lambda entry point — wraps FastAPI with Mangum ASGI adapter."""

import json

from mangum import Mangum

from src.api.main import app  # noqa: E402

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Lambda entry point.

    Handles four event types:
    1. HTTP (API Gateway) — forwarded to FastAPI via Mangum
    2. Background job (source='recommendation-worker') — runs recommendation workflow
    3. Background job (source='stats-worker') — recomputes a user's persisted stats
    4. Background job (source='letterboxd-worker') — runs a Letterboxd CSV import
    """
    src = event.get("source")
    if src == "recommendation-worker":
        return _run_background_recommendation(event)
    if src == "stats-worker":
        return _run_background_stats(event)
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
    """Run a Letterboxd CSV import on its own Lambda container so it doesn't
    block the HTTP request handler for the duration of the import."""
    from src.api.routes.users import _import_letterboxd_background

    job_id = event["job_id"]
    user_id = event["user_id"]
    csv_content = event["csv_content"]
    _import_letterboxd_background(job_id, user_id, csv_content)
    return {"status": "ok", "job_id": job_id}
