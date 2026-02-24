"""AWS Lambda entry point — wraps FastAPI with Mangum ASGI adapter."""

import json

from mangum import Mangum

from src.api.main import app  # noqa: E402

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Lambda entry point.

    Handles two event types:
    1. HTTP (API Gateway) — forwarded to FastAPI via Mangum
    2. Background job (source='recommendation-worker') — runs recommendation workflow
    """
    if event.get("source") == "recommendation-worker":
        return _run_background_recommendation(event)
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
