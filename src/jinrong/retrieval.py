from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Iterable

from .utils import norm_text


def tokenize(value: Any) -> list[str]:
    text = norm_text(value).lower()
    if not text:
        return []
    tokens: list[str] = []
    tokens.extend(re.findall(r"[a-z0-9]+", text))
    cjk = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    if cjk:
        tokens.extend(cjk[i : i + 2] for i in range(max(len(cjk) - 1, 0)))
        tokens.extend(cjk[i : i + 3] for i in range(max(len(cjk) - 2, 0)))
        if len(cjk) <= 8:
            tokens.append(cjk)
    return [token for token in tokens if token]


def bm25_rank(
    query: str,
    rows: Iterable[dict[str, Any]],
    text_fields: tuple[str, ...] = ("text",),
    top_k: int = 20,
) -> list[tuple[float, dict[str, Any]]]:
    materialized = list(rows)
    if not materialized:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    docs: list[Counter[str]] = []
    lengths: list[int] = []
    doc_freq: Counter[str] = Counter()
    for row in materialized:
        text = " ".join(str(row.get(field, "")) for field in text_fields)
        counts = Counter(tokenize(text))
        docs.append(counts)
        length = sum(counts.values())
        lengths.append(length)
        for token in counts:
            doc_freq[token] += 1

    avg_len = sum(lengths) / len(lengths) if lengths else 1.0
    avg_len = avg_len or 1.0
    n_docs = len(materialized)
    k1 = 1.5
    b = 0.75
    query_counts = Counter(query_tokens)
    ranked: list[tuple[float, dict[str, Any]]] = []

    for row, counts, length in zip(materialized, docs, lengths):
        if not counts:
            continue
        score = 0.0
        for token, qf in query_counts.items():
            tf = counts.get(token, 0)
            if not tf:
                continue
            df = doc_freq[token]
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * length / avg_len)
            score += idf * (tf * (k1 + 1) / denom) * min(qf, 3)
        score += _exact_boost(query, row, text_fields)
        if score > 0:
            ranked.append((score, row))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[:top_k]


def _exact_boost(query: str, row: dict[str, Any], text_fields: tuple[str, ...]) -> float:
    q = norm_text(query).lower()
    if not q:
        return 0.0
    text = norm_text(" ".join(str(row.get(field, "")) for field in text_fields)).lower()
    boost = 0.0
    if q in text:
        boost += 3.0
    for piece in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9.%-]+", str(query)):
        if norm_text(piece).lower() in text:
            boost += 0.25
    return boost
