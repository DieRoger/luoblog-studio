"""Tests for Review Agent — report parsing, scoring, edge cases.

Coverage:
  - Unit: parse valid JSON → ReviewReport, parse with markdown fences
  - Failure: empty article, JSON parse failure → fallback report
  - Edge: missing score keys, zero issues, boundary values
  - LLM mock: test error handling with mocked litellm
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

# Mock litellm at module level
if "litellm" not in sys.modules:
    _mock_litellm = MagicMock()
    _mock_litellm.acompletion = AsyncMock()
    sys.modules["litellm"] = _mock_litellm
else:
    _mock_litellm = sys.modules["litellm"]
    if not hasattr(_mock_litellm, "acompletion"):
        _mock_litellm.acompletion = AsyncMock()

from domain.errors import LLMError
from domain.review import ReviewIssue, ReviewReport
from domain.value_objects import ReviewScores
from services.review import ReviewAgent


@pytest.fixture
def agent() -> ReviewAgent:
    return ReviewAgent(system_prompt="Review this article.")


# ============================================================================
# UNIT TESTS — Parsing (no LLM calls)
# ============================================================================


class TestReviewParsing:
    """Test JSON parsing from LLM responses."""

    def test_parse_valid_json(self, agent: ReviewAgent) -> None:
        raw = '{"scores": {"technical_accuracy": 8.5, "evidence_coverage": 7.8, "writing_quality": 8.2, "originality": 7.5}, "issues": [{"severity": "warning", "location": "Section 2", "message": "Missing evidence", "suggestion": "Add source"}], "summary": "Good article."}'
        report = agent._parse_report(raw)
        assert report.scores.technical_accuracy == 8.5
        assert report.scores.evidence_coverage == 7.8
        assert len(report.issues) == 1
        assert report.issues[0].severity == "warning"

    def test_parse_with_markdown_fences(self, agent: ReviewAgent) -> None:
        raw = '```json\n{"scores": {"technical_accuracy": 9.0, "evidence_coverage": 8.0, "writing_quality": 8.5, "originality": 8.0}, "issues": [], "summary": "Well written."}\n```'
        report = agent._parse_report(raw)
        assert report.scores.technical_accuracy == 9.0
        assert len(report.issues) == 0

    def test_parse_invalid_json_returns_fallback(self, agent: ReviewAgent) -> None:
        raw = "not json at all"
        report = agent._parse_report(raw)
        assert report.scores.technical_accuracy == 7.0  # fallback
        assert len(report.issues) == 1
        assert report.issues[0].severity == "warning"

    def test_parse_missing_scores_uses_defaults(self, agent: ReviewAgent) -> None:
        raw = '{"scores": {}, "issues": [], "summary": ""}'
        report = agent._parse_report(raw)
        assert report.scores.technical_accuracy == 7.0

    def test_overall_score_is_weighted_average(self) -> None:
        scores = ReviewScores(10.0, 10.0, 10.0, 10.0)
        assert scores.overall == 10.0

        scores = ReviewScores(10.0, 0.0, 0.0, 0.0)
        assert scores.overall == 3.5  # 10 * 0.35


# ============================================================================
# FAILURE TESTS
# ============================================================================


class TestReviewFailures:
    pytestmark = pytest.mark.asyncio
    async def test_empty_article_raises_app_error(self, agent: ReviewAgent) -> None:
        from domain.errors import AppError

        with pytest.raises(AppError) as exc:
            await agent.review("")
        assert exc.value.code == "EMPTY_ARTICLE"

    async def test_whitespace_only_raises(self, agent: ReviewAgent) -> None:
        from domain.errors import AppError

        with pytest.raises(AppError):
            await agent.review("   \n\n  ")

    async def test_llm_failure_raises_llm_error(self, agent: ReviewAgent) -> None:
        _mock_litellm.acompletion.reset_mock()
        _mock_litellm.acompletion.side_effect = ConnectionError("API down")
        with pytest.raises(LLMError):
            await agent.review("Test article content.")


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestReviewEdgeCases:
    def test_issue_with_empty_location(self) -> None:
        issue = ReviewIssue(severity="critical", location="", message="Problem", suggestion="Fix")
        assert issue.severity == "critical"

    def test_report_with_zero_issues(self) -> None:
        scores = ReviewScores(8.0, 7.0, 8.5, 7.5)
        report = ReviewReport(scores=scores, issues=[], summary="Perfect.")
        assert len(report.issues) == 0

    def test_scores_at_boundaries(self) -> None:
        scores = ReviewScores(0.0, 0.0, 0.0, 0.0)
        assert scores.overall == 0.0

        scores = ReviewScores(10.0, 10.0, 10.0, 10.0)
        assert scores.overall == 10.0

    def test_overall_with_mixed_scores(self) -> None:
        scores = ReviewScores(8.0, 7.0, 6.0, 5.0)
        expected = round(8.0 * 0.35 + 7.0 * 0.30 + 6.0 * 0.20 + 5.0 * 0.15, 1)
        assert scores.overall == expected
