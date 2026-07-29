"""GitHub Sync — publish article drafts to a GitHub repository.

Uses GitHub API to create/update files in a configured repo.
Supports personal access tokens for authentication.
"""

import os
from pathlib import Path
from uuid import UUID

from domain.entities import Article
from domain.errors import AppError
from domain.repositories import ArticleRepository
from logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_BRANCH = "main"
API_BASE = "https://api.github.com"


class GithubSyncService:
    """Publish articles as Markdown files to a GitHub repository."""

    def __init__(
        self,
        article_repo: ArticleRepository,
        token: str,
        repo_owner: str,
        repo_name: str,
        target_path: str = "content/posts",
        branch: str = DEFAULT_BRANCH,
    ) -> None:
        self._article_repo = article_repo
        self._token = token
        self._owner = repo_owner
        self._repo = repo_name
        self._target_path = target_path.strip("/")
        self._branch = branch

    async def publish(self, article_id: UUID, commit_message: str | None = None) -> dict:
        """Publish an article to GitHub as a Markdown file.

        Args:
            article_id: UUID of the article to publish.
            commit_message: Optional commit message (auto-generated if omitted).

        Returns:
            dict with html_url, content_url, sha, branch.
        """
        article = await self._article_repo.get_by_id(article_id)
        if article is None:
            raise AppError(code="ARTICLE_NOT_FOUND", message=f"Article {article_id} not found", status_code=404)

        md_content = self._format_markdown(article)
        file_path = self._build_file_path(article)
        message = commit_message or f"Publish: {article.title}"

        result = await self._github_upsert(file_path, md_content, message)
        logger.info("github.published", article_id=str(article_id), path=file_path, url=result.get("html_url"))
        return result

    async def _github_upsert(self, path: str, content: str, message: str) -> dict:
        """Create or update a file on GitHub via the API."""
        import httpx

        url = f"{API_BASE}/repos/{self._owner}/{self._repo}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Check if file exists (to get SHA for update)
        existing_sha = await self._get_file_sha(path)

        body = {
            "message": message,
            "content": _b64encode(content),
            "branch": self._branch,
        }
        if existing_sha:
            body["sha"] = existing_sha

        async with httpx.AsyncClient() as client:
            resp = await client.put(url, json=body, headers=headers)
            if resp.status_code not in (200, 201):
                raise AppError(
                    code="GITHUB_API_ERROR",
                    message=f"GitHub API returned {resp.status_code}: {resp.text[:200]}",
                    status_code=502,
                )
            data = resp.json()
            return {
                "html_url": data["content"]["html_url"],
                "content_url": data["content"]["download_url"],
                "sha": data["content"]["sha"],
                "branch": self._branch,
            }

    async def _get_file_sha(self, path: str) -> str | None:
        """Get SHA of existing file (for update) or None if new."""
        import httpx

        url = f"{API_BASE}/repos/{self._owner}/{self._repo}/contents/{path}?ref={self._branch}"
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github.v3+json"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()["sha"]
            return None

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _build_file_path(self, article: Article) -> str:
        slug = article.slug or article.title.lower().replace(" ", "-").replace("/", "-")[:80]
        return f"{self._target_path}/{slug}.md"

    @staticmethod
    def _format_markdown(article: Article) -> str:
        lines = ["---"]
        lines.append(f"title: {article.title}")
        if article.summary:
            lines.append(f"description: {article.summary}")
        lines.append(f"date: {article.created_at.strftime('%Y-%m-%d')}")
        lines.append("draft: false")
        if article.topics:
            lines.append(f"tags: [{', '.join(article.topics)}]")
        lines.append("---")
        lines.append("")
        if article.content:
            lines.append(article.content)
        else:
            lines.append("_No content yet._")
        return "\n".join(lines)


def _b64encode(text: str) -> str:
    """Base64 encode for GitHub API content."""
    import base64
    return base64.b64encode(text.encode("utf-8")).decode("ascii")
