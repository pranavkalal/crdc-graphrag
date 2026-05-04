"""Application settings and configuration helpers."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration for the API and adapters."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="CRDC Lazy GraphRAG")
    app_env: str = Field(default="development")

    neo4j_uri: str = Field(...)
    neo4j_username: str = Field(...)
    neo4j_password: SecretStr = Field(...)
    neo4j_database: str = Field(default="neo4j")

    openai_api_key: SecretStr | None = Field(default=None)
    openai_model: str | None = Field(default=None)

    gemini_api_key: SecretStr = Field(...)
    gemini_model: str = Field(default="gemini-2.5-flash")

    # ── Vector RAG bridge (optional — only needed for LangGraph agent) ───
    postgres_connection_string: SecretStr | None = Field(default=None)
    openai_api_key: SecretStr | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for app-wide reuse."""
    return Settings()
