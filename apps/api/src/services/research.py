"""Research Agent — analyzes a topic using Knowledge Hub + LLM.

Outputs a structured research brief with sources, insights, and gaps.
"""

import json
from pathlib import Path

from config import settings
from domain.embedding import EmbeddingService
from domain.errors import LLMError
from domain.repositories import ChunkRepository, DocumentRepository
from logging_config import get_logger

logger = get_logger(__name__)


class ResearchAgent:
    """Search knowledge base and produce a structured research brief."""

    def __init__(
        self,
        embedder: EmbeddingService,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo
        self._system_prompt = self._load_prompt()

    async def research(self, topic: str, top_k: int = 15) -> dict:
        """Research a topic and return structured findings.

        Returns:
            dict with topic_analysis, sources, research_gaps, recommended_angles
        """
        logger.info("research.start", topic=topic, top_k=top_k)

        # 1. Search Knowledge Hub
        embedding = await self._embedder.embed_one(topic)
        if not embedding:
            return {"topic_analysis": {}, "sources": [], "research_gaps": [], "recommended_angles": []}

        results = await self._chunk_repo.vector_search(embedding, top_k)
        context = await self._format_context(results)

        if not context:
            logger.warning("research.no_results", topic=topic)
            return {"topic_analysis": {"core_concepts": [topic]}, "sources": [], "research_gaps": ["No relevant documents found in knowledge base"], "recommended_angles": []}

        # 2. LLM analysis
        raw = await self._call_llm(topic, context)
        parsed = self._parse_json(raw, {})

        logger.info("research.complete", topic=topic, sources=len(parsed.get("sources", [])))
        return parsed

    async def _format_context(self, results) -> str:
        lines = []
        for chunk, score in results:
            doc = await self._doc_repo.get_by_id(chunk.document_id)
            title = doc.title if doc else "Unknown"
            lines.append(f"[Score: {score:.2f}] From: {title} | Section: {chunk.section or ''}\n{chunk.content[:500]}")
        return "\n\n".join(lines)

    async def _call_llm(self, topic: str, context: str) -> str:
        import litellm

        prompt = (
            f"Research Topic: {topic}\n\n"
            f"Knowledge Base Results:\n{context}"
        )
        response = await litellm.acompletion(
            model=f"{settings.llm_provider}/{settings.llm_model}",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or ""
        return content

    @staticmethod
    def _load_prompt() -> str:
        path = Path(__file__).resolve().parents[4] / "agents" / "prompts" / "research" / "system.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return text
        return "Analyze the topic using the provided sources."

    @staticmethod
    def _parse_json(raw: str, default: dict) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("research.json_parse_failed", preview=raw[:100])
            return default
