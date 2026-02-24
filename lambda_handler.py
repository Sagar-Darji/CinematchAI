"""AWS Lambda entry point — wraps FastAPI with Mangum ASGI adapter."""

from mangum import Mangum

from src.api.main import app  # noqa: E402

# Lambda handler — API Gateway (HTTP API or REST API) invokes this
handler = Mangum(app, lifespan="off")
