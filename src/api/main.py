"""FastAPI Application - CineMatch AI Recommendation API."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time
import uuid

from src.api.rate_limit import limiter
from src.api.routes import admin, auth, groups, health, history, movie_web, movies, news, profile, recommendations, reviews, users, watchlist
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ── Sentry — no-op when SENTRY_DSN isn't set ──────────────────────────────────
_sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.environ.get("DEPLOYMENT_ENV", "development"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,
        )
        logger.info("Sentry initialized")
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Sentry init failed (continuing without it): {exc}")

# Rate limiter is imported as a singleton from src.api.rate_limit so route
# modules can decorate endpoints with @limiter.limit("…") and share state.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("CineMatch AI API starting up...")

    # Pre-load agents (optional - can be lazy loaded)
    try:
        from src.agents.graph.workflow import get_agents
        agents = get_agents()
        logger.info(f"Pre-loaded {len(agents)} agents")
    except Exception as e:
        logger.warning(f"Failed to pre-load agents: {e}")

    # On HF Spaces: download vectordb from HF Datasets Hub if local copy is empty/small
    if os.environ.get("HF_SPACES") == "1":
        hf_dataset = os.environ.get("HF_VECTORDB_DATASET", "")
        vectordb_path = Path("data/vectordb")
        chroma_db_file = vectordb_path / "chroma.sqlite3"
        # Download if file doesn't exist or is < 10 MB (empty/stub DB)
        db_too_small = chroma_db_file.exists() and chroma_db_file.stat().st_size < 10 * 1024 * 1024
        if hf_dataset and (not chroma_db_file.exists() or db_too_small):
            logger.info(f"HF Spaces: downloading vectordb from {hf_dataset}...")
            try:
                from huggingface_hub import hf_hub_download
                import zipfile
                zip_path = hf_hub_download(
                    repo_id=hf_dataset,
                    filename="data_vectordb.zip",
                    repo_type="dataset",
                )
                vectordb_path.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Zip stores paths relative to data/ (e.g. vectordb/chroma.sqlite3)
                    zf.extractall("data/")
                logger.info("HF Spaces: vectordb downloaded and extracted successfully")
            except Exception as e:
                logger.warning(f"HF Spaces: vectordb download failed — starting with empty DB: {e}")
        elif not hf_dataset:
            logger.warning("HF Spaces: HF_VECTORDB_DATASET secret not set — starting with empty vectordb")

    # Pre-connect to vector DB (optional)
    try:
        from src.core.vectordb.chroma_client import get_chroma_client
        chroma_client = get_chroma_client()
        logger.info("Connected to ChromaDB")
    except Exception as e:
        logger.warning(f"Failed to connect to ChromaDB: {e}")

    # Initialize cloud vector DB (Zilliz + Qdrant)
    try:
        from src.services.cloud_vectordb import get_cloud_vectordb
        cloud_db = get_cloud_vectordb()
        availability = cloud_db.is_available()
        logger.info(f"Cloud vector DB status: {availability}")
    except Exception as e:
        logger.warning(f"Cloud vector DB init skipped: {e}")

    # Run light enrichment in background on startup
    try:
        from config.settings import get_settings
        _settings = get_settings()
        has_cloud = _settings.zilliz_uri or _settings.qdrant_url
        if has_cloud and _settings.enrichment_on_startup:
            import threading

            def _startup_enrich():
                try:
                    from src.services.enrichment_pipeline import EnrichmentPipeline
                    count = EnrichmentPipeline().run_light_cycle()
                    logger.info(f"Startup enrichment: {count} new movies indexed")
                except Exception as e:
                    logger.warning(f"Startup enrichment failed: {e}")

            threading.Thread(target=_startup_enrich, daemon=True).start()
            logger.info("Startup enrichment launched in background")
    except Exception as e:
        logger.warning(f"Startup enrichment setup failed: {e}")

    logger.info("CineMatch AI API startup complete")

    # Start CineDigest background news refresh
    try:
        from src.services.news_service import start_background_refresh
        start_background_refresh()
    except Exception as e:
        logger.warning(f"CineDigest startup failed: {e}")

    yield

    # Shutdown
    logger.info("CineMatch AI API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="CineMatch AI",
    description="Multi-Agent Movie Recommendation System with RAG and Multi-Modal Embeddings",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# CORS — read explicit origins from CORS_ORIGINS (comma-separated) when set;
# fall back to a sane production allow-list. allow_credentials stays False so
# browsers accept the response with allow-origin: * fallback if the env var is
# missing.
def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "https://cinematch-ai.me",
        "https://www.cinematch-ai.me",
        "https://feat-aws-deployment.dlhjm5yul87j0.amplifyapp.com",
        "http://localhost:3000",
        "http://localhost:5173",
    ]


_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS allow_origins: {_origins}")

# Wire slowapi limiter — endpoints opt in via @limiter.limit("…").
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# Strip absolute AWS hostnames from Location headers — FastAPI's
# trailing-slash redirects (and any RedirectResponse built from request.url)
# include the upstream API Gateway host, which leaks past the Amplify /api
# proxy and hits cellular networks that block *.execute-api.amazonaws.com.
# Make those redirects same-origin by emitting only the path+query.
@app.middleware("http")
async def relativize_redirect_location(request: Request, call_next):
    response = await call_next(request)
    loc = response.headers.get("location")
    if loc and ("execute-api" in loc or "amazonaws.com" in loc):
        from urllib.parse import urlparse
        parsed = urlparse(loc)
        relative = parsed.path or "/"
        if parsed.query:
            relative = f"{relative}?{parsed.query}"
        response.headers["location"] = relative
    return response


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)

    logger.info(
        f"Request: {request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Duration: {process_time:.3f}s | "
        f"RequestID: {request_id}"
    )

    return response


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Not Found",
            "detail": f"Path {request.url.path} not found",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
        },
    )


# Include routers
app.include_router(auth.router)
app.include_router(health.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(movies.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(news.router, prefix="/api/v1")
app.include_router(movie_web.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")

# ── Prometheus metrics endpoint at /metrics ───────────────────────────────────
# Exposes: request count, latency histograms, in-flight requests, response sizes
# Scraped by Prometheus every 15 s (see infra/monitoring/prometheus/prometheus.yml)
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"],
    inprogress_labels=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# ── Static file serving (HuggingFace Spaces / self-hosted with bundled UI) ────
# When /app/static/index.html exists (i.e. the React build was copied in by
# Dockerfile.spaces), serve the SPA at "/" and let React Router handle routing.
# All /api/* paths are already registered above and take priority.
_static_dir = Path(__file__).parent.parent.parent / "static"
_serve_spa = (_static_dir / "index.html").exists()

if _serve_spa:
    # Serve React app assets (JS/CSS chunks)
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def spa_root():
        return FileResponse(_static_dir / "index.html")

    # SPA catch-all: any path that isn't an API route returns index.html so
    # React Router can handle client-side navigation.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catchall(full_path: str):
        candidate = _static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")

else:
    # No bundled UI — serve API discovery JSON at root (local dev)
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "CineMatch AI",
            "version": "1.0.0",
            "description": "Multi-Agent Movie Recommendation System",
            "docs": "/docs",
            "health": "/api/v1/health",
            "endpoints": {
                "recommendations": "/api/v1/recommendations",
                "group_recommendations": "/api/v1/groups/recommendations",
                "onboarding": "/api/v1/users/onboard",
                "letterboxd_import": "/api/v1/users/import/letterboxd",
                "feedback": "/api/v1/users/feedback",
                "trending_movies": "/api/v1/movies/trending",
                "popular_by_language": "/api/v1/movies/popular/{language}",
                "recent_releases": "/api/v1/movies/recent",
                "search_movies": "/api/v1/movies/search",
                "movie_details": "/api/v1/movies/{tmdb_id}",
            },
        }


# Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
