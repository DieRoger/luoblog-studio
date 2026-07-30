"""arXiv论文批量下载 + 上传到知识库

搜索与项目技术栈相关的最新论文，下载PDF并上传到LuoBlog知识库。
"""

import asyncio
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

# 项目技术栈关键词 — 覆盖所有核心模块
QUERIES = [
    "RAG evaluation metrics faithfulness",
    "Retrieval Augmented Generation pipeline",
    "LLM agent evaluation benchmark",
    "large language model hallucination detection",
    "semantic chunking document splitting",
    "dense passage retrieval embedding",
    "hybrid search vector BM25",
    "Clean Architecture Python backend",
    "FastAPI async web framework",
    "PGVector vector database performance",
    "LiteLLM gateway multi-provider",
    "AI content review automated evaluation",
    "multi-agent debate LLM reasoning",
    "knowledge graph document relationship",
    "evidence grounding fact verification",
    "AI writing assistant generation",
    "sentence transformer embedding model BGE",
    "code review automated static analysis",
    "RAGAS retrieval augmented generation",
    "agent orchestration LangGraph workflow",
]

ARXIV_API = "https://export.arxiv.org/api/query"
PAPERS_PER_QUERY = 3          # 每类搜3篇
MAX_TOTAL_PAPERS = 25          # 总共不超过25篇
DOWNLOAD_DIR = Path("papers")  # 下载目录


async def search_arxiv(query: str, max_results: int) -> list[dict]:
    """Search arXiv API for papers matching a query."""
    params = {
        "search_query": f"all:{urllib.parse.quote_plus(query)}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            print(f"  API error: {resp.status_code}")
            return []

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            pdf_link = None
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_link = link.get("href")
                    break

            if pdf_link:
                papers.append({
                    "title": (title.text or "").strip().replace("\n", " "),
                    "summary": (summary.text or "").strip()[:200].replace("\n", " "),
                    "pdf_url": pdf_link,
                    "arxiv_id": pdf_link.split("/")[-1].replace(".pdf", ""),
                })
        return papers


async def download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF file."""
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 10000:
                dest.write_bytes(resp.content)
                return True
            return False
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


async def upload_to_knowledge_base(pdf_path: Path, api_base: str) -> bool:
    """Upload a PDF to LuoBlog and trigger processing."""
    upload_url = f"{api_base}/api/v1/documents/upload"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                resp = await client.post(upload_url, files=files)
                if resp.status_code == 201:
                    doc_id = resp.json()["data"]["id"]

                    # Trigger processing pipeline
                    process_url = f"{api_base}/api/v1/knowledge/process/{doc_id}"
                    proc_resp = await client.post(process_url)
                    if proc_resp.status_code == 202:
                        print(f"    Uploaded + processing: {pdf_path.name}")
                        return True
                    else:
                        print(f"    Uploaded but process failed: {proc_resp.status_code}")
                        return False
                else:
                    print(f"    Upload failed: {resp.status_code} {resp.text[:100]}")
                    return False
    except Exception as e:
        print(f"    Upload error: {e}")
        return False


async def main():
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    # 默认API地址（可配置）
    api_base = os.environ.get("LUOBLOG_API", "http://localhost:8000")
    upload = os.environ.get("LUOBLOG_UPLOAD", "1") == "1"

    print(f"arXiv论文搜索与下载")
    print(f"API: {api_base}")
    print(f"自动上传: {'是' if upload else '否'}")
    print(f"搜索分类: {len(QUERIES)} 类")
    print()

    all_papers = []
    seen_ids = set()

    for i, query in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] 搜索: {query[:50]}...")

        # Add delay to respect arXiv rate limits
        await asyncio.sleep(1.5)
        papers = await search_arxiv(query, PAPERS_PER_QUERY)

        new_count = 0
        for p in papers:
            if p["arxiv_id"] not in seen_ids:
                seen_ids.add(p["arxiv_id"])
                all_papers.append(p)
                new_count += 1

        print(f"  找到 {new_count} 篇新论文 (累计 {len(all_papers)} 篇)")

        if len(all_papers) >= MAX_TOTAL_PAPERS:
            break

    # Truncate to max
    all_papers = all_papers[:MAX_TOTAL_PAPERS]

    print(f"\n=== 共找到 {len(all_papers)} 篇论文，开始下载 ===")

    success = 0
    for i, paper in enumerate(all_papers, 1):
        filename = f"{paper['arxiv_id']}.pdf"
        dest = DOWNLOAD_DIR / filename

        if dest.exists():
            print(f"  [{i}/{len(all_papers)}] 已存在: {paper['title'][:60]}...")
            success += 1
            continue

        print(f"  [{i}/{len(all_papers)}] 下载: {paper['title'][:60]}...")
        ok = await download_pdf(paper["pdf_url"], dest)
        if ok:
            success += 1
            print(f"    OK ({os.path.getsize(dest) // 1024} KB)")

            if upload:
                ok2 = await upload_to_knowledge_base(dest, api_base)
                if not ok2:
                    print(f"    Upload failed, continuing...")
        else:
            print(f"    FAILED")

        # Be nice to arXiv
        await asyncio.sleep(1)

    print(f"\n=== 完成: {success}/{len(all_papers)} 篇下载成功 ===")

    # Save manifest
    manifest = []
    for p in all_papers:
        manifest.append({"arxiv_id": p["arxiv_id"], "title": p["title"], "pdf_url": p["pdf_url"]})
    manifest_path = DOWNLOAD_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Manifest saved: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
