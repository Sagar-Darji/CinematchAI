"""Health Check API Routes."""

from fastapi import APIRouter, status

from src.api.schemas.response import HealthResponse
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
async def health_check():
    """
    Health check endpoint.

    Returns service health status, version, and component availability.
    """
    logger.info("GET /health")

    try:
        # Check if agents are loaded
        from src.agents.graph.workflow import get_agents

        agents = get_agents()
        agents_loaded = len(agents) > 0

        # Check vector DB connection (Qdrant on Lambda, ChromaDB locally)
        vectordb_connected = False
        movie_count = None
        try:
            import os
            if os.environ.get("LAMBDA_TASK_ROOT") or os.environ.get("QDRANT_URL"):
                from qdrant_client import QdrantClient
                qc = QdrantClient(
                    url=os.environ["QDRANT_URL"],
                    api_key=os.environ.get("QDRANT_API_KEY"),
                )
                movie_count = qc.count(collection_name="cinematch_movies").count
                vectordb_connected = True
            else:
                from src.core.vectordb.chroma_client import get_chroma_client
                chroma_client = get_chroma_client()
                vectordb_connected = chroma_client is not None
        except Exception as e:
            logger.warning(f"Vector DB check failed: {e}")
            vectordb_connected = False

        # Postgres health — quick SELECT 1 against the cached connection
        postgres_connected = False
        postgres_error = None
        try:
            from src.core.db import get_db
            db = get_db()
            if db.is_postgres:
                with db.connect() as conn:
                    conn.execute("SELECT 1")
                postgres_connected = True
            else:
                postgres_connected = True  # SQLite fallback always reachable
        except Exception as e:
            postgres_error = str(e)
            logger.warning(f"Postgres health check failed: {e}")

        # Determine overall status — Postgres is now load-bearing for auth
        components_ok = [agents_loaded, vectordb_connected, postgres_connected]
        if all(components_ok):
            overall_status = "healthy"
        elif any(components_ok):
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        response = HealthResponse(
            status=overall_status,
            version="1.0.0",
            agents_loaded=agents_loaded,
            vectordb_connected=vectordb_connected,
            details={
                "agents_count": len(agents) if agents_loaded else 0,
                "vectordb_type": "Qdrant" if os.environ.get("QDRANT_URL") else "ChromaDB",
                "movie_count": movie_count if vectordb_connected and os.environ.get("QDRANT_URL") else None,
                "postgres_connected": postgres_connected,
                **({"postgres_error": postgres_error} if postgres_error else {}),
            },
        )

        return response

    except Exception as e:
        logger.error(f"Health check failed: {e}")

        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            agents_loaded=False,
            vectordb_connected=False,
            details={"error": str(e)},
        )
