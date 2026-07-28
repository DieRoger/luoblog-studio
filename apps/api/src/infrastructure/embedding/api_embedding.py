"""API-based embedding via LiteLLM — delegates to configured LLM provider.

Supports OpenAI (text-embedding-3-small, text-embedding-ada-002) and any
provider supported by LiteLLM's embedding API.
"""

import math
from types import MappingProxyType

from domain.embedding import EmbeddingService
from domain.errors import EmbeddingError
from logging_config import get_logger
from config import settings

logger = get_logger(__name__)

DEFAULT_BATCH_SIZE = 100

# Known embedding model dimensions — immutable for safety.
_DIM_MAP: MappingProxyType[str, int] = MappingProxyType({
    "openai/text-embedding-3-small": 1536,
    "openai/text-embedding-3-large": 3072,
    "openai/text-embedding-ada-002": 1536,
    "deepseek/deepseek-embedding": 1024,
})


def _l2_normalize(vec: list[float]) -> list[float]:
    """In-place L2 normalization. Returns the same list for convenience."""
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    for i in range(len(vec)):
        vec[i] /= norm
    return vec


class LiteLLMEmbeddingService(EmbeddingService):
    """Embedding via LiteLLM — routes to the configured provider's embedding API.

    Features:
      - Automatic batching (configurable max_batch_size)
      - L2 normalization for cosine-similarity compatibility
      - Dimension auto-detection on first request
    """

    def __init__(
        self,
        model: str | None = None,
        max_batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._model = model or self._default_embedding_model()
        self._max_batch_size = max_batch_size
        self._cached_dim: int | None = None
        logger.info("embedding.service_init", model=self._model, batch_size=max_batch_size)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            logger.warning("embedding.empty_input")
            return []

        import litellm

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._max_batch_size):
            batch = texts[i : i + self._max_batch_size]
            try:
                response = await litellm.aembedding(model=self._model, input=batch)
            except Exception as exc:
                logger.exception(
                    "embedding.api_failed",
                    model=self._model,
                    batch_start=i,
                    batch_size=len(batch),
                )
                raise EmbeddingError(f"API embedding failed at batch {i}: {exc}") from exc

            for item in response.data:
                vec: list[float] = item["embedding"]
                _l2_normalize(vec)
                all_embeddings.append(vec)

        # Cache dimension from first successful call
        if self._cached_dim is None and all_embeddings:
            self._cached_dim = len(all_embeddings[0])

        logger.info(
            "embedding.completed",
            model=self._model,
            text_count=len(texts),
            batches=len(texts) // self._max_batch_size + 1,
            dim=self._cached_dim or 0,
        )
        return all_embeddings

    async def embed_one(self, text: str) -> list[float]:
        if not text:
            logger.warning("embedding.empty_text")
            return []
        result = await self.embed([text])
        return result[0] if result else []

    @property
    def dimension(self) -> int:
        # Return cached dim from first API call, else fallback to map
        if self._cached_dim is not None:
            return self._cached_dim
        return _DIM_MAP.get(self._model, 1024)

    @staticmethod
    def _default_embedding_model() -> str:
        provider = settings.llm_provider
        model = settings.embedding_api_model
        if "/" not in model:
            model = f"{provider}/{model}"
        return model
