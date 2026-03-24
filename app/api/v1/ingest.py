"""Placeholder ingestion routes for the pilot API."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("/pilot", summary="Placeholder pilot ingestion endpoint")
async def ingest_pilot_documents() -> None:
    """Reserve the pilot ingestion endpoint until extraction is implemented."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Pilot ingestion has not been implemented yet.",
    )
