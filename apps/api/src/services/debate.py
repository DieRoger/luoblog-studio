"""Multi-Agent Debate — multiple perspectives on a topic, synthesized into balanced output.

Pattern:
  Topic → 2-3 Agent Personas (independent perspectives) → Moderator (synthesis)
"""

from config import settings
from domain.errors import LLMError
from logging_config import get_logger

logger = get_logger(__name__)

# Persona definitions — each agent has a distinct role and system prompt
PERSONAS = [
    {
        "name": "Researcher",
        "role": "academic researcher",
        "prompt": (
            "You are a rigorous academic researcher. Your job is to analyze topics "
            "based on published papers, empirical evidence, and established theory. "
            "Cite specific research when possible. Be precise and cautious about claims. "
            "Focus on what the evidence says, not what's fashionable."
        ),
    },
    {
        "name": "Practitioner",
        "role": "industry practitioner",
        "prompt": (
            "You are an experienced industry practitioner who builds real systems. "
            "Your job is to analyze topics based on practical experience, engineering "
            "trade-offs, and production lessons. Focus on what actually works in practice, "
            "not just theory. Be honest about failures and limitations."
        ),
    },
    {
        "name": "Critic",
        "role": "devil's advocate",
        "prompt": (
            "You are a constructive critic. Your job is to identify weaknesses, "
            "unexamined assumptions, and potential failure modes. Push back on claims "
            "that lack evidence. Ask hard questions. Your goal is to strengthen the "
            "final analysis by stress-testing every position."
        ),
    },
]

MODERATOR_PROMPT = (
    "You are a technical moderator. Your job is to synthesize the following "
    "perspectives into a balanced, actionable analysis. Identify areas of "
    "agreement, disagreement, and unresolved questions. Produce a final "
    "analysis that an engineer can use to make decisions."
)


class DebateAgent:
    """Run a multi-perspective debate on a topic and synthesize results."""

    async def debate(
        self,
        topic: str,
        personas: list[str] | None = None,
    ) -> dict:
        """Run a multi-agent debate on a topic.

        Args:
            topic: The question or topic to debate.
            personas: List of persona names ("Researcher", "Practitioner", "Critic").
                      Defaults to all three.

        Returns:
            dict with perspectives (list of {name, role, content}) and synthesis.
        """
        logger.info("debate.start", topic=topic)

        selected = [p for p in PERSONAS if personas is None or p["name"] in personas]
        if not selected:
            selected = PERSONAS

        # Phase 1: Each persona writes their perspective independently
        perspectives = []
        for persona in selected:
            content = await self._call_persona(persona, topic)
            perspectives.append(
                {
                    "name": persona["name"],
                    "role": persona["role"],
                    "content": content,
                }
            )
            logger.info("debate.perspective", persona=persona["name"])

        # Phase 2: Moderator synthesizes all perspectives
        synthesis = await self._synthesize(topic, perspectives)
        logger.info("debate.complete", topic=topic, perspectives=len(perspectives))

        return {
            "topic": topic,
            "perspectives": perspectives,
            "synthesis": synthesis,
        }

    async def _call_persona(self, persona: dict, topic: str) -> str:
        """Call LLM with a specific persona's system prompt."""
        import litellm

        prompt = f"Analyze the following topic from your perspective:\n\n{topic}"
        try:
            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=[
                    {"role": "system", "content": persona["prompt"]},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"Debate persona '{persona['name']}' failed: {exc}") from exc

    async def _synthesize(self, topic: str, perspectives: list[dict]) -> str:
        """Call LLM as moderator to synthesize all perspectives."""
        import litellm

        context = f"Topic: {topic}\n\n"
        for p in perspectives:
            context += f"--- {p['name']} ({p['role']}) ---\n{p['content'][:2000]}\n\n"

        prompt = f"{context}\nSynthesize these perspectives into a balanced analysis."
        try:
            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=[
                    {"role": "system", "content": MODERATOR_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"Debate synthesis failed: {exc}") from exc
