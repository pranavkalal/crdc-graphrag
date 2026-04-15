"""Graph query API routes — NL question → Cypher → synthesised answer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.services.graph_service import GraphService

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


# ── Request / Response schemas ───────────────────────────────────────────────

class GraphQueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=500,
        examples=["What chemicals control Green Mirids?"],
    )


class GraphQueryResponse(BaseModel):
    question: str
    cypher: str
    explanation: str
    answer: str
    record_count: int
    records: list[dict] = Field(default_factory=list)


# ── Dependency ───────────────────────────────────────────────────────────────

def get_graph_service(request: Request) -> GraphService:
    """Build GraphService from the shared Neo4j client and app settings."""
    neo4j_client: Neo4jClient = request.app.state.neo4j_client
    settings = get_settings()
    return GraphService(
        neo4j_client=neo4j_client,
        gemini_api_key=settings.gemini_api_key.get_secret_value(),
        gemini_model=settings.gemini_model,
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/query",
    response_model=GraphQueryResponse,
    summary="Ask a natural language question answered by the Knowledge Graph",
    description=(
        "Converts your question to a Cypher query via Gemini, executes it against "
        "Neo4j Aura, then synthesises a human-readable answer from the results."
    ),
)
async def query_graph(
    body: GraphQueryRequest,
    service: GraphService = Depends(get_graph_service),
) -> GraphQueryResponse:
    """Natural language → graph query → synthesised answer."""
    try:
        result = await service.query(body.question)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph query failed: {exc}",
        ) from exc

    return GraphQueryResponse(**result)
