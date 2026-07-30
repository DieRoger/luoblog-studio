"""Review Agent — evaluates article quality across 4 dimensions.

Uses the Review Agent system prompt from agents/prompts/review/system.md.
When a GroundingChecker is provided, includes real evidence coverage data.
"""

import json
from pathlib import Path

from config import settings
from domain.errors import AppError, LLMError
from domain.review import ReviewIssue, ReviewReport
from domain.value_objects import ReviewScores
from logging_config import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 2


class ReviewAgent:
    """Evaluate article quality using LLM + structured scoring."""

    def __init__(
        self,
        system_prompt: str | None = None,
        grounding_checker=None,
    ) -> None:
        self._system_prompt = system_prompt or self._load_system_prompt()
        self._checker = grounding_checker

    async def review(self, article_text: str, section_count: int = 0) -> ReviewReport:
        if not article_text.strip():
            raise AppError(
                code="EMPTY_ARTICLE", message="Cannot review empty article", status_code=422
            )

        # Run Grounding Checker if available — gives real evidence data
        grounding_context = ""
        if self._checker:
            try:
                report = await self._checker.verify(article_text)
                grounded = report.grounded_claims
                total = report.total_claims
                if total > 0:
                    grounding_context = (
                        f"\nGrounding Check Results:\n"
                        f"- Total claims extracted: {total}\n"
                        f"- Verified (grounded in knowledge base): {grounded}\n"
                        f"- Unverified: {report.ungrounded_claims}\n"
                        f"- Evidence coverage: {report.evidence_coverage:.0%}\n"
                    )
                    if report.ungrounded_claims > 0:
                        grounding_context += "- Unverified claims:\n"
                        for v in report.verifications:
                            if not v.is_grounded:
                                grounding_context += f'  * "{v.claim_text[:80]}..."\n'
            except Exception as exc:
                logger.warning("review.grounding_failed", error=str(exc))

        prompt = self._build_prompt(article_text, section_count, grounding_context)
        raw = await self._call_llm(prompt)
        return self._parse_report(raw)

    def _build_prompt(self, article: str, section_count: int, grounding: str = "") -> str:
        context = ""
        if section_count > 0:
            context = f"\nThe article has {section_count} sections.\n"
        return (
            f"Review the following technical article:\n"
            f"{context}{grounding}\n"
            f"---ARTICLE START---\n{article}\n---ARTICLE END---"
        )

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str) -> str:
        import litellm

        for attempt in range(MAX_RETRIES):
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
                content = response.choices[0].message.content or ""
                if hasattr(response, "usage") and response.usage:
                    logger.info(
                        "review.llm_ok",
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                    )
                return content
            except Exception as exc:
                if _is_retryable(exc) and attempt < MAX_RETRIES - 1:
                    import asyncio

                    delay = 1.0 * (2**attempt)
                    logger.warning("review.llm_retry", attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
                    continue
                logger.exception("review.llm_failed", attempt=attempt + 1)
                raise LLMError(f"Review LLM call failed: {exc}") from exc

        raise LLMError("Review LLM call failed after all retries")

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def _parse_report(self, raw: str) -> ReviewReport:
        """Parse LLM JSON response into ReviewReport."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (with optional language tag)
            cleaned = cleaned.split("\n", 1)[-1]
            # Remove closing fence
            cleaned = cleaned.rsplit("```", 1)[0]
            # Strip any trailing whitespace
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("review.json_parse_failed", raw_preview=raw[:200])
            return self._fallback_report()

        scores_data = data.get("scores", {})
        try:
            scores = ReviewScores(
                technical_accuracy=float(scores_data.get("technical_accuracy", 7.0)),
                evidence_coverage=float(scores_data.get("evidence_coverage", 7.0)),
                writing_quality=float(scores_data.get("writing_quality", 7.0)),
                originality=float(scores_data.get("originality", 7.0)),
            )
        except (ValueError, TypeError):
            scores = ReviewScores(7.0, 7.0, 7.0, 7.0)

        issues = []
        for item in data.get("issues", []):
            issues.append(
                ReviewIssue(
                    severity=item.get("severity", "suggestion"),
                    location=item.get("location", ""),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion", ""),
                )
            )

        return ReviewReport(
            scores=scores,
            issues=issues,
            summary=data.get("summary", ""),
        )

    @staticmethod
    def _load_system_prompt() -> str:
        """Load review prompt from file."""
        prompt_path = (
            Path(__file__).resolve().parents[4] / "agents" / "prompts" / "review" / "system.md"
        )
        if not prompt_path.exists():
            logger.warning("review.prompt_file_missing", path=str(prompt_path))
            return "Review this article. Score 0-10 for: technical_accuracy, evidence_coverage, writing_quality, originality."
        try:
            text = prompt_path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
                raise ValueError(f"Malformed YAML frontmatter in {prompt_path}")
            return text
        except Exception as exc:
            logger.error("review.prompt_load_failed", path=str(prompt_path), error=str(exc))
            raise AppError(
                code="PROMPT_LOAD_FAILED",
                message=f"Failed to load review prompt: {exc}",
                status_code=500,
            ) from exc

    @staticmethod
    def _fallback_report() -> ReviewReport:
        return ReviewReport(
            scores=ReviewScores(7.0, 7.0, 7.0, 7.0),
            issues=[
                ReviewIssue(
                    severity="warning",
                    location="",
                    message="Could not parse LLM response as JSON",
                    suggestion="Re-run the review",
                )
            ],
            summary="Review parsing failed. Using default scores.",
        )


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        k in msg for k in ["rate limit", "timeout", "503", "502", "429", "service unavailable"]
    )
