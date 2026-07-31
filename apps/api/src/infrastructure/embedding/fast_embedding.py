"""FastEmbed embedding via fastembed (ONNX runtime, no torch dependency).

Uses BAAI/bge-large-en-v1.5 (1024 dim) — matches ORM Vector(1024).
Zero API cost, local inference.
"""

from domain.embedding import EmbeddingService
from domain.errors import EmbeddingError
from logging_config import get_logger

logger = get_logger(__name__)

MODEL_NAME = "BAAI/bge-large-en-v1.5"
DIM = 1024


class FastEmbeddingService(EmbeddingService):
    """Local embedding via fastembed — ONNX, no torch needed."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None
        logger.info("embedding.fastembed_init", model=model_name, dim=DIM)

    def _get_or_load_model(self):
        """Lazy-load the fastembed model (sync)."""
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
            logger.info("embedding.model_loaded", model=self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            logger.warning("embedding.empty_input")
            return []

        try:
            import anyio

            model = self._get_or_load_model()

            def _run() -> list[list[float]]:
                return [vec.tolist() for vec in model.embed(texts)]

            embeddings = await anyio.to_thread.run_sync(_run)
            logger.info("embedding.fastembed_completed", text_count=len(texts), dim=DIM)
            return embeddings
        except Exception as exc:
            logger.exception("embedding.fastembed_failed", model=self._model_name)
            raise EmbeddingError(f"FastEmbed embedding failed: {exc}") from exc

    async def embed_one(self, text: str) -> list[float]:
        if not text:
            logger.warning("embedding.empty_text")
            return []
        result = await self.embed([text])
        return result[0] if result else []

    @property
    def dimension(self) -> int:
        return DIM
