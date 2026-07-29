"""Tests for GitHub Sync — article publishing and Markdown formatting."""
import sys, uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.entities import Article
from domain.enums import ArticleStatus
from domain.errors import AppError
from services.github_sync import GithubSyncService, _b64encode


@pytest.fixture
def mock_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: MagicMock) -> GithubSyncService:
    return GithubSyncService(
        article_repo=mock_repo,
        token="ghp_test_token",
        repo_owner="DieRoger",
        repo_name="luoblog-studio",
    )


class TestGithubSync:
    pytestmark = pytest.mark.asyncio

    async def test_publish_missing_article_raises(self, service: GithubSyncService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = None
        with pytest.raises(AppError) as exc:
            await service.publish(uuid.uuid4())
        assert exc.value.code == "ARTICLE_NOT_FOUND"

    async def test_format_markdown_with_content(self, service: GithubSyncService) -> None:
        from datetime import datetime
        article = Article(id=uuid.uuid4(), title="Test Post", slug="test-post",
                          content="# Hello\n\nWorld.", summary="A test post.",
                          status=ArticleStatus.DRAFT, created_at=datetime(2026, 7, 30))
        md = service._format_markdown(article)
        assert "title: Test Post" in md
        assert "# Hello" in md
        assert "date: 2026-07-30" in md

    async def test_format_markdown_no_content(self, service: GithubSyncService) -> None:
        article = Article(id=uuid.uuid4(), title="Empty", slug="empty", status=ArticleStatus.DRAFT)
        md = service._format_markdown(article)
        assert "_No content yet._" in md

    async def test_build_file_path(self, service: GithubSyncService) -> None:
        article = Article(id=uuid.uuid4(), title="My Great Article", slug="my-great-article", status=ArticleStatus.DRAFT)
        path = service._build_file_path(article)
        assert path == "content/posts/my-great-article.md"

    async def test_github_upsert_new_file(self, service: GithubSyncService, mock_repo: MagicMock) -> None:
        with patch.object(service, "_get_file_sha", return_value=None):
            with patch("httpx.AsyncClient") as mock_client:
                mock_resp = MagicMock()
                mock_resp.status_code = 201
                mock_resp.json.return_value = {
                    "content": {"html_url": "https://github.com/test", "download_url": "https://raw.test", "sha": "abc123"}
                }
                mock_client.return_value.__aenter__.return_value.put.return_value = mock_resp

                result = await service._github_upsert("test.md", "# Content", "Test commit")
                assert result["html_url"] == "https://github.com/test"
                assert result["sha"] == "abc123"

    def test_b64encode(self) -> None:
        result = _b64encode("Hello World")
        assert isinstance(result, str)
        assert len(result) > 0
