"""论文搜索与下载 — 使用 Semantic Scholar API（不受 arXiv 限流影响）

搜索与技术栈相关论文，下载PDF并上传到LuoBlog知识库。
"""

import asyncio
import json
import os
from pathlib import Path

import httpx

API_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"

QUERIES = [
    "RAG evaluation metrics",
    "Retrieval Augmented Generation",
    "LLM agent evaluation",
    "hallucination detection LLM",
    "semantic chunking documents",
    "dense passage retrieval",
    "hybrid search vector",
    "BGE embedding model",
    "evidence grounding fact",
    "sentence transformer embedding",
    "multi-agent LLM debate",
    "knowledge graph extraction",
]

PAPERS_PER_QUERY = 3
MAX_TOTAL = 25
DOWNLOAD_DIR = Path("papers")


async def search(query: str, limit: int) -> list[dict]:
    params = {"query": query, "limit": limit, "fields": "title,url,externalIds"}
    url = f"{API_BASE}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    async with httpx.AsyncClient(timeout=30, trust_env=False) as c:
        try:
            r = await c.get(url)
            if r.status_code != 200:
                print(f"  API {r.status_code}")
                return []
            data = r.json()
            papers = []
            for p in data.get("data", []):
                ext = p.get("externalIds") or {}
                arxiv_id = ext.get("ArXiv", "")
                title = (p.get("title") or "").strip()
                pdf = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""
                if pdf:
                    papers.append({"title": title, "pdf_url": pdf, "arxiv_id": arxiv_id})
            return papers
        except Exception as e:
            print(f"  Error: {e}")
            return []


async def download(url: str, dest: Path) -> bool:
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True, trust_env=False) as c:
            r = await c.get(url)
            if r.status_code == 200 and len(r.content) > 10000:
                dest.write_bytes(r.content)
                return True
            return False
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


async def main():
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    upload = os.environ.get("UPLOAD", "0") == "1"
    api_base = os.environ.get("API", "http://localhost:8000")

    print(f"搜索论文: {len(QUERIES)} 类, 每类最多 {PAPERS_PER_QUERY} 篇")
    print(f"最多 {MAX_TOTAL} 篇, 自动上传: {'是' if upload else '否'}")

    all_papers, seen = [], set()
    for i, q in enumerate(QUERIES, 1):
        print(f"\n[{i}/{len(QUERIES)}] {q[:50]}...")
        await asyncio.sleep(0.5)
        papers = await search(q, PAPERS_PER_QUERY)
        new = [p for p in papers if p["arxiv_id"] not in seen]
        for p in new:
            seen.add(p["arxiv_id"])
            all_papers.append(p)
        print(f"  新增 {len(new)} 篇, 累计 {len(all_papers)}")
        if len(all_papers) >= MAX_TOTAL:
            break

    all_papers = all_papers[:MAX_TOTAL]
    print(f"\n共 {len(all_papers)} 篇, 开始下载...")

    ok_count = 0
    for i, p in enumerate(all_papers, 1):
        fn = f"{p['arxiv_id']}.pdf"
        dest = DOWNLOAD_DIR / fn
        if dest.exists():
            ok_count += 1
            continue
        print(f"  [{i}] {p['title'][:60]}...")
        if await download(p["pdf_url"], dest):
            ok_count += 1
            size = os.path.getsize(dest) // 1024
            print(f"    OK ({size} KB)")
            if upload:
                async with httpx.AsyncClient(timeout=60, trust_env=False) as c:
                    with open(dest, "rb") as f:
                        r1 = await c.post(f"{api_base}/api/v1/documents/upload", files={"file": (fn, f, "application/pdf")})
                        if r1.status_code == 201:
                            doc_id = r1.json()["data"]["id"]
                            await c.post(f"{api_base}/api/v1/knowledge/process/{doc_id}")
                            print(f"    Uploaded + processing")
        else:
            print(f"    FAILED")
        await asyncio.sleep(0.5)

    print(f"\n完成: {ok_count}/{len(all_papers)} 篇")
    (DOWNLOAD_DIR / "manifest.json").write_text(
        json.dumps([{"arxiv_id": p["arxiv_id"], "title": p["title"]} for p in all_papers], indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    asyncio.run(main())
