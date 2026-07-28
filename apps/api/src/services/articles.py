"""Article Service — CRUD for draft articles."""

from uuid import UUID

from domain.entities import Article
from domain.enums import ArticleStatus
from domain.errors import AppError, NotFoundError
from domain.repositories import ArticleRepository
from logging_config import get_logger

logger = get_logger(__name__)


class ArticleService:
    """Manage article drafts — create, save, publish, archive."""

    def __init__(self, repo: ArticleRepository) -> None:
        self._repo = repo

    async def create(self, title: str) -> Article:
        article = Article(
            title=title,
            slug=title.lower().replace(" ", "-").replace("/", "-")[:100],
            status=ArticleStatus.DRAFT,
        )
        saved = await self._repo.save(article)
        logger.info("article.created", article_id=str(saved.id), title=title)
        return saved

    async def get(self, article_id: UUID) -> Article:
        article = await self._repo.get_by_id(article_id)
        if article is None:
            raise NotFoundError("Article", str(article_id))
        return article

    async def update_content(self, article_id: UUID, content: str) -> Article:
        article = await self.get(article_id)
        article.content = content
        saved = await self._repo.save(article)
        logger.info("article.updated", article_id=str(article_id))
        return saved

    async def update_status(self, article_id: UUID, status: str) -> Article:
        article = await self.get(article_id)
        await self._repo.update_status(article_id, status)
        logger.info("article.status_changed", article_id=str(article_id), status=status)
        return article

    async def list(self, status: str | None = None, page: int = 1, page_size: int = 20) -> tuple[list[Article], int]:
        offset = (page - 1) * page_size
        return await self._repo.list_all(status=status, limit=page_size, offset=offset)

    async def delete(self, article_id: UUID) -> None:
        await self.get(article_id)
        await self._repo.delete(article_id)
        logger.info("article.deleted", article_id=str(article_id))
