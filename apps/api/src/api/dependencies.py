"""FastAPI dependency injection — provides shared services to route handlers.

Each dependency yields a service instance. Services will be implemented in later
phases; for now we wire the dependency graph through factory functions that raise
NotImplementedError so the import chain is verified at startup.
"""

from collections.abc import AsyncGenerator

from infrastructure.persistence.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session. Sessions are created per-request."""
    async for session in get_session():
        yield session
