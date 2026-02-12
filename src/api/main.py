"""FastAPI Application - CineMatch AI Recommendation API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

from src.api.routes import groups, health, movies, recommendations, users
from src.utils.logging import get_logger

logger = get_logger(__name__)


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

    # Pre-connect to vector DB (optional)
    try:
        from src.core.vectordb.chroma_client import get_chroma_client
        chroma_client = get_chroma_client()
        logger.info("Connected to ChromaDB")
    except Exception as e:
        logger.warning(f"Failed to connect to ChromaDB: {e}")

    logger.info("CineMatch AI API startup complete")

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


# CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
app.include_router(health.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(movies.router, prefix="/api/v1")


# Root endpoint
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
