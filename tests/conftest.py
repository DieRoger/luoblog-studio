"""Pytest configuration — shared fixtures and helpers.

Usage:
  cd apps/api
  pytest ../../tests/

Fixtures that require PostgreSQL + pgvector are skipped automatically
when those packages are not installed (e.g., on Windows without build tools).
"""

import sys
from pathlib import Path

import pytest

SRC = str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src")
sys.path.insert(0, SRC)

# ---------------------------------------------------------------------------
# Optional DB-dependent fixtures (skipped if pgvector not installed)
# ---------------------------------------------------------------------------

try:
    from httpx import ASGITransport, AsyncClient
    from main import create_app
    from infrastructure.persistence.models import Base

    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


@pytest.fixture
async def client():
    """Httpx async client pointed at the FastAPI app. Requires PostgreSQL + pgvector."""
    if not _DB_AVAILABLE:
        pytest.skip("PostgreSQL + pgvector not available (install in Docker)")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client) -> None:
    """Smoke test: the app starts and /health returns 200."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
