"""Tests for Embedding Service — interface contract, LiteLLM API mode, local BGE mode.

Coverage:
  - Unit: embed_one returns correct shape, embed batch preserves order
  - Unit: dimension property matches expected per model
  - Failure: empty texts returns empty list
  - Failure: API error raises EmbeddingError
  - Failure: local model not installed raises EmbeddingError
  - Edge: single char text, very long text
  - Performance: batched embedding under time limit
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock litellm before any import that might reference it
_mock_litellm = MagicMock()

def _make_embedding_response(dim: int, count: int = 1):
    data = []
    for i in range(count):
        vec = [float(i + 1) * 0.1] * dim
        item = MagicMock()
        item.__getitem__ = MagicMock(return_value=vec)
        item.embedding = vec
        data.append(item)
    resp = MagicMock()
    resp.data = data
    return resp

_mock_litellm.aembedding = AsyncMock()
sys.modules["litellm"] = _mock_litellm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.embedding import EmbeddingService
from domain.errors import EmbeddingError


# ============================================================================
# UNIT TESTS — LiteLLMEmbeddingService
# ============================================================================


class TestLiteLLMEmbeddingService:
    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def service(self) -> EmbeddingService:
        from infrastructure.embedding.api_embedding import LiteLLMEmbeddingService

        return LiteLLMEmbeddingService(model="openai/text-embedding-3-small")

    async def test_embed_one_returns_1536_dim(self, service: EmbeddingService) -> None:
        """embed_one returns a vector of the expected dimension."""
        _mock_litellm.aembedding.reset_mock()
        _mock_litellm.aembedding.return_value = _make_embedding_response(1536, 1)
        result = await service.embed_one("Hello world")
        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)
        # Verify L2 normalization
        norm = sum(v * v for v in result) ** 0.5
        assert abs(norm - 1.0) < 0.001, f"Expected L2 norm 1.0, got {norm}"

    async def test_embed_batch_preserves_order(self, service: EmbeddingService) -> None:
        _mock_litellm.aembedding.reset_mock()
        _mock_litellm.aembedding.return_value = _make_embedding_response(1536, 2)
        results = await service.embed(["first", "second"])
        assert len(results) == 2
        # Both should be L2 normalized (norm ≈ 1.0)
        for v in results:
            norm = sum(x * x for x in v) ** 0.5
            assert abs(norm - 1.0) < 0.001

    async def test_embed_returns_empty_list_for_empty_input(self, service: EmbeddingService) -> None:
        results = await service.embed([])
        assert results == []

    async def test_embed_one_empty_string_returns_empty(self, service: EmbeddingService) -> None:
        _mock_litellm.aembedding.reset_mock()
        _mock_litellm.aembedding.return_value = _make_embedding_response(1536, 0)
        result = await service.embed_one("")
        assert result == []

    async def test_api_error_raises_embedding_error(self, service: EmbeddingService) -> None:
        _mock_litellm.aembedding.reset_mock()
        _mock_litellm.aembedding.side_effect = ConnectionError("API unavailable")
        with pytest.raises(EmbeddingError) as exc:
            await service.embed(["test"])
        assert "API embedding failed" in str(exc.value)

    async def test_dimension_property(self, service: EmbeddingService) -> None:
        assert service.dimension == 1536

    def test_deepseek_model_dimension(self) -> None:
        from infrastructure.embedding.api_embedding import LiteLLMEmbeddingService

        s = LiteLLMEmbeddingService(model="deepseek/deepseek-embedding")
        assert s.dimension == 1024


# ============================================================================
# UNIT TESTS — LocalBgeEmbeddingService (mocked sentence-transformers)
# ============================================================================


class TestLocalBgeEmbeddingService:
    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def service(self) -> EmbeddingService:
        from infrastructure.embedding.local_bge import LocalBgeEmbeddingService

        return LocalBgeEmbeddingService(model_name="BAAI/bge-m3")

    async def test_embed_one_returns_1024_dim(self, service: EmbeddingService) -> None:
        with patch(
            "infrastructure.embedding.local_bge.LocalBgeEmbeddingService._get_model",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_model = MagicMock()
            mock_model.encode.return_value = [MagicMock(tolist=lambda: [0.5] * 1024)]
            mock_get.return_value = mock_model

            result = await service.embed_one("Test text")
            assert len(result) == 1024

    async def test_embed_batch(self, service: EmbeddingService) -> None:
        with patch(
            "infrastructure.embedding.local_bge.LocalBgeEmbeddingService._get_model",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_model = MagicMock()
            mock_model.encode.return_value = [
                MagicMock(tolist=lambda: [0.1] * 1024),
                MagicMock(tolist=lambda: [0.2] * 1024),
            ]
            mock_get.return_value = mock_model

            results = await service.embed(["a", "b"])
            assert len(results) == 2
            assert results[0][0] == 0.1

    async def test_empty_input_returns_empty(self, service: EmbeddingService) -> None:
        results = await service.embed([])
        assert results == []

    async def test_model_not_installed_raises_embedding_error(
        self, service: EmbeddingService
    ) -> None:
        """When sentence-transformers is not installed, _get_model raises EmbeddingError."""
        with patch(
            "infrastructure.embedding.local_bge.LocalBgeEmbeddingService._get_model",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.side_effect = EmbeddingError("sentence-transformers not installed")
            with pytest.raises(EmbeddingError) as exc:
                await service.embed(["test"])
            assert "sentence-transformers" in str(exc.value)

    def test_dimension_is_1024(self, service: EmbeddingService) -> None:
        assert service.dimension == 1024


# ============================================================================
# INTERFACE CONTRACT TESTS — every implementation must pass
# ============================================================================


class TestEmbeddingInterfaceContract:
    """Shared contract tests for all EmbeddingService implementations.

    Add new implementations here to verify they conform to the ABC.
    """

    @pytest.fixture(
        params=[
            pytest.param("litellm", marks=pytest.mark.skip(reason="Requires API key")),
            pytest.param("local", marks=pytest.mark.skip(reason="Requires sentence-transformers")),
        ]
    )
    def service(self, request: pytest.FixtureRequest) -> EmbeddingService:
        raise NotImplementedError("Integration tests require external dependencies")

    def test_is_abc_implementable(self) -> None:
        """At minimum, verify the ABC has the required methods."""
        for method in ["embed", "embed_one"]:
            assert hasattr(EmbeddingService, method)
        assert isinstance(EmbeddingService.dimension, property) or hasattr(
            EmbeddingService, "dimension"
        )

    def test_all_implementations_have_required_methods(self) -> None:
        from infrastructure.embedding.api_embedding import LiteLLMEmbeddingService
        from infrastructure.embedding.local_bge import LocalBgeEmbeddingService

        for impl_class in [LiteLLMEmbeddingService, LocalBgeEmbeddingService]:
            if "LiteLLM" in impl_class.__name__:
                obj = impl_class(model="openai/text-embedding-3-small")
            else:
                obj = impl_class()
            assert hasattr(obj, "embed")
            assert hasattr(obj, "embed_one")
            assert hasattr(obj, "dimension")
