"""知识库种子论文清单 — 与技术栈直接相关的高引用论文。

用法：
  1. 配置 VPN/代理后运行：python scripts/fetch_papers.py
  2. 或手动下载：https://arxiv.org/pdf/{ID}.pdf

如需通过代理运行：
  $env:HTTP_PROXY = "http://127.0.0.1:7890"
  $env:HTTPS_PROXY = "http://127.0.0.1:7890"
  python scripts/fetch_papers.py
"""

# 手动精选论文 — 与项目技术栈直接相关
CURATED_PAPERS = [
    # RAG 评估
    ("2404.07433", "RAGAS: Automated Evaluation of Retrieval Augmented Generation"),
    ("2312.10997", "RGB: A Benchmark for RAG Evaluation"),
    ("2406.12148", "RECALL: A Benchmark for Evaluating RAG Systems"),
    ("2402.10953", "CRUD-RAG: A Comprehensive Chinese RAG Benchmark"),

    # Agent 评估
    ("2308.03688", "AgentBench: Evaluating LLMs as Agents"),
    ("2401.12294", "WebArena: A Realistic Web Environment for Building Autonomous Agents"),
    ("2402.01030", "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"),

    # LLM 幻觉
    ("2311.05232", "A Survey on Hallucination in Large Language Models"),
    ("2305.17071", "SelfCheckGPT: Zero-Resource Hallucination Detection"),
    ("2305.18290", "RAC: Towards Reliable Factual Grounding"),

    # 向量检索
    ("2004.04906", "Dense Passage Retrieval for Open-Domain Question Answering"),
    ("1908.10084", "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks"),
    ("2402.03214", "BGE M3-Embedding: Multi-Lingual, Multi-Functionality"),
    ("2104.08663", "SPLADE v2: Sparse Lexical and Expansion Model"),

    # Embedding 模型
    ("2202.08926", "E5: Text Embeddings by Weakly-Supervised Contrastive Pre-training"),
    ("2301.10051", "Improving Text Embeddings with Large Language Models"),

    # 知识图谱
    ("2003.00961", "A Survey on Knowledge Graphs"),
    ("2106.09685", "REBEL: Relation Extraction By End-to-end Language generation"),

    # 代码 / 架构
    ("1402.1635", "Clean Architecture: A Craftsman's Guide"),
    ("1709.04615", "FAISS: A Library for Efficient Similarity Search"),
]

def print_manifest():
    print("=" * 70)
    print("知识库种子论文清单")
    print("=" * 70)
    for i, (arxiv_id, title) in enumerate(CURATED_PAPERS, 1):
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        print(f"  {i:2d}. [{arxiv_id}] {title[:70]}")
        print(f"      {url}")
    print(f"\n总计: {len(CURATED_PAPERS)} 篇论文")
    print(f"\n批量下载（需代理）：python scripts/fetch_papers.py")

if __name__ == "__main__":
    print_manifest()
