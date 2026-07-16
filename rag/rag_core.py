from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


RAG_DIR = Path(__file__).resolve().parent
ROOT = RAG_DIR.parent
CONFIG_PATH = RAG_DIR / "rag_config.json"
CHUNKS_PATH = RAG_DIR / "chunks" / "tunnel_rag_chunks.jsonl"
INDEX_PATH = RAG_DIR / "indexes" / "tunnel_rag_index.json"

ENGINEERING_KEYWORDS = [
    "超挖",
    "欠挖",
    "超欠挖",
    "监控量测",
    "量测",
    "新奥法",
    "钻爆",
    "爆破",
    "炮眼",
    "围岩",
    "围岩压力",
    "支护",
    "锚杆",
    "喷射混凝土",
    "衬砌",
    "初期支护",
    "二次衬砌",
    "坍方",
    "涌水",
    "地下水",
    "通风",
    "防排水",
    "施工组织",
    "养护",
    "病害",
    "掘进机",
    "TBM",
    "洞口",
    "断面",
    "开挖",
]

INTENT_LAYER_HINTS = {
    "operation_maintenance": ["养护", "运营", "维修", "病害", "渗漏", "火灾", "检查"],
    "qa_training_samples": ["习题", "考试", "名词解释", "简答", "训练样本"],
    "construction_methods": ["施工", "钻爆", "爆破", "炮眼", "新奥法", "TBM", "掘进机", "超挖", "欠挖", "监控量测", "开挖"],
    "engineering_principles": ["围岩", "围岩压力", "支护", "衬砌", "勘测", "设计", "洞门", "限界", "净空"],
}


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    text = text.replace("\u0007", " ").replace("\u0001", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chinese_sequences(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]+", text)


def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    tokens: list[str] = []
    tokens.extend(t.lower() for t in re.findall(r"[A-Za-z0-9_+.-]{2,}", text))
    for kw in ENGINEERING_KEYWORDS:
        if kw in text:
            tokens.append(kw)
            tokens.append(kw)
    for seq in chinese_sequences(text):
        if len(seq) == 1:
            tokens.append(seq)
            continue
        tokens.extend(seq[i : i + 2] for i in range(len(seq) - 1))
        if len(seq) >= 3:
            tokens.extend(seq[i : i + 3] for i in range(len(seq) - 2))
    return tokens


def infer_layer(question: str) -> str | None:
    scores = {}
    for layer, hints in INTENT_LAYER_HINTS.items():
        scores[layer] = sum(1 for h in hints if h.lower() in question.lower())
    if not scores:
        return None
    layer, score = max(scores.items(), key=lambda item: item[1])
    return layer if score > 0 else None


@lru_cache(maxsize=1)
def load_rag_index() -> dict[str, Any]:
    if not CHUNKS_PATH.exists() or not INDEX_PATH.exists():
        return {"available": False, "chunks": [], "index": {}, "config": load_config()}
    chunks = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"available": True, "chunks": chunks, "index": index, "config": load_config()}


def bm25_score(query_tokens: list[str], chunk_stat: dict[str, Any], index: dict[str, Any]) -> float:
    if not query_tokens:
        return 0.0
    tf = chunk_stat.get("tf", {})
    doc_len = max(1, int(chunk_stat.get("length", 1)))
    avgdl = max(1.0, float(index.get("avgdl", 1.0)))
    total_docs = max(1, int(index.get("total_docs", 1)))
    df = index.get("df", {})
    k1 = 1.5
    b = 0.75
    score = 0.0
    for token in query_tokens:
        freq = int(tf.get(token, 0))
        if freq <= 0:
            continue
        term_df = int(df.get(token, 0))
        idf = math.log(1 + (total_docs - term_df + 0.5) / (term_df + 0.5))
        score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_len / avgdl))
    return score


def boosted_score(question: str, query_tokens: list[str], chunk: dict[str, Any], chunk_stat: dict[str, Any], index: dict[str, Any]) -> float:
    score = bm25_score(query_tokens, chunk_stat, index)
    text = chunk.get("content", "")
    metadata = chunk.get("metadata", {})
    tags = metadata.get("topic_tags", []) + metadata.get("default_tags", [])
    for kw in ENGINEERING_KEYWORDS:
        if kw in question and kw in text:
            score += 1.15
    for tag in tags:
        if tag and str(tag) in question:
            score += 0.75
    hinted_layer = infer_layer(question)
    if hinted_layer and metadata.get("layer") == hinted_layer:
        score += 1.25
    if metadata.get("layer") == "qa_training_samples" and hinted_layer != "qa_training_samples":
        score -= 18.0
    if metadata.get("authority_level") == "教材参考":
        score += 0.1
    return score


def retrieve(question: str, top_k: int | None = None, min_score: float = 0.1) -> list[dict[str, Any]]:
    state = load_rag_index()
    if not state.get("available"):
        return []
    config = state["config"]
    top_k = top_k or int(config.get("retrieval", {}).get("default_top_k", 6))
    query_tokens = tokenize(question)
    if not query_tokens:
        return []
    chunks = state["chunks"]
    index = state["index"]
    stats = index.get("chunks", {})
    scored = []
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        chunk_stat = stats.get(chunk_id)
        if not chunk_stat:
            continue
        score = boosted_score(question, query_tokens, chunk, chunk_stat, index)
        if score >= min_score:
            item = dict(chunk)
            item["score"] = round(score, 4)
            scored.append(item)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def source_label(item: dict[str, Any]) -> str:
    meta = item.get("metadata", {})
    chapter = meta.get("chapter") or "-"
    source_file = meta.get("source_file") or meta.get("file") or "-"
    layer_label = meta.get("layer_label") or meta.get("layer") or "-"
    return f"{chapter} / {source_file} / {layer_label}"


def retrieve_for_prompt(question: str, top_k: int | None = None, max_context_chars: int | None = None) -> dict[str, Any]:
    state = load_rag_index()
    config = state.get("config") or load_config()
    max_context_chars = max_context_chars or int(config.get("retrieval", {}).get("max_context_chars", 5200))
    results = retrieve(question, top_k=top_k)
    if not results:
        return {"available": state.get("available", False), "context": "", "sources": [], "results": []}
    parts = [
        "RAG知识库检索结果：以下内容来自隧道工程资料库。资料优先级低于平台实时数据、项目文件和现行规范；若回答采用这些内容，请注明资料来源。"
    ]
    sources = []
    seen_sources = set()
    used_chars = len(parts[0])
    for idx, item in enumerate(results, start=1):
        meta = item.get("metadata", {})
        content = normalize_text(item.get("content", ""))
        snippet = content[:900]
        label = source_label(item)
        block = (
            f"\n[{idx}] 来源：{label}；权威级别：{meta.get('authority_level', '资料参考')}；"
            f"主题：{', '.join(meta.get('topic_tags', [])[:8])}\n内容：{snippet}"
        )
        if used_chars + len(block) > max_context_chars:
            break
        parts.append(block)
        used_chars += len(block)
        if label not in seen_sources:
            seen_sources.add(label)
            sources.append(
                {
                    "rank": len(sources) + 1,
                    "score": item.get("score"),
                    "chunk_id": item.get("chunk_id"),
                    "source": label,
                    "chapter": meta.get("chapter"),
                    "source_file": meta.get("source_file"),
                    "layer": meta.get("layer"),
                    "layer_label": meta.get("layer_label"),
                    "authority_level": meta.get("authority_level"),
                }
            )
    return {"available": True, "context": "\n".join(parts), "sources": sources, "results": results}


def clear_cache() -> None:
    load_rag_index.cache_clear()
