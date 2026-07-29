"""Tests for Agent API endpoints — write + review."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

if "litellm" not in sys.modules:
    _m = MagicMock()
    _m.acompletion = AsyncMock()
    _m.aembedding = AsyncMock()
    sys.modules["litellm"] = _m

from httpx import ASGITransport, AsyncClient
from main import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAgentAPI:
    pytestmark = pytest.mark.asyncio

    async def test_write_missing_topic_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/agents/write", json={})
        assert resp.status_code == 422

    async def test_write_empty_topic_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/agents/write", json={"topic": ""})
        assert resp.status_code == 422

    async def test_review_missing_article_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/agents/review", json={})
        assert resp.status_code == 422

    async def test_review_empty_article_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/agents/review", json={"article": ""})
        assert resp.status_code == 422
