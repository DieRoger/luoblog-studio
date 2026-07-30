"""Download papers from manifest, retry once, 30s timeout."""
import asyncio, json, os
from pathlib import Path
import httpx

MANIFEST = Path("papers/manifest.json")
DOWNLOAD_DIR = Path("papers")

async def download_one(url, dest, sem):
    async with sem:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, trust_env=False) as c:
                r = await c.get(url)
                if r.status_code == 200 and len(r.content) > 5000:
                    dest.write_bytes(r.content)
                    return True, len(r.content) // 1024
                return False, r.status_code
        except Exception as e:
            return False, type(e).__name__

async def main():
    if not MANIFEST.exists():
        print("Run scripts/fetch_papers.py first")
        return

    papers = json.loads(MANIFEST.read_text())
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(3)
    ok = 0

    for i, p in enumerate(papers, 1):
        title = p.get("title", "?")[:70]
        url = p.get("pdf_url", "")
        if not url:
            print(f"  [{i}] NO URL - {title}")
            continue

        fn = url.split("/")[-1].split("?")[0]
        if not fn.endswith(".pdf"):
            fn += ".pdf"
        dest = DOWNLOAD_DIR / fn

        if dest.exists():
            ok += 1
            print(f"  [{i}] EXISTS - {title}")
            continue

        print(f"  [{i}] DL - {title}")
        success, info = await download_one(url, dest, sem)
        if success:
            ok += 1
            print(f"       OK ({info} KB)")
        else:
            print(f"       FAIL ({info})")
            if dest.exists():
                dest.unlink()

    print(f"\nDownloaded: {ok}/{len(papers)}")

if __name__ == "__main__":
    asyncio.run(main())
