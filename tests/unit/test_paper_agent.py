"""Tests for Paper Agent."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from services.paper import PaperAgent


@pytest.fixture
def agent() -> PaperAgent:
    return PaperAgent()


class TestPaperAgent:
    pytestmark = pytest.mark.asyncio

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_analyze_parses_json(self, mock_llm, agent):
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"abstract_summary": "Test abstract.", "contributions": ["C1"], "experiments": [], "limitations": [], "engineering_insights": []}'))]
        )
        result = await agent.analyze("Test Paper", "Full text here.")
        assert result["abstract_summary"] == "Test abstract."
        assert result["contributions"] == ["C1"]

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_fallback_on_bad_json(self, mock_llm, agent):
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json at all"))]
        )
        result = await agent.analyze("Bad", "text")
        assert "abstract_summary" in result
        assert result["contributions"] == []

    def test_prompt_loaded(self, agent):
        assert agent._system_prompt
        assert "Paper Analysis Agent" in agent._system_prompt or "analyze" in agent._system_prompt.lower()
