"""Placeholder graph query routes for the pilot API."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.post("/query", summary="Placeholder graph query endpoint")
async def query_graph() -> None:
    """Reserve the graph query surface for the next implementation slice."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Graph querying has not been implemented yet.",
    )
