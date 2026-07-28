"""Writing Agent — generates evidence-backed technical articles from topics.

Pipeline:
  Topic → Research (Knowledge Hub) → Outline (LLM) → Write (LLM) → Assemble (Citations)
"""

import json
from pathlib import Path
from uuid import UUID

from config import settings
from domain.embedding import EmbeddingService
from domain.errors import AppError, LLMError
from domain.repositories import ChunkRepository, DocumentRepository
from domain.writing import Citation, Section, WritingResult
from logging_config import get_logger

logger = get_logger(__name__)


class WritingAgent:
    """Generate technical blog drafts using Knowledge Hub + LLM."""

    def __init__(
        self,
        embedder: EmbeddingService,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo

    async def write(
        self,
        topic: str,
        max_sections: int = 5,
        search_top_k: int = 10,
    ) -> WritingResult:
        """Generate a complete article from a topic.

        1. Search knowledge base for relevant context
        2. Generate outline from search results
        3. Write each section with citations
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

        # Step 3: Write sections
        logger.info("writing.sections", topic=topic, sections=len(outline))
        sections = await self._write_sections(topic, outline, context_str)

        # Step 4: Assemble with citations
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
            output.append({
                "chunk_id": str(chunk.id),
                "document_title": doc.title if doc else "Unknown",
                "section": chunk.section or "",
                "content": chunk.content,
                "score": round(score, 4),
            })
        return output

    # ------------------------------------------------------------------
    # Step 2: Outline
    # ------------------------------------------------------------------

    async def _generate_outline(
        self, topic: str, context: str, max_sections: int
    ) -> dict:
        """Generate JSON outline from topic + research context."""
        prompt = f"""You are a technical writing assistant. Given a topic and research context, generate an article outline.

Topic: {topic}

Research Context (top results from knowledge base):
{context}

Generate a JSON object with:
- "title": article title
- "summary": 1-2 sentence summary
- "sections": list of {max_sections} section headings

The article should be technical, evidence-driven, and follow this structure:
1. Background / Problem
2. Approach / Architecture
3. Implementation Details
4. Lessons Learned
5. Conclusion

Return ONLY valid JSON, no markdown formatting."""
        raw = await self._call_llm(prompt)
        return self._parse_json(raw, {"title": topic, "summary": "", "sections": []})

    # ------------------------------------------------------------------
    # Step 3: Write sections
    # ------------------------------------------------------------------

    async def _write_sections(
        self, topic: str, outline: dict, context: str
    ) -> list[Section]:
        """Write each section with inline citations."""
        sections = []
        for heading in outline.get("sections", []):
            prompt = f"""You are a technical writer with deep AI engineering expertise.

Article Topic: {topic}
Section Heading: {heading}

Research Context (use this for evidence and citations):
{context}

Write the section content in 2-3 paragraphs. Follow these rules:
1. Start with a real engineering problem or insight
2. Use specific evidence from the research context
3. Include inline citations like [Source: Document Title]
4. End with a practical takeaway
5. Be specific and technical — avoid generic statements

Return ONLY the section content as plain text (no metadata)."""
            raw = await self._call_llm(prompt)

            # Extract citations from the research results
            citations = self._extract_citations(context, heading)

            sections.append(Section(heading=heading, content=raw.strip(), citations=citations))
        return sections

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
    def _extract_citations(context: str, heading: str) -> list[Citation]:
        """Extract citations from context — heuristic: match [N] references."""
        import re

        citations = []
        seen = set()
        for match in re.finditer(r"\[(\d+)\]\s*From:\s*([^|\n]+)", context):
            num = int(match.group(1))
            title = match.group(2).strip()
            if num not in seen:
                seen.add(num)
                citations.append(Citation(source_title=title, chunk_content="", score=0.0))
        return citations

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM via LiteLLM."""
        try:
            import litellm

            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.exception("writing.llm_failed")
            raise LLMError(f"LLM call failed: {exc}") from exc

    @staticmethod
    def _parse_json(raw: str, default: dict) -> dict:
        """Try to parse JSON from LLM response, fallback to default."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("writing.json_parse_failed", raw_preview=raw[:200])
            return default
