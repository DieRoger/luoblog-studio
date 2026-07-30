"""Auto-tagging Service — generates tags for documents using LLM."""

from config import settings
from domain.errors import LLMError
from domain.repositories import TagRepository
from logging_config import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a technical tag generator. Given a document title and excerpt, generate 3-5 relevant tags.

Rules:
- Tags should be single words or short phrases (2-3 words max)
- Use technical terms (Python, RAG, Agent, Architecture, etc.)
- Prefer existing tags over inventing new ones
- Return ONLY a comma-separated list of tags, no explanation"""


class AutoTaggingService:
    """Generate and apply tags to documents using the LLM."""

    def __init__(self, tag_repo: TagRepository) -> None:
        self._tag_repo = tag_repo

    async def generate_tags(self, title: str, content_excerpt: str, max_tags: int = 5) -> list[str]:
        """Generate tags from document title and content."""
        prompt = (
            f"Document Title: {title}\n\n"
            f"Content Excerpt:\n{content_excerpt[:1000]}\n\n"
            f"Generate up to {max_tags} technical tags as a comma-separated list."
        )
        raw = await self._call_llm(prompt)
        tags = [t.strip().lower() for t in raw.replace("\n", ",").split(",") if t.strip()]
        return tags[:max_tags]

    async def apply_tags(self, document_id, title: str, content_excerpt: str) -> list[str]:
        """Generate tags and store them in the database, linked to the document."""
        tag_names = await self.generate_tags(title, content_excerpt)
        for name in tag_names:
            tag = await self._tag_repo.get_by_name(name)
            if tag is None:
                tag = await self._tag_repo.create(name, is_ai_generated=True)
            await self._tag_repo.add_to_document(document_id, tag.id)
        logger.info("autotag.applied", document_id=str(document_id), tags=tag_names)
        return tag_names

    async def _call_llm(self, prompt: str) -> str:
        import litellm

        try:
            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"Auto-tagging LLM call failed: {exc}") from exc
