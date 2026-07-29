"""Tests for Auto-tagging Service."""
import sys, uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from services.auto_tagging import AutoTaggingService


@pytest.fixture
def mock_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: MagicMock) -> AutoTaggingService:
    return AutoTaggingService(tag_repo=mock_repo)


class TestAutoTagging:
    pytestmark = pytest.mark.asyncio

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_generate_tags_parses_comma_list(self, mock_acompletion, service, mock_repo):
        mock_acompletion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="RAG, Python, Architecture"))]
        )
        tags = await service.generate_tags("Building RAG", "RAG systems...")
        assert tags == ["rag", "python", "architecture"]

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_max_tags_limit(self, mock_acompletion, service, mock_repo):
        mock_acompletion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="a, b, c, d, e, f, g"))]
        )
        tags = await service.generate_tags("T", "C", max_tags=3)
        assert len(tags) == 3

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_apply_tags_creates_and_links(self, mock_acompletion, service, mock_repo):
        mock_acompletion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="rag, python"))]
        )
        mock_repo.get_by_name.return_value = None
        mock_repo.create.return_value = MagicMock(id=uuid.uuid4(), name="rag", is_ai_generated=True)
        tags = await service.apply_tags(uuid.uuid4(), "Title", "Content")
        assert len(tags) == 2
        assert mock_repo.create.call_count == 2
