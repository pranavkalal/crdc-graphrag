"""FastAPI application entry point for the CRDC Lazy GraphRAG ."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.graph import router as graph_router
from app.api.v1.ingest import router as ingest_router
from app.core.config import get_settings
from app.infrastructure.neo4j_client import HealthCheckResult, Neo4jClient


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize and close shared infrastructure clients for the API."""
    neo4j_client = getattr(application.state, "neo4j_client", None)

    if neo4j_client is None:
        settings = get_settings()
        neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password.get_secret_value(),
            database=settings.neo4j_database,
        )
        application.state.neo4j_client = neo4j_client

    await neo4j_client.connect()

    try:
        yield
    finally:
        await neo4j_client.close()
        application.state.neo4j_client = None


def get_neo4j_client(request: Request) -> Neo4jClient:
    """Provide the shared Neo4j client instance to route handlers."""
    return request.app.state.neo4j_client


def normalize_health_result(result: HealthCheckResult) -> dict[str, Any]:
    """Normalize health-check return values into a response payload."""
    if isinstance(result, Mapping):
        return dict(result)

    return {"ok": bool(result)}


app = FastAPI(title="CRDC Lazy GraphRAG", lifespan=lifespan)
app.include_router(graph_router)
app.include_router(ingest_router)


@app.get("/health", summary="Verify API and Neo4j availability")
async def health_check(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
) -> JSONResponse:
    """Report service health and Neo4j connectivity state."""
    try:
        neo4j_status = normalize_health_result(await neo4j_client.health_check())
    except Exception as exc:  # pragma: no cover - error shape is what matters
        neo4j_status = {
            "ok": False,
            "error": exc.__class__.__name__,
            "message": str(exc),
        }

    healthy = bool(neo4j_status.get("ok"))
    payload = {"status": "ok" if healthy else "unhealthy", "neo4j": neo4j_status}
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)
