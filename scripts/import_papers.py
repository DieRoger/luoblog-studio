"""将 papers/ 目录下的论文批量导入 LuoBlog 知识库。

流程: PDF → PdfParser → Chunking → Embedding (fastembed) → PGVector
"""

import asyncio
import os
import sys
from pathlib import Path

# LuoBlog API src 在 new/luoblog-studio/apps/api/src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api" / "src"))

from domain.enums import DocumentStatus
from infrastructure.persistence.database import get_session
from infrastructure.persistence.repositories import DocumentRepository, ChunkRepository
from infrastructure.parsing.pdf_parser import PdfParser
from services.chunking import ChunkingService
from logging_config import get_logger

logger = get_logger(__name__)

# 用户下载的论文在 workspace 根目录的 papers/
PAPERS_ROOT = Path(os.environ.get("PAPERS_ROOT", str(Path(__file__).resolve().parents[2] / "papers")))
MAX_PDFS = int(os.environ.get("MAX_PDFS", "30"))


async def main():
    # 收集所有 PDF
    pdfs = sorted(PAPERS_ROOT.rglob("*.pdf"))
    pdfs = [p for p in pdfs if "books" not in str(p)]
    pdfs = pdfs[:MAX_PDFS]
    print(f"找到 {len(pdfs)} 篇论文")

    parser = PdfParser()
    chunker = ChunkingService()

    # fastembed embedding service
    from infrastructure.embedding.fast_embedding import FastEmbeddingService
    embedder = FastEmbeddingService()

    # 测试 embedding 可用性
    test_vec = await embedder.embed_one("test")
    print(f"Embedding dim: {len(test_vec)}")
    if len(test_vec) != 1024:
        print(f"WARNING: 期望 1024 维 (ORM Vector(1024))，实际 {len(test_vec)} 维")

    async for session in get_session():
        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)

        # 已导入的论文（按 source_path 去重）
        from sqlalchemy import select, text
        from infrastructure.persistence.models import DocumentModel

        result = await session.execute(
            select(DocumentModel.source_path).where(DocumentModel.deleted_at.is_(None))
        )
        imported_paths = {row[0] for row in result}
        print(f"已导入 {len(imported_paths)} 篇，跳过重复")

        imported = 0
        for pdf_path in pdfs:
            rel = str(pdf_path.relative_to(PAPERS_ROOT))

            # 跳过已导入
            abs_path = str(pdf_path)
            if abs_path in imported_paths:
                print(f"\n[SKIP] {rel} (已导入)")
                continue

            print(f"\n[{imported+1}/{len(pdfs)}] {rel}")

            # 1. 解析
            try:
                parsed = parser.parse(str(pdf_path))
            except Exception as e:
                print(f"  PARSE FAILED: {e}")
                continue

            # 2. 分块
            chunks = chunker.chunk(parsed, document_id=None)
            if not chunks:
                print(f"  NO CHUNKS")
                continue

            # 3. 嵌入
            texts = [c.content for c in chunks]
            try:
                embeddings = await embedder.embed(texts)
            except Exception as e:
                print(f"  EMBED FAILED: {e}")
                continue

            # 4. 存储 — 需要先建 Document 记录
            import uuid
            from domain.entities import Document
            from domain.enums import FileType

            doc = Document(
                id=uuid.uuid4(),
                title=pdf_path.stem,
                file_type=FileType.PDF,
                status=DocumentStatus.READY,
                source_path=str(pdf_path),
                metadata={"source": "arxiv", "chunk_count": len(chunks)},
            )
            saved_doc = await doc_repo.save(doc)

            # 5. 保存 chunks + embeddings
            for chunk, vec in zip(chunks, embeddings, strict=False):
                chunk.document_id = saved_doc.id
                chunk.metadata["embedding"] = vec
                # 清洗 PostgreSQL 无法存储的字符（\x00 等）
                chunk.content = chunk.content.replace("\x00", "")
                if chunk.section:
                    chunk.section = chunk.section.replace("\x00", "")

            await chunk_repo.save_batch(chunks)
            await session.commit()
            imported += 1
            print(f"  OK: {len(chunks)} chunks, {len(texts)} texts embedded")

        print(f"\n=== 导入完成: {imported}/{len(pdfs)} 篇 ===")


if __name__ == "__main__":
    asyncio.run(main())
