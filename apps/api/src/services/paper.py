"""Paper Agent — analyzes academic papers from parsed PDF content.

Pipeline: ParsedDocument → LLM Analysis → PaperReport
"""

import json
from pathlib import Path

from config import settings
from domain.errors import LLMError
from logging_config import get_logger

logger = get_logger(__name__)


class PaperAgent:
    """Extract structured insights from an academic paper."""

    def __init__(self) -> None:
        self._system_prompt = self._load_prompt()

    async def analyze(self, title: str, sections_text: str) -> dict:
        """Analyze a paper and return structured report.

        Args:
            title: Paper title (from ParsedDocument.title).
            sections_text: Concatenated section content.

        Returns:
            dict with abstract_summary, contributions, method_summary,
            experiments, limitations, engineering_insights, key_quotes.
        """
        logger.info("paper.analyze", title=title)

        prompt = (
            f"Paper Title: {title}\n\n"
            f"Paper Content:\n{sections_text[:8000]}\n\n"
            f"Analyze this paper and return the structured report."
        )

        raw = await self._call_llm(prompt)
        return self._parse_json(
            raw,
            {
                "title": title,
                "abstract_summary": "",
                "contributions": [],
                "method_summary": "",
                "experiments": [],
                "limitations": [],
                "engineering_insights": [],
                "key_quotes": [],
            },
        )

    async def _call_llm(self, prompt: str) -> str:
        import litellm

        try:
            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"Paper analysis failed: {exc}") from exc

    @staticmethod
    def _load_prompt() -> str:
        path = Path(__file__).resolve().parents[4] / "agents" / "prompts" / "paper" / "system.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return text
        return "Analyze this academic paper. Extract abstract, contributions, method, experiments, limitations, and engineering insights."

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
            logger.warning("paper.json_parse_failed", preview=raw[:100])
            return default
