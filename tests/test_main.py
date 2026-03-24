from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


class StubNeo4jClient:
    def __init__(self, health_result=None, health_error: Exception | None = None) -> None:
        self.connect = AsyncMock()
        self.close = AsyncMock()
        self.health_check = AsyncMock()

        if health_error is not None:
            self.health_check.side_effect = health_error
        else:
            self.health_check.return_value = health_result or {"ok": True, "database": "neo4j"}


@pytest.fixture(autouse=True)
def clear_app_state() -> None:
    app.state.neo4j_client = None
    yield
    app.state.neo4j_client = None


def test_lifespan_connects_and_closes_the_neo4j_client() -> None:
    stub_client = StubNeo4jClient()
    app.state.neo4j_client = stub_client

    with TestClient(app):
        stub_client.connect.assert_awaited_once()

    stub_client.close.assert_awaited_once()


def test_health_route_returns_healthy_status() -> None:
    stub_client = StubNeo4jClient({"ok": True, "database": "crdc"})
    app.state.neo4j_client = stub_client

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "neo4j": {"ok": True, "database": "crdc"},
    }
    stub_client.health_check.assert_awaited_once()


def test_health_route_returns_unhealthy_status_when_check_fails() -> None:
    stub_client = StubNeo4jClient(health_error=RuntimeError("Neo4j unavailable"))
    app.state.neo4j_client = stub_client

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "neo4j": {
            "ok": False,
            "error": "RuntimeError",
            "message": "Neo4j unavailable",
        },
    }
