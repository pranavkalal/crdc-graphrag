"""Placeholder graph service for future traversal and retrieval logic."""

from app.infrastructure.neo4j_client import Neo4jClient


class GraphService:
    """Coordinate graph queries against Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient) -> None:
        self._neo4j_client = neo4j_client

    async def query(self, question: str) -> dict[str, object]:
        """Placeholder graph query entry point."""
        raise NotImplementedError("Graph querying has not been implemented yet.")
