"""Local BGE-m3 embedding via sentence-transformers.

Requires:
  pip install sentence-transformers

On first run, downloads model weights (~2.2 GB for BAAI/bge-m3).
Subsequent runs use a local cache.
"""

from domain.embedding import EmbeddingService
from domain.errors import EmbeddingError
from logging_config import get_logger
from config import settings

logger = get_logger(__name__)

BGE_M3_DIM = 1024


class LocalBgeEmbeddingService(EmbeddingService):
    """Local BGE-m3 embedding via sentence-transformers.

    Falls back gracefully if sentence-transformers is not installed.
    Model weights are downloaded on first call and cached locally.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.embedding_local_model
        self._model = None
        logger.info("embedding.local_init", model=self._model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            logger.warning("embedding.empty_input")
            return []

        model = await self._get_model()
        try:
            import functools

            import anyio

            fn = functools.partial(model.encode, texts, normalize_embeddings=True, show_progress_bar=False)
            embeddings = await anyio.to_thread.run_sync(fn)
        except Exception as exc:
            logger.exception("embedding.local_failed", model=self._model_name)
            raise EmbeddingError(f"Local embedding failed: {exc}") from exc

        result = [emb.tolist() for emb in embeddings]

        logger.info(
            "embedding.local_completed",
            model=self._model_name,
            text_count=len(texts),
            dim=len(result[0]) if result else 0,
        )
        return result

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0] if result else []

    @property
    def dimension(self) -> int:
        return BGE_M3_DIM

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    async def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            import anyio
            from sentence_transformers import SentenceTransformer

            self._model = await anyio.to_thread.run_sync(
                SentenceTransformer, self._model_name
            )
            logger.info("embedding.model_loaded", model=self._model_name)
            return self._model
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            ) from exc
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to load local model '{self._model_name}': {exc}"
            ) from exc
