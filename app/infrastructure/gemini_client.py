"""Async Gemini client wrapper for structured output extraction."""

from typing import TypeVar, get_type_hints

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Wrapper for LangChain's Google GenAI chat model."""

    def __init__(self, api_key: str, model: str = "gemini-3.1-pro"):
        self._api_key = api_key
        self._model_name = model
        self._llm = ChatGoogleGenerativeAI(
            model=self._model_name,
            google_api_key=self._api_key,
            temperature=0.0,  # Extraction must be deterministic
        )

    def get_extractor(self, schema: type[T]):
        """Bind a Pydantic schema to the Gemini model for structured output."""
        return self._llm.with_structured_output(schema)

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        return self._llm
