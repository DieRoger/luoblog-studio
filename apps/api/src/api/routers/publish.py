"""GitHub Sync API — publish articles to GitHub."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from domain.errors import AppError
from infrastructure.persistence.repositories import ArticleRepository as ArticleRepoImpl
from services.github_sync import GithubSyncService
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/publish", tags=["publish"])


def get_sync_service(db: AsyncSession = Depends(get_db)) -> GithubSyncService:
    """Build sync service from config. Token/owner/repo should be in .env."""
    from config import settings
    token = settings.github_token
    owner = getattr(settings, "github_owner", "DieRoger")
    repo = getattr(settings, "github_repo", "luorunjie.github.io")
    if not token:
        raise AppError(code="GITHUB_NOT_CONFIGURED", message="GITHUB_TOKEN not set in .env", status_code=500)
    return GithubSyncService(
        article_repo=ArticleRepoImpl(db),
        token=token,
        repo_owner=owner,
        repo_name=repo,
    )


@router.post("/{article_id}")
async def publish_article(
    article_id: UUID,
    body: dict = {},
    service: GithubSyncService = Depends(get_sync_service),
) -> dict:
    """Publish an article draft to GitHub as a Markdown file."""
    commit_msg = body.get("commit_message", None)
    try:
        result = await service.publish(article_id, commit_msg)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("publish.failed", article_id=str(article_id))
        raise AppError(code="PUBLISH_FAILED", message=str(exc), status_code=500)

    return {"data": result}
