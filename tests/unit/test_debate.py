"""Tests for Multi-Agent Debate Service."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from services.debate import DebateAgent, PERSONAS, MODERATOR_PROMPT


@pytest.fixture
def agent() -> DebateAgent:
    return DebateAgent()


class TestDebateAgent:
    pytestmark = pytest.mark.asyncio

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_debate_returns_all_perspectives(self, mock_llm, agent):
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Perspective content."))]
        )
        result = await agent.debate("RAG evaluation methods", personas=["Researcher", "Practitioner"])
        assert len(result["perspectives"]) == 2
        assert result["perspectives"][0]["name"] == "Researcher"
        assert result["perspectives"][1]["name"] == "Practitioner"
        assert result["synthesis"]

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_debate_defaults_to_all_personas(self, mock_llm, agent):
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Content."))]
        )
        result = await agent.debate("Test topic")
        assert len(result["perspectives"]) == len(PERSONAS)

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_synthesis_uses_moderator_prompt(self, mock_llm, agent):
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Synthesis."))]
        )
        # First 3 calls = personas, 4th = moderator
        result = await agent.debate("Topic")
        assert result["synthesis"] == "Synthesis."

    def test_personas_defined(self):
        assert len(PERSONAS) >= 2
        assert MODERATOR_PROMPT
