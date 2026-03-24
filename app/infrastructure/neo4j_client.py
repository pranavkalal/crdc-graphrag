"""Async Neo4j client wrapper used by the API and services."""

from collections.abc import Mapping
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase


class Neo4jClient:
    """Small async wrapper around the Neo4j driver."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        self._uri = uri
        self._username = username
        self._password = password
        self._database = database
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Initialize the async driver if it has not been created yet."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
            )

    async def close(self) -> None:
        """Close the underlying driver and clear the local reference."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def health_check(self) -> dict[str, Any]:
        """Run a minimal query to verify the database is reachable."""
        if self._driver is None:
            raise RuntimeError("Neo4j driver is not connected.")

        async with self._driver.session(database=self._database) as session:
            result = await session.run("RETURN 1 AS ok")
            record = await result.single()

        ok = bool(record and record.get("ok") == 1)
        return {"ok": ok, "database": self._database}

    @property
    def driver(self) -> AsyncDriver | None:
        """Expose the raw driver for future repository adapters when needed."""
        return self._driver


HealthCheckResult = bool | Mapping[str, Any]
