"""Placeholder extraction service for future document processing logic."""

from app.infrastructure.openai_client import OpenAIClient


class ExtractionService:
    """Coordinate ontology extraction from pilot documents."""

    def __init__(self, openai_client: OpenAIClient) -> None:
        self._openai_client = openai_client

    async def extract_document(self, document_path: str) -> dict[str, object]:
        """Placeholder document extraction entry point."""
        raise NotImplementedError("Document extraction has not been implemented yet.")
