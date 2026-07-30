from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .config import (
    TABLE_ROWS_PATH,
    TABLE_VECTOR_INDEX_PATH,
    TEXT_CHUNKS_PATH,
    TEXT_UNITS_PATH,
    TEXT_VECTOR_INDEX_PATH,
    VECTOR_INDEX_MANIFEST_PATH,
)
from .knowledge_base import load_table_rows, load_text_chunks
from .retrieval import tokenize
from .utils import ensure_dir, read_jsonl, write_jsonl


VECTOR_DIMENSIONS = 4096


def build_vector_index(
    text_output_path: Path = TEXT_VECTOR_INDEX_PATH,
    table_output_path: Path = TABLE_VECTOR_INDEX_PATH,
    manifest_path: Path = VECTOR_INDEX_MANIFEST_PATH,
) -> dict[str, Any]:
    text_rows = read_jsonl(TEXT_UNITS_PATH) if TEXT_UNITS_PATH.exists() else load_text_chunks(TEXT_CHUNKS_PATH)
    table_rows = load_table_rows(TABLE_ROWS_PATH)

    text_index = [_vector_entry("text", row, ("source_title", "section_path", "article_no", "text")) for row in text_rows]
    table_index = [_vector_entry("table_row", row, ("source_title", "text")) for row in table_rows]

    write_jsonl(text_output_path, text_index)
    write_jsonl(table_output_path, table_index)

    payload = {
        "embedding_type": "local_hashing_v1",
        "dimensions": VECTOR_DIMENSIONS,
        "text_source": str(TEXT_UNITS_PATH if TEXT_UNITS_PATH.exists() else TEXT_CHUNKS_PATH),
        "table_source": str(TABLE_ROWS_PATH),
        "text_vectors": len(text_index),
        "table_row_vectors": len(table_index),
        "text_index_path": str(text_output_path),
        "table_index_path": str(table_output_path),
    }
    ensure_dir(manifest_path.parent)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def vector_index_available() -> bool:
    return TEXT_VECTOR_INDEX_PATH.exists() or TABLE_VECTOR_INDEX_PATH.exists()


@lru_cache(maxsize=8)
def load_vector_entries(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


def vector_rank(
    query: str,
    entries: Iterable[dict[str, Any]],
    top_k: int = 50,
) -> list[tuple[float, dict[str, Any]]]:
    query_vector = hashed_embedding(query)
    if not query_vector:
        return []
    ranked: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        score = cosine_sparse(query_vector, entry.get("vector", {}))
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[:top_k]


def hashed_embedding(value: Any, dimensions: int = VECTOR_DIMENSIONS) -> dict[str, float]:
    counts: Counter[int] = Counter()
    for token in tokenize(value):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % dimensions
        counts[index] += 1
    if not counts:
        return {}
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {str(index): round(count / norm, 6) for index, count in counts.items()}


def cosine_sparse(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    score = sum(value * float(right.get(key, 0.0)) for key, value in left.items())
    return float(score)


def _vector_entry(kind: str, row: dict[str, Any], text_fields: tuple[str, ...]) -> dict[str, Any]:
    text = " ".join(str(row.get(field, "")) for field in text_fields)
    return {
        "id": _row_id(kind, row),
        "kind": kind,
        "doc_id": row.get("doc_id"),
        "source_type": row.get("source_type") or ("excel" if kind == "table_row" else None),
        "vector": hashed_embedding(text),
    }


def _row_id(kind: str, row: dict[str, Any]) -> str:
    if kind == "table_row":
        return str(row.get("row_id"))
    return str(row.get("unit_id") or row.get("chunk_id"))
