"""测试知识库检索效果 — 用已导入的论文做语义搜索验证"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "apps/api/src")

from sqlalchemy import select, text
from infrastructure.persistence.database import get_session
from infrastructure.persistence.models import DocumentModel, DocumentChunkModel
from infrastructure.embedding.fast_embedding import FastEmbeddingService

QUERIES = [
    "ReAct reasoning and acting in language models",
    "Toolformer teaching language models to use tools",
    "Reflexion verbal reinforcement learning for agents",
    "VOYAGER embodied lifelong learning agent Minecraft",
]

async def main():
    embedder = FastEmbeddingService()

    async for session in get_session():
        # 文档统计
        docs = await session.execute(select(DocumentModel.title, DocumentModel.source_path))
        doc_list = docs.all()
        print(f"知识库文档数: {len(doc_list)}")
        for title, path in doc_list[:6]:
            print(f"  - {title[:60]}")

        # 逐条查询测试
        for q in QUERIES:
            vec = (await embedder.embed_one(q))
            # 余弦相似度 = 1 - cosine_distance
            stmt = select(
                DocumentChunkModel.document_id,
                DocumentChunkModel.section,
                DocumentChunkModel.content,
                (1.0 - DocumentChunkModel.embedding.cosine_distance(vec)).label("score"),
            ).order_by(DocumentChunkModel.embedding.cosine_distance(vec)).limit(3)
            rows = await session.execute(stmt)
            print(f"\n=== 查询: {q[:50]} ===")
            for row in rows:
                doc = await session.get(DocumentModel, row.document_id)
                title = doc.title[:40] if doc else "?"
                score = float(row.score)
                content = row.content[:80].replace("\n", " ")
                print(f"  [{score:.3f}] {title} | {content}...")

asyncio.run(main())
