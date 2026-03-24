"""Placeholder OpenAI adapter for future extraction work."""

from typing import Any

from openai import AsyncOpenAI
from pydantic import SecretStr


class OpenAIClient:
    """Thin wrapper reserved for future extraction and summarization flows."""

    def __init__(self, api_key: SecretStr | None, model: str | None = None) -> None:
        self.model = model or "gpt-4o-mini"
        self._client = (
            AsyncOpenAI(api_key=api_key.get_secret_value()) if api_key is not None else None
        )

    async def extract_entities(self, text: str) -> dict[str, Any]:
        """Placeholder method for the pilot extraction workflow."""
        raise NotImplementedError("OpenAI-backed extraction has not been implemented yet.")
