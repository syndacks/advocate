"""Integration tests for the worker no-op Prefect flow."""

import pytest


@pytest.mark.integration
async def test_noop_flow_runs() -> None:
    """No-op Prefect flow runs synchronously and returns 'ok'."""
    from apps.worker.main import noop_flow

    result = await noop_flow(return_state=False)
    assert result == "ok"


@pytest.mark.integration
async def test_api_health_endpoint(test_client: object) -> None:
    """GET /health returns 200 with status ok."""
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    response = await test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
