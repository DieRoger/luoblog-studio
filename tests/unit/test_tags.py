"""Tests for Tag System — TagService with mocked repository.

Coverage:
  - Unit: create, list, delete tags
  - Unit: link/unlink tags to documents
  - Unit: duplicate tag creation returns existing
  - Failure: empty tag name
  - Failure: delete nonexistent tag
  - Edge: special characters in tag names
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.errors import AppError, NotFoundError
from domain.repositories import TagRepository as TagRepoABC
from services.tags import TagService


# ---------------------------------------------------------------------------
# Helper — create a tag-like mock avoiding the reserved `name` kwarg
# ---------------------------------------------------------------------------


def _tag_mock(tag_id: uuid.UUID | None = None, **attrs):
    """Create a MagicMock with tag attributes, avoiding MagicMock's name kwarg."""
    m = MagicMock()
    m.id = tag_id or uuid.uuid4()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


# ============================================================================
# UNIT TESTS — TagService with mocked repository
# ============================================================================


@pytest.fixture
def mock_repo() -> MagicMock:
    """Create a mock that conforms to TagRepository interface."""
    return MagicMock(spec=TagRepoABC)


@pytest.fixture
def service(mock_repo: MagicMock) -> TagService:
    return TagService(repo=mock_repo)


class TestTagService:
    """Tag CRUD via TagService (mock repository)."""
    pytestmark = pytest.mark.asyncio

    async def test_create_tag_returns_tag(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_name.return_value = None
        mock_repo.create.return_value = _tag_mock(name="rag", is_ai_generated=False)

        result = await service.create_tag("rag")
        assert result["name"] == "rag"

    async def test_create_duplicate_tag_returns_existing(self, service: TagService, mock_repo: MagicMock) -> None:
        existing = _tag_mock(name="rag", is_ai_generated=True)
        mock_repo.get_by_name.return_value = existing

        result = await service.create_tag("rag")
        assert result["name"] == "rag"
        assert result["is_ai_generated"] is True
        mock_repo.create.assert_not_called()

    async def test_empty_tag_name_raises(self, service: TagService, mock_repo: MagicMock) -> None:
        with pytest.raises(AppError) as exc:
            await service.create_tag("  ")
        assert exc.value.code == "INVALID_TAG"

    async def test_list_tags(self, service: TagService, mock_repo: MagicMock) -> None:
        t1 = _tag_mock(name="a", is_ai_generated=False)
        t2 = _tag_mock(name="b", is_ai_generated=True)
        mock_repo.list_all.return_value = [t1, t2]

        tags = await service.list_tags()
        assert len(tags) == 2

    async def test_delete_tag(self, service: TagService, mock_repo: MagicMock) -> None:
        await service.delete_tag(uuid.uuid4())
        mock_repo.delete.assert_called_once()

    async def test_delete_nonexistent_propagates_error(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.delete.side_effect = NotFoundError("Tag", str(uuid.uuid4()))
        with pytest.raises(NotFoundError):
            await service.delete_tag(uuid.uuid4())


class TestTagDocumentLinking:
    """Tag ↔ Document association."""
    pytestmark = pytest.mark.asyncio

    async def test_add_tag_creates_if_missing(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_name.return_value = None
        mock_repo.create.return_value = _tag_mock(name="new-tag", is_ai_generated=False)

        result = await service.add_tag_to_document(uuid.uuid4(), "new-tag")
        assert result["name"] == "new-tag"
        mock_repo.create.assert_called_once()

    async def test_add_existing_tag_links_without_creating(self, service: TagService, mock_repo: MagicMock) -> None:
        tag_id = uuid.uuid4()
        mock_repo.get_by_name.return_value = _tag_mock(tag_id=tag_id, name="existing", is_ai_generated=True)

        await service.add_tag_to_document(uuid.uuid4(), "existing")
        mock_repo.create.assert_not_called()
        mock_repo.add_to_document.assert_called_once()

    async def test_remove_missing_tag_no_error(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_name.return_value = None
        await service.remove_tag_from_document(uuid.uuid4(), "nonexistent")
        mock_repo.remove_from_document.assert_not_called()

    async def test_get_document_tags(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.get_document_tags.return_value = [_tag_mock(name="test-tag")]

        tags = await service.get_document_tags(uuid.uuid4())
        assert len(tags) == 1
        assert tags[0]["name"] == "test-tag"


class TestTagEdgeCases:
    """Edge cases for tag operations."""
    pytestmark = pytest.mark.asyncio

    async def test_tag_name_stripped(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_name.return_value = None
        mock_repo.create.return_value = _tag_mock(name="AI Engineering", is_ai_generated=False)

        result = await service.create_tag("  AI Engineering  ")
        assert result["name"] == "AI Engineering"

    async def test_unicode_tag(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_name.return_value = None
        mock_repo.create.return_value = _tag_mock(name="研究", is_ai_generated=True)

        result = await service.create_tag("研究", is_ai_generated=True)
        assert result["name"] == "研究"

    async def test_empty_list(self, service: TagService, mock_repo: MagicMock) -> None:
        mock_repo.list_all.return_value = []
        assert await service.list_tags() == []
