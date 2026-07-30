"""Writing Agent — generates evidence-backed technical articles from topics.

Pipeline:
  Topic → Research (Knowledge Hub) → Outline (LLM) → Write (LLM) → Assemble (Citations)
"""

import asyncio
import json
import re
from pathlib import Path

from config import settings
from domain.embedding import EmbeddingService
from domain.errors import AppError, LLMError
from domain.repositories import ChunkRepository, DocumentRepository
from domain.writing import Citation, Section, WritingResult
from logging_config import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


class WritingAgent:
    """Generate technical blog drafts using Knowledge Hub + LLM."""

    def __init__(
        self,
        embedder: EmbeddingService,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
        max_tokens: int = 8192,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo
        self._max_tokens = max_tokens
        self._system_prompt = self._load_system_prompt()

    async def write(
        self,
        topic: str,
        max_sections: int = 5,
        search_top_k: int = 10,
    ) -> WritingResult:
        """Generate a complete article from a topic.

        1. Search knowledge base for relevant context
        2. Generate outline from search results
        3. Write each section with citations (parallel)
        4. Assemble into final result
        """
        # Step 1: Research
        logger.info("writing.research", topic=topic, top_k=search_top_k)
        research_results = await self._research(topic, search_top_k)
        if not research_results:
            raise AppError(
                code="NO_SEARCH_RESULTS",
                message=f"No relevant knowledge found for '{topic}'. Import documents first.",
                status_code=400,
            )

        context_str = self._format_context(research_results)

        # Step 2: Outline
        logger.info("writing.outline", topic=topic)
        outline = await self._generate_outline(topic, context_str, max_sections)

        # Step 3: Write sections in parallel
        headings = outline.get("sections", [])
        logger.info("writing.sections", topic=topic, sections=len(headings))

        tasks = [self._write_single_section(topic, h, context_str) for h in headings]
        sections = await asyncio.gather(*tasks)

        # Step 4: Assemble
        logger.info(
            "writing.completed",
            topic=topic,
            sections=len(sections),
        )
        return WritingResult(
            title=outline.get("title", topic),
            summary=outline.get("summary", ""),
            sections=sections,
        )

    # ------------------------------------------------------------------
    # Step 1: Research
    # ------------------------------------------------------------------

    async def _research(self, topic: str, top_k: int) -> list[dict]:
        """Search knowledge base for relevant chunks."""
        query_embedding = await self._embedder.embed_one(topic)
        if not query_embedding:
            return []

        results = await self._chunk_repo.vector_search(query_embedding, top_k)
        output = []
        for chunk, score in results:
            doc = await self._doc_repo.get_by_id(chunk.document_id)
            output.append(
                {
                    "chunk_id": str(chunk.id),
                    "document_title": doc.title if doc else "Unknown",
                    "section": chunk.section or "",
                    "content": chunk.content,
                    "score": round(score, 4),
                }
            )
        return output

    # ------------------------------------------------------------------
    # Step 2: Outline
    # ------------------------------------------------------------------

    async def _generate_outline(self, topic: str, context: str, max_sections: int) -> dict:
        """Generate JSON outline from topic + research context."""
        prompt = (
            f"You are a technical writing assistant. Given a topic and research context, "
            f"generate an article outline.\n\n"
            f"Topic: {topic}\n\n"
            f"Research Context (top results from knowledge base):\n{context}\n\n"
            f"Generate a JSON object with:\n"
            f'- "title": article title\n'
            f'- "summary": 1-2 sentence summary\n'
            f'- "sections": list of {max_sections} section headings\n\n'
            f"The article should be technical, evidence-driven, and follow this structure:\n"
            f"1. Background / Problem\n"
            f"2. Approach / Architecture\n"
            f"3. Implementation Details\n"
            f"4. Lessons Learned\n"
            f"5. Conclusion\n\n"
            f"Return ONLY valid JSON, no markdown formatting."
        )
        raw = await self._call_llm(prompt)
        return self._parse_json(raw, {"title": topic, "summary": "", "sections": []})

    # ------------------------------------------------------------------
    # Step 3: Write a single section
    # ------------------------------------------------------------------

    async def _write_single_section(self, topic: str, heading: str, context: str) -> Section:
        """Write one section with inline citations."""
        prompt = (
            f"You are a technical writer with deep AI engineering expertise.\n\n"
            f"Article Topic: {topic}\n"
            f"Section Heading: {heading}\n\n"
            f"Research Context (use this for evidence and citations):\n{context}\n\n"
            f"Write the section content in 2-3 paragraphs. Follow these rules:\n"
            f"1. Start with a real engineering problem or insight\n"
            f"2. Use specific evidence from the research context\n"
            f"3. Include inline citations like [Source: Document Title]\n"
            f"4. End with a practical takeaway\n"
            f"5. Be specific and technical — avoid generic statements\n\n"
            f"Return ONLY the section content as plain text (no metadata)."
        )
        raw = await self._call_llm(prompt)
        citations = self._extract_citations(context)
        return Section(heading=heading, content=raw.strip(), citations=citations)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_context(results: list[dict]) -> str:
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] From: {r['document_title']}"
                f" | Section: {r['section']}"
                f" | Relevance: {r['score']}\n"
                f"    {r['content'][:500]}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _extract_citations(context: str) -> list[Citation]:
        """Extract citations from context — match [N] From: Title patterns."""
        citations = []
        seen = set()
        for match in re.finditer(r"\[(\d+)\]\s*From:\s*([^|\n]+)", context):
            num = int(match.group(1))
            title = match.group(2).strip()
            if num not in seen:
                seen.add(num)
                citations.append(Citation(source_title=title, chunk_content="", score=0.0))
        return citations

    @staticmethod
    def _parse_json(raw: str, default: dict) -> dict:
        """Try to parse JSON from LLM response, fallback to default."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("writing.json_parse_failed", raw_preview=raw[:200])
            return default

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    @staticmethod
    def _load_system_prompt() -> str:
        """Load writing system prompt from file, with fallback."""
        prompt_path = (
            Path(__file__).resolve().parents[4] / "agents" / "prompts" / "writing" / "system.md"
        )
        try:
            if prompt_path.exists():
                text = prompt_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter (--- ... ---)
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        text = parts[2].strip()
                return text
        except Exception as exc:
            logger.warning("writing.prompt_load_failed", path=str(prompt_path), error=str(exc))
        return "You are a technical writing assistant. Write clear, evidence-driven technical articles."

    # ------------------------------------------------------------------
    # LLM with retry
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM via LiteLLM with retry + exponential backoff."""
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                import litellm

                response = await litellm.acompletion(
                    model=f"{settings.llm_provider}/{settings.llm_model}",
                    messages=[
                        {"role": "system", "content": self._system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=self._max_tokens,
                )
                content = response.choices[0].message.content or ""

                # Track token usage
                if hasattr(response, "usage") and response.usage:
                    logger.info(
                        "writing.llm_ok",
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        attempt=attempt + 1,
                    )
                return content

            except Exception as exc:
                last_exc = exc
                is_retryable = _is_retryable_error(exc)
                if not is_retryable or attempt == MAX_RETRIES - 1:
                    logger.exception(
                        "writing.llm_failed",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                    )
                    raise LLMError(
                        f"LLM call failed after {attempt + 1} attempt(s): {exc}"
                    ) from exc

                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "writing.llm_retry",
                    attempt=attempt + 1,
                    delay_sec=delay,
                    error=str(exc)[:100],
                )
                await asyncio.sleep(delay)

        raise LLMError(f"LLM call failed: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _is_retryable_error(exc: Exception) -> bool:
    """Check if the error is likely transient (rate limit, timeout, 5xx)."""
    msg = str(exc).lower()
    if "rate limit" in msg or "rate_limit" in msg:
        return True
    if "timeout" in msg:
        return True
    if "503" in msg or "502" in msg or "429" in msg:
        return True
    if "service unavailable" in msg:
        return True
    return False
