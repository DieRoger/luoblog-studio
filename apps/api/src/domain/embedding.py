"""Embedding service abstraction — domain interface.

All embedding implementations must conform to this contract.
Callers depend on this ABC, never on concrete implementations.
"""

from abc import ABC, abstractmethod


class EmbeddingService(ABC):
    """Abstract embedding service. Implementations handle local model inference
    or API calls via LiteLLM.
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, each a list of floats.
            Order matches input order.

        Raises:
            EmbeddingError: if the service fails (network, model, etc.).
        """
        ...

    @abstractmethod
    async def embed_one(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension (e.g., 1024 for BGE-m3)."""
        ...
