"""Tests for Article Service — CRUD, status transitions, edge cases."""

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

# Mock pgvector at module level before any infrastructure import
if "pgvector" not in sys.modules:
    import types
    m = types.ModuleType("pgvector")
    m.sqlalchemy = types.ModuleType("pgvector.sqlalchemy")
    m.sqlalchemy.Vector = MagicMock()
    sys.modules["pgvector"] = m
    sys.modules["pgvector.sqlalchemy"] = m.sqlalchemy

from domain.entities import Article
from domain.enums import ArticleStatus
from domain.errors import NotFoundError
from services.articles import ArticleService


@pytest.fixture
def mock_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: MagicMock) -> ArticleService:
    return ArticleService(repo=mock_repo)


class TestArticleService:
    pytestmark = pytest.mark.asyncio

    async def test_create_article(self, service: ArticleService, mock_repo: MagicMock) -> None:
        mock_repo.save.return_value = Article(id=uuid.uuid4(), title="Test Article", slug="test-article", status=ArticleStatus.DRAFT)
        article = await service.create("Test Article")
        assert article.title == "Test Article"
        assert article.status == ArticleStatus.DRAFT
        mock_repo.save.assert_called_once()

    async def test_get_nonexistent_raises(self, service: ArticleService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await service.get(uuid.uuid4())

    async def test_update_content(self, service: ArticleService, mock_repo: MagicMock) -> None:
        article_id = uuid.uuid4()
        mock_repo.get_by_id.return_value = Article(id=article_id, title="T", slug="t", status=ArticleStatus.DRAFT)
        mock_repo.save.return_value = Article(id=article_id, title="T", slug="t", content="New content", status=ArticleStatus.DRAFT)
        result = await service.update_content(article_id, "New content")
        assert result.content == "New content"

    async def test_update_status(self, service: ArticleService, mock_repo: MagicMock) -> None:
        article_id = uuid.uuid4()
        mock_repo.get_by_id.return_value = Article(id=article_id, title="T", slug="t", status=ArticleStatus.DRAFT)
        result = await service.update_status(article_id, "published")
        mock_repo.update_status.assert_called_once_with(article_id, "published")

    async def test_list_articles(self, service: ArticleService, mock_repo: MagicMock) -> None:
        mock_repo.list_all.return_value = ([Article(id=uuid.uuid4(), title="A", slug="a")], 1)
        articles, total = await service.list()
        assert total == 1
        assert len(articles) == 1

    async def test_delete_article(self, service: ArticleService, mock_repo: MagicMock) -> None:
        article_id = uuid.uuid4()
        mock_repo.get_by_id.return_value = Article(id=article_id, title="T", slug="t")
        await service.delete(article_id)
        mock_repo.delete.assert_called_once_with(article_id)
