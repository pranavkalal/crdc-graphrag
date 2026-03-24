import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "app.api.v1.graph",
        "app.api.v1.ingest",
        "app.services.graph_service",
        "app.services.extraction",
        "app.infrastructure.openai_client",
        "scripts.pilot_ingest",
    ],
)
def test_placeholder_modules_import_cleanly(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module is not None
