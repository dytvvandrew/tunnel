from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from rag_core import RAG_DIR, load_config, normalize_text, tokenize


DEFAULT_SOURCE_DIR = RAG_DIR / "processed" / "tunnel_engineering_old_textbook_ascii"
CHUNKS_DIR = RAG_DIR / "chunks"
INDEX_DIR = RAG_DIR / "indexes"
METADATA_DIR = RAG_DIR / "metadata"


def is_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 120:
        return False
    if re.match(r"^第[0-9一二三四五六七八九十百]+[章节]", line):
        return True
    if re.match(r"^[一二三四五六七八九十]+[、．.]", line):
        return True
    if re.match(r"^\(?[一二三四五六七八九十]\)", line):
        return True
    if re.match(r"^\d+[、．.]", line):
        return True
    return False


def paragraph_blocks(text: str) -> list[dict]:
    lines = [line.strip() for line in normalize_text(text).splitlines()]
    blocks = []
    current_heading = ""
    buffer = []
    for line in lines:
        if not line:
            if buffer:
                blocks.append({"heading": current_heading, "text": "\n".join(buffer)})
                buffer = []
            continue
        if is_heading(line):
            if buffer:
                blocks.append({"heading": current_heading, "text": "\n".join(buffer)})
                buffer = []
            current_heading = line
            blocks.append({"heading": current_heading, "text": line})
        else:
            buffer.append(line)
    if buffer:
        blocks.append({"heading": current_heading, "text": "\n".join(buffer)})
    return blocks


def chunk_document(doc_meta: dict, text: str, config: dict) -> list[dict]:
    max_chars = int(config.get("chunking", {}).get("max_chars", 900))
    overlap = int(config.get("chunking", {}).get("overlap_chars", 140))
    layers = config["layers"]
    layer = doc_meta["layer"]
    layer_conf = layers[layer]
    blocks = paragraph_blocks(text)
    chunks = []
    current_parts = []
    current_heading = ""

    def emit() -> None:
        nonlocal current_parts
        if not current_parts:
            return
        content = normalize_text("\n".join(current_parts))
        if not content:
            current_parts = []
            return
        chunk_no = len(chunks) + 1
        chunk_id = f"{doc_meta['file'].rsplit('.', 1)[0]}_{chunk_no:04d}"
        metadata = {
            "doc_id": doc_meta["file"].rsplit(".", 1)[0],
            "file": doc_meta["file"],
            "source_file": doc_meta["source_file"],
            "source_type": "教材",
            "chapter": doc_meta["chapter"],
            "section": current_heading,
            "layer": layer,
            "layer_label": layer_conf["label"],
            "knowledge_domain": layer_conf["label"],
            "authority_level": layer_conf["authority_level"],
            "topic_tags": sorted(set(layer_conf.get("default_tags", []) + doc_meta.get("topic_tags", []))),
            "project_scope": "通用隧道工程",
        }
        chunks.append({"chunk_id": chunk_id, "content": content, "metadata": metadata})
        if overlap > 0 and len(content) > overlap:
            current_parts = [content[-overlap:]]
        else:
            current_parts = []

    for block in blocks:
        block_text = block["text"]
        if block.get("heading"):
            current_heading = block["heading"]
        prospective_len = len("\n".join(current_parts)) + len(block_text) + 1
        if current_parts and prospective_len > max_chars:
            emit()
        if len(block_text) > max_chars:
            start = 0
            while start < len(block_text):
                piece = block_text[start : start + max_chars]
                current_parts.append(piece)
                emit()
                start += max_chars - overlap
        else:
            current_parts.append(block_text)
    emit()
    return chunks


def build_index(source_dir: Path) -> dict:
    config = load_config()
    all_chunks = []
    missing = []
    for doc_meta in config["documents"]:
        path = source_dir / doc_meta["file"]
        if not path.exists():
            missing.append(str(path))
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        all_chunks.extend(chunk_document(doc_meta, text, config))

    token_stats = {}
    df = Counter()
    total_len = 0
    for chunk in all_chunks:
        tokens = tokenize(chunk["content"] + " " + " ".join(chunk["metadata"].get("topic_tags", [])))
        counts = Counter(tokens)
        token_stats[chunk["chunk_id"]] = {"length": sum(counts.values()), "tf": dict(counts)}
        total_len += sum(counts.values())
        for token in counts:
            df[token] += 1

    avgdl = total_len / max(1, len(all_chunks))
    index = {
        "version": config["version"],
        "built_at": int(time.time()),
        "source_dir": str(source_dir),
        "total_docs": len(all_chunks),
        "avgdl": avgdl,
        "df": dict(df),
        "chunks": token_stats,
        "missing_files": missing,
    }

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    chunks_path = CHUNKS_DIR / "tunnel_rag_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as fh:
        for chunk in all_chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    index_path = INDEX_DIR / "tunnel_rag_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "name": config["name"],
        "version": config["version"],
        "built_at": index["built_at"],
        "source_dir": str(source_dir),
        "chunk_count": len(all_chunks),
        "missing_files": missing,
        "layers": config["layers"],
        "outputs": {
            "chunks": str(chunks_path),
            "index": str(index_path),
        },
    }
    manifest_path = METADATA_DIR / "tunnel_rag_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    args = parser.parse_args()
    manifest = build_index(Path(args.source_dir))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

