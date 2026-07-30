from __future__ import annotations

import re
from typing import Any

from .retrieval import tokenize
from .utils import norm_text


def rerank_evidence(query: str, results: list[dict[str, Any]], top_k: int | None = None) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for rank, result in enumerate(results, start=1):
        item = dict(result)
        base_score = float(item.get("score") or 0.0)
        features = _features(query, item)
        rerank_score = (
            features["body_token_coverage"] * 5.0
            + features["token_coverage"] * 1.5
            + features["phrase_hits"] * 1.0
            + features["date_phrase_hits"] * 2.0
            + features["title_hits"] * 0.2
            + features["metadata_hits"] * 0.08
            + features["position_hits"] * 0.15
            + features["exact_query"] * 1.5
            + features["substantive_text"] * 0.35
            + 1.0 / (60.0 + rank)
        )
        item["base_score"] = round(base_score, 4)
        item["score"] = round(rerank_score, 4)
        item["rerank"] = {
            "method": "rule_reranker_v1",
            "base_rank": rank,
            **features,
        }
        ranked.append(item)
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked[:top_k] if top_k else ranked


def _features(query: str, result: dict[str, Any]) -> dict[str, Any]:
    query_tokens = _query_terms(query)
    evidence_text = _evidence_text(result)
    evidence_norm = norm_text(evidence_text).lower()
    body_norm = norm_text(" ".join([str(result.get("source_title", "")), str(result.get("text", "")), str(result.get("position", ""))])).lower()
    title_norm = norm_text(result.get("source_title")).lower()
    metadata_norm = norm_text(
        " ".join(
            str(result.get(key, ""))
            for key in ("publisher", "publish_date", "doc_no", "business_domain", "regulatory_topic", "column")
        )
    ).lower()
    position = result.get("position") or {}
    position_norm = norm_text(" ".join(str(value) for value in position.values())).lower() if isinstance(position, dict) else ""

    matched_tokens = [token for token in query_tokens if token in evidence_norm]
    body_matched_tokens = [token for token in query_tokens if token in body_norm]
    token_coverage = len(matched_tokens) / len(query_tokens) if query_tokens else 0.0
    body_token_coverage = len(body_matched_tokens) / len(query_tokens) if query_tokens else 0.0
    phrase_hits = sum(1 for phrase in _phrases(query) if phrase in evidence_norm)
    date_phrase_hits = sum(1 for phrase in _date_phrases(query) if phrase in body_norm)
    title_hits = sum(1 for token in query_tokens if token in title_norm)
    metadata_hits = sum(1 for token in query_tokens if token in metadata_norm)
    position_hits = sum(1 for token in query_tokens if token in position_norm)
    exact_query = 1.0 if norm_text(query).lower() in evidence_norm else 0.0
    return {
        "token_coverage": round(token_coverage, 4),
        "body_token_coverage": round(body_token_coverage, 4),
        "matched_tokens": matched_tokens[:20],
        "body_matched_tokens": body_matched_tokens[:20],
        "phrase_hits": phrase_hits,
        "date_phrase_hits": date_phrase_hits,
        "title_hits": title_hits,
        "metadata_hits": metadata_hits,
        "position_hits": position_hits,
        "exact_query": exact_query,
        "substantive_text": 1.0 if len(norm_text(result.get("text"))) >= 40 else 0.0,
    }


def _evidence_text(result: dict[str, Any]) -> str:
    position = result.get("position") or {}
    position_text = ""
    if isinstance(position, dict):
        position_text = " ".join(str(value) for value in position.values())
    fields = [
        result.get("source_title", ""),
        result.get("text", ""),
        result.get("publisher", ""),
        result.get("doc_no", ""),
        result.get("business_domain", ""),
        result.get("regulatory_topic", ""),
        result.get("column", ""),
        position_text,
    ]
    return " ".join(str(field) for field in fields if field is not None)


def _query_terms(query: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for token in tokenize(query):
        if len(token) < 2:
            continue
        if token not in seen:
            seen.add(token)
            terms.append(token)
    for phrase in _phrases(query):
        if phrase not in seen:
            seen.add(phrase)
            terms.append(phrase)
    return terms


def _phrases(query: str) -> list[str]:
    phrases = [norm_text(piece).lower() for piece in re.split(r"\s+", query) if piece.strip()]
    phrases.extend(norm_text(piece).lower() for piece in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9.%-]+", query))
    phrases.extend(_date_phrases(query))
    return [phrase for phrase in phrases if len(phrase) >= 2]


def _date_phrases(query: str) -> list[str]:
    return [norm_text(piece).lower() for piece in re.findall(r"\d{4}\s*年\s*\d{1,2}\s*月|\d{4}[-/]\d{1,2}", query)]
