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
        try:
            import os
            if os.environ.get("LAMBDA_TASK_ROOT") or os.environ.get("QDRANT_URL"):
                from qdrant_client import QdrantClient
                qc = QdrantClient(
                    url=os.environ["QDRANT_URL"],
                    api_key=os.environ.get("QDRANT_API_KEY"),
                )
                qc.get_collections()
                vectordb_connected = True
            else:
                from src.core.vectordb.chroma_client import get_chroma_client
                chroma_client = get_chroma_client()
                vectordb_connected = chroma_client is not None
        except Exception as e:
            logger.warning(f"Vector DB check failed: {e}")
            vectordb_connected = False

        # Determine overall status
        if agents_loaded and vectordb_connected:
            overall_status = "healthy"
        elif agents_loaded or vectordb_connected:
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
                "vectordb_type": "ChromaDB" if vectordb_connected else None,
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
