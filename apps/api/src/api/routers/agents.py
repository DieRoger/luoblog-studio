"""Agent API — expose Writing Agent and Review Agent as HTTP endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from config import settings
from domain.embedding import EmbeddingService
from domain.errors import AppError
from infrastructure.persistence.repositories import ChunkRepository, DocumentRepository
from infrastructure.embedding.api_embedding import LiteLLMEmbeddingService
from services.writing import WritingAgent
from services.review import ReviewAgent
from services.grounding import GroundingChecker
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


def _get_embedder() -> EmbeddingService:
    return LiteLLMEmbeddingService()


def _build_writing_agent(db: AsyncSession) -> WritingAgent:
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    embedder = _get_embedder()
    return WritingAgent(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)


def _build_review_agent(db: AsyncSession) -> ReviewAgent:
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    embedder = _get_embedder()
    checker = GroundingChecker(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)
    return ReviewAgent(grounding_checker=checker)


@router.post("/write")
async def agent_write(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a blog draft on a given topic using the Knowledge Hub."""
    topic = (body.get("topic") or "").strip()
    if not topic:
        raise AppError(code="MISSING_TOPIC", message="Topic is required", status_code=422)

    max_sections = max(1, min(body.get("max_sections", 5), 10))
    agent = _build_writing_agent(db)
    try:
        result = await agent.write(topic=topic, max_sections=max_sections)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("agent.write_failed", topic=topic)
        raise AppError(code="WRITE_FAILED", message=str(exc), status_code=500)

    return {
        "data": {
            "title": result.title,
            "summary": result.summary,
            "sections": [
                {
                    "heading": s.heading,
                    "content": s.content,
                    "citations": [
                        {"source": c.source_title, "score": c.score}
                        for c in s.citations
                    ],
                }
                for s in result.sections
            ],
        }
    }


@router.post("/review")
async def agent_review(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Review an article and return quality scores."""
    article = (body.get("article") or "").strip()
    if not article:
        raise AppError(code="MISSING_ARTICLE", message="Article text is required", status_code=422)

    agent = _build_review_agent(db)
    try:
        report = await agent.review(article_text=article)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("agent.review_failed")
        raise AppError(code="REVIEW_FAILED", message=str(exc), status_code=500)

    return {
        "data": {
            "scores": {
                "technical_accuracy": report.scores.technical_accuracy,
                "evidence_coverage": report.scores.evidence_coverage,
                "writing_quality": report.scores.writing_quality,
                "originality": report.scores.originality,
                "overall": report.scores.overall,
            },
            "issues": [
                {
                    "severity": i.severity,
                    "location": i.location,
                    "message": i.message,
                    "suggestion": i.suggestion,
                }
                for i in report.issues
            ],
            "summary": report.summary,
        }
    }
