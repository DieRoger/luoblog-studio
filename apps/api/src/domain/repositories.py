"""Repository interfaces (Abstract Base Classes).

Domain layer defines WHAT persistence looks like. Infrastructure layer
provides the SQLAlchemy implementation. Services depend on these ABCs,
never on concrete implementations.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from domain.entities import AgentTask, Article, Claim, Document, DocumentChunk, Evidence


class DocumentRepository(ABC):
    @abstractmethod
    async def save(self, document: Document) -> Document: ...

    @abstractmethod
    async def get_by_id(self, doc_id: UUID) -> Document | None: ...

    @abstractmethod
    async def list_all(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[Document], int]: ...

    @abstractmethod
    async def delete(self, doc_id: UUID) -> None: ...


class ChunkRepository(ABC):
    @abstractmethod
    async def save_batch(self, chunks: Sequence[DocumentChunk]) -> Sequence[DocumentChunk]: ...

    @abstractmethod
    async def get_by_document(self, doc_id: UUID) -> Sequence[DocumentChunk]: ...

    @abstractmethod
    async def vector_search(
        self, embedding: list[float], top_k: int = 10
    ) -> Sequence[tuple[DocumentChunk, float]]: ...

    @abstractmethod
    async def hybrid_search(
        self, query: str, embedding: list[float], top_k: int = 10
    ) -> Sequence[tuple[DocumentChunk, float]]: ...

    @abstractmethod
    async def delete_by_document(self, doc_id: UUID) -> None: ...


class ArticleRepository(ABC):
    @abstractmethod
    async def save(self, article: Article) -> Article: ...

    @abstractmethod
    async def get_by_id(self, article_id: UUID) -> Article | None: ...

    @abstractmethod
    async def list_all(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[Article], int]: ...

    @abstractmethod
    async def delete(self, article_id: UUID) -> None: ...


class EvidenceRepository(ABC):
    @abstractmethod
    async def save(self, evidence: Evidence) -> Evidence: ...

    @abstractmethod
    async def get_by_claim(self, claim_id: UUID) -> Sequence[Evidence]: ...

    @abstractmethod
    async def get_by_chunk(self, chunk_id: UUID) -> Sequence[Evidence]: ...


class ClaimRepository(ABC):
    @abstractmethod
    async def save(self, claim: Claim) -> Claim: ...

    @abstractmethod
    async def get_by_article(self, article_id: UUID) -> Sequence[Claim]: ...


class AgentTaskRepository(ABC):
    @abstractmethod
    async def save(self, task: AgentTask) -> AgentTask: ...

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> AgentTask | None: ...

    @abstractmethod
    async def list_recent(self, limit: int = 20) -> Sequence[AgentTask]: ...
