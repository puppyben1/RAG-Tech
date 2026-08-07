from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DOCUMENT_METADATA_PATH, KB_STATS_PATH, MANIFEST_ENRICHED_PATH, MANIFEST_PATH, RAW_DATA_DIR, TEXT_UNITS_PATH
from .eval_excel import evaluate_excel
from .eval_text import evaluate_text
from .excel_parser import parse_xlsx
from .knowledge_base import kb_available, load_table_rows, load_text_chunks
from .manifest import build_manifest
from .path_refs import resolve_project_ref, to_project_ref
from .reranker import rerank_evidence
from .text_parser import extract_text, split_sentences
from .text_qa import ngram_coverage
from .retrieval import bm25_rank
from .utils import norm_text, read_jsonl
from .vector_index import TABLE_VECTOR_INDEX_PATH, TEXT_VECTOR_INDEX_PATH, load_vector_entries, vector_index_available, vector_rank


@lru_cache(maxsize=2)
def get_manifest() -> list[dict[str, Any]]:
    manifest_path = MANIFEST_ENRICHED_PATH if MANIFEST_ENRICHED_PATH.exists() else MANIFEST_PATH
    if not manifest_path.exists():
        build_manifest()
        manifest_path = MANIFEST_PATH
    return read_jsonl(manifest_path)


@lru_cache(maxsize=2)
def get_document_metadata() -> dict[str, dict[str, Any]]:
    if not DOCUMENT_METADATA_PATH.exists():
        return {}
    return {row["doc_id"]: row for row in read_jsonl(DOCUMENT_METADATA_PATH)}


@lru_cache(maxsize=2)
def load_text_units() -> list[dict[str, Any]]:
    return read_jsonl(TEXT_UNITS_PATH) if TEXT_UNITS_PATH.exists() else []


def list_documents(
    source_type: str | None = None,
    file_ext: str | None = None,
    query: str | None = None,
    publisher: str | None = None,
    publish_date_from: str | None = None,
    publish_date_to: str | None = None,
    business_domain: str | None = None,
    regulatory_topic: str | None = None,
    doc_no: str | None = None,
    column: str | None = None,
    source_site: str | None = None,
    version_status: str | None = None,
    effective_date_from: str | None = None,
    effective_date_to: str | None = None,
    version_group: str | None = None,
    has_version_relation: bool | None = None,
    has_source_url: bool | None = None,
    article_no: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    rows = get_manifest()
    metadata = get_document_metadata()
    rows = [_merge_document_metadata(row, metadata) for row in rows]
    if source_type:
        rows = [row for row in rows if row.get("source_type") == source_type]
    if file_ext:
        ext = file_ext if file_ext.startswith(".") else f".{file_ext}"
        rows = [row for row in rows if row.get("file_ext") == ext]
    if query:
        q = norm_text(query)
        rows = [row for row in rows if q in norm_text(row.get("title", "")) or q in norm_text(row.get("file_name", ""))]
    rows = _filter_document_rows(
        rows,
        publisher=publisher,
        publish_date_from=publish_date_from,
        publish_date_to=publish_date_to,
        business_domain=business_domain,
        regulatory_topic=regulatory_topic,
        doc_no=doc_no,
        column=column,
        source_site=source_site,
        version_status=version_status,
        effective_date_from=effective_date_from,
        effective_date_to=effective_date_to,
        version_group=version_group,
        has_version_relation=has_version_relation,
        has_source_url=has_source_url,
        article_no=article_no,
    )
    total = len(rows)
    rows = rows[offset : offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "documents": rows}


def get_document(doc_id: str) -> dict[str, Any] | None:
    metadata = get_document_metadata()
    for row in get_manifest():
        if row.get("doc_id") == doc_id:
            return _merge_document_metadata(row, metadata)
    return None


def search_evidence(
    query: str,
    source_type: str | None = None,
    doc_id: str | None = None,
    publisher: str | None = None,
    publish_date_from: str | None = None,
    publish_date_to: str | None = None,
    business_domain: str | None = None,
    regulatory_topic: str | None = None,
    doc_no: str | None = None,
    column: str | None = None,
    source_site: str | None = None,
    version_status: str | None = None,
    effective_date_from: str | None = None,
    effective_date_to: str | None = None,
    version_group: str | None = None,
    has_version_relation: bool | None = None,
    indicator: str | None = None,
    period: str | None = None,
    has_source_url: bool | None = None,
    article_no: str | None = None,
    retrieval: str = "bm25",
    rerank: bool = False,
    prefer_current: bool = True,
    include_superseded: bool = True,
    top_k: int = 5,
) -> dict[str, Any]:
    if kb_available():
        return search_evidence_kb(
            query=query,
            source_type=source_type,
            doc_id=doc_id,
            publisher=publisher,
            publish_date_from=publish_date_from,
            publish_date_to=publish_date_to,
            business_domain=business_domain,
            regulatory_topic=regulatory_topic,
            doc_no=doc_no,
            column=column,
            source_site=source_site,
            version_status=version_status,
            effective_date_from=effective_date_from,
            effective_date_to=effective_date_to,
            version_group=version_group,
            has_version_relation=has_version_relation,
            indicator=indicator,
            period=period,
            has_source_url=has_source_url,
            article_no=article_no,
            retrieval=retrieval,
            rerank=rerank,
            prefer_current=prefer_current,
            include_superseded=include_superseded,
            top_k=top_k,
        )
    records = get_manifest()
    metadata = get_document_metadata()
    records = [_merge_document_metadata(row, metadata) for row in records]
    if source_type:
        records = [r for r in records if r.get("source_type") == source_type]
    if doc_id:
        records = [r for r in records if r.get("doc_id") == doc_id]
    records = _filter_document_rows(
        records,
        publisher=publisher,
        publish_date_from=publish_date_from,
        publish_date_to=publish_date_to,
        business_domain=business_domain,
        regulatory_topic=regulatory_topic,
        doc_no=doc_no,
        column=column,
        source_site=source_site,
        version_status=version_status,
        effective_date_from=effective_date_from,
        effective_date_to=effective_date_to,
        version_group=version_group,
        has_version_relation=has_version_relation,
        has_source_url=has_source_url,
        article_no=article_no,
    )
    if not doc_id:
        records = _prefilter_records(query, records, limit=12)

    results: list[dict[str, Any]] = []
    for record in records:
        path = resolve_project_ref(record["local_path"])
        if not path.exists():
            continue
        if record.get("source_type") == "excel" and path.suffix.lower() == ".xlsx":
            results.extend(_search_excel_record(query, record, path))
        elif record.get("source_type") in {"word", "pdf"}:
            results.extend(_search_text_record(query, record, path))

    results.sort(key=lambda x: x["score"], reverse=True)
    results = _apply_version_policy(results, prefer_current=prefer_current, include_superseded=include_superseded)
    return {"query": query, "total": len(results), "top_k": top_k, "results": results[:top_k]}


def search_evidence_kb(
    query: str,
    source_type: str | None = None,
    doc_id: str | None = None,
    publisher: str | None = None,
    publish_date_from: str | None = None,
    publish_date_to: str | None = None,
    business_domain: str | None = None,
    regulatory_topic: str | None = None,
    doc_no: str | None = None,
    column: str | None = None,
    source_site: str | None = None,
    version_status: str | None = None,
    effective_date_from: str | None = None,
    effective_date_to: str | None = None,
    version_group: str | None = None,
    has_version_relation: bool | None = None,
    indicator: str | None = None,
    period: str | None = None,
    has_source_url: bool | None = None,
    article_no: str | None = None,
    retrieval: str = "bm25",
    rerank: bool = False,
    prefer_current: bool = True,
    include_superseded: bool = True,
    top_k: int = 5,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    allowed_docs = _allowed_doc_ids(
        source_type=source_type,
        doc_id=doc_id,
        publisher=publisher,
        publish_date_from=publish_date_from,
        publish_date_to=publish_date_to,
        business_domain=business_domain,
        regulatory_topic=regulatory_topic,
        doc_no=doc_no,
        column=column,
        source_site=source_site,
        version_status=version_status,
        effective_date_from=effective_date_from,
        effective_date_to=effective_date_to,
        version_group=version_group,
        has_version_relation=has_version_relation,
        has_source_url=has_source_url,
        article_no=article_no,
    )
    metadata = get_document_metadata()
    if source_type in {None, "word", "pdf"}:
        text_rows = load_text_units() or load_text_chunks()
        chunks = [
            chunk
            for chunk in text_rows
            if (not source_type or chunk.get("source_type") == source_type)
            and (not doc_id or chunk.get("doc_id") == doc_id)
            and (allowed_docs is None or chunk.get("doc_id") in allowed_docs)
            and (not article_no or _text_contains(chunk.get("article_no"), article_no))
        ]
        text_ranked = bm25_rank(query, chunks, text_fields=("source_title", "section_path", "article_no", "text"), top_k=max(top_k * 4, 20))
        if retrieval == "hybrid":
            text_ranked = _hybrid_rank_text(query, chunks, text_ranked, top_k=max(top_k * 4, 20))
        for score, chunk in text_ranked:
            doc_meta = metadata.get(chunk["doc_id"], {})
            results.append(
                {
                    "doc_id": chunk["doc_id"],
                    "source_type": chunk["source_type"],
                    "source_title": chunk["source_title"],
                    "source": chunk["local_path"],
                    "position": _text_position(chunk),
                    "score": round(score, 4),
                    "text": chunk["text"],
                    **_evidence_metadata(doc_meta),
                    "evidence_type": "text_unit" if chunk.get("unit_id") else "text_chunk",
                    "index": retrieval if retrieval == "hybrid" else "bm25",
                }
            )
    if source_type in {None, "excel"}:
        table_rows = [
            row
            for row in load_table_rows()
            if (not doc_id or row.get("doc_id") == doc_id)
            and (allowed_docs is None or row.get("doc_id") in allowed_docs)
            and not article_no
            and (not indicator or _text_contains(row.get("indicator") or row.get("row_header"), indicator))
            and (not period or _list_text_contains(row.get("periods"), period) or _text_contains(row.get("period"), period))
        ]
        table_ranked = bm25_rank(query, table_rows, text_fields=("source_title", "text"), top_k=max(top_k * 4, 20))
        if retrieval == "hybrid":
            table_ranked = _hybrid_rank_table(query, table_rows, table_ranked, top_k=max(top_k * 4, 20))
        for score, row in table_ranked:
            doc_meta = metadata.get(row["doc_id"], {})
            results.append(
                {
                    "doc_id": row["doc_id"],
                    "source_type": "excel",
                    "source_title": row["source_title"],
                    "source": row["local_path"],
                    "position": {
                        "sheet_name": row["sheet_name"],
                        "row_index": row["row_index"],
                        "row_header": row["row_header"],
                        "cell_refs": row.get("cell_refs", []),
                        "indicator": row.get("indicator") or row.get("row_header"),
                        "periods": row.get("periods", []),
                        "headers": row.get("headers", []),
                    },
                    "score": round(score, 4),
                    "text": row["text"],
                    "semantic_text": row.get("semantic_text"),
                    "unit": row.get("unit"),
                    "values": row.get("values", []),
                    "indicator": row.get("indicator") or row.get("row_header"),
                    "periods": row.get("periods", []),
                    "headers": row.get("headers", []),
                    "cells": row.get("cells", []),
                    **_evidence_metadata(doc_meta),
                    "evidence_type": "table_row",
                    "index": retrieval if retrieval == "hybrid" else "bm25",
                }
            )

    if not results:
        results = _fallback_search_evidence_kb(
            query=query,
            source_type=source_type,
            doc_id=doc_id,
            allowed_docs=allowed_docs,
            article_no=article_no,
            top_k=top_k,
        )
    results.sort(key=lambda x: x["score"], reverse=True)
    if rerank:
        results = rerank_evidence(query, results, top_k=max(top_k * 4, 20))
    results = _apply_version_policy(results, prefer_current=prefer_current, include_superseded=include_superseded)
    index_name = "hybrid_bm25_hash_embedding" if retrieval == "hybrid" and vector_index_available() else "bm25_processed_jsonl"
    if rerank:
        index_name = f"{index_name}+rule_reranker_v1"
    return {
        "query": query,
        "total": len(results),
        "top_k": top_k,
        "index": index_name,
        "rerank": rerank,
        "version_policy": {
            "prefer_current": prefer_current,
            "include_superseded": include_superseded,
            "method": "current_boost_superseded_penalty_v1",
        },
        "results": results[:top_k],
    }


def _fallback_search_evidence_kb(
    query: str,
    source_type: str | None = None,
    doc_id: str | None = None,
    allowed_docs: set[str] | None = None,
    article_no: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    q = norm_text(query)
    results: list[dict[str, Any]] = []
    metadata = get_document_metadata()
    if source_type in {None, "word", "pdf"}:
        for chunk in load_text_units() or load_text_chunks():
            if source_type and chunk.get("source_type") != source_type:
                continue
            if doc_id and chunk.get("doc_id") != doc_id:
                continue
            if allowed_docs is not None and chunk.get("doc_id") not in allowed_docs:
                continue
            if article_no and not _text_contains(chunk.get("article_no"), article_no):
                continue
            score = _score_norm_query(q, chunk.get("norm_text", ""))
            if score > 0.25:
                results.append(
                    {
                        "doc_id": chunk["doc_id"],
                        "source_type": chunk["source_type"],
                        "source_title": chunk["source_title"],
                        "source": chunk["local_path"],
                        "position": {"chunk_id": chunk["chunk_id"], "chunk_index": chunk["chunk_index"]},
                        "score": round(score, 4),
                        "text": chunk["text"],
                        **_evidence_metadata(metadata.get(chunk["doc_id"], {})),
                        "evidence_type": "text_unit" if chunk.get("unit_id") else "text_chunk",
                        "index": "coverage_fallback",
                    }
                )
    if source_type in {None, "excel"}:
        for row in load_table_rows():
            if doc_id and row.get("doc_id") != doc_id:
                continue
            if allowed_docs is not None and row.get("doc_id") not in allowed_docs:
                continue
            if article_no:
                continue
            score = _score_norm_query(q, row.get("norm_text", ""))
            if score > 0.25:
                results.append(
                    {
                        "doc_id": row["doc_id"],
                        "source_type": "excel",
                        "source_title": row["source_title"],
                        "source": row["local_path"],
                        "position": {
                            "sheet_name": row["sheet_name"],
                            "row_index": row["row_index"],
                            "row_header": row["row_header"],
                            "cell_refs": row.get("cell_refs", []),
                            "indicator": row.get("indicator") or row.get("row_header"),
                            "periods": row.get("periods", []),
                            "headers": row.get("headers", []),
                        },
                        "score": round(score, 4),
                        "text": row["text"],
                        "semantic_text": row.get("semantic_text"),
                        "unit": row.get("unit"),
                        "values": row.get("values", []),
                        "indicator": row.get("indicator") or row.get("row_header"),
                        "periods": row.get("periods", []),
                        "headers": row.get("headers", []),
                        "cells": row.get("cells", []),
                        **_evidence_metadata(metadata.get(row["doc_id"], {})),
                        "evidence_type": "table_row",
                        "index": "coverage_fallback",
                    }
                )
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _hybrid_rank_text(
    query: str,
    rows: list[dict[str, Any]],
    bm25_ranked: list[tuple[float, dict[str, Any]]],
    top_k: int,
) -> list[tuple[float, dict[str, Any]]]:
    if not vector_index_available():
        return bm25_ranked
    row_by_id = {_text_row_id(row): row for row in rows}
    allowed_ids = set(row_by_id)
    vector_entries = [entry for entry in load_vector_entries(TEXT_VECTOR_INDEX_PATH) if entry.get("id") in allowed_ids]
    vector_ranked = [(score, row_by_id[entry["id"]]) for score, entry in vector_rank(query, vector_entries, top_k=top_k)]
    return _rrf_merge(bm25_ranked, vector_ranked, _text_row_id, top_k)


def _hybrid_rank_table(
    query: str,
    rows: list[dict[str, Any]],
    bm25_ranked: list[tuple[float, dict[str, Any]]],
    top_k: int,
) -> list[tuple[float, dict[str, Any]]]:
    if not vector_index_available():
        return bm25_ranked
    row_by_id = {str(row.get("row_id")): row for row in rows}
    allowed_ids = set(row_by_id)
    vector_entries = [entry for entry in load_vector_entries(TABLE_VECTOR_INDEX_PATH) if entry.get("id") in allowed_ids]
    vector_ranked = [(score, row_by_id[entry["id"]]) for score, entry in vector_rank(query, vector_entries, top_k=top_k)]
    return _rrf_merge(bm25_ranked, vector_ranked, lambda row: str(row.get("row_id")), top_k)


def _rrf_merge(
    bm25_ranked: list[tuple[float, dict[str, Any]]],
    vector_ranked: list[tuple[float, dict[str, Any]]],
    key_fn: Any,
    top_k: int,
) -> list[tuple[float, dict[str, Any]]]:
    merged: dict[str, dict[str, Any]] = {}
    k = 60.0
    for rank, (score, row) in enumerate(bm25_ranked, start=1):
        key = key_fn(row)
        bucket = merged.setdefault(key, {"row": row, "score": 0.0, "bm25": 0.0, "vector": 0.0})
        bucket["score"] += 1.0 / (k + rank)
        bucket["bm25"] = float(score)
    for rank, (score, row) in enumerate(vector_ranked, start=1):
        key = key_fn(row)
        bucket = merged.setdefault(key, {"row": row, "score": 0.0, "bm25": 0.0, "vector": 0.0})
        bucket["score"] += 1.0 / (k + rank)
        bucket["vector"] = float(score)
    ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    return [(float(item["score"]), item["row"]) for item in ranked[:top_k]]


def _text_row_id(row: dict[str, Any]) -> str:
    return str(row.get("unit_id") or row.get("chunk_id"))


def _merge_document_metadata(row: dict[str, Any], metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    extra = metadata.get(row.get("doc_id"), {})
    if not extra:
        return row
    merged = dict(row)
    for key in (
        "publisher",
        "publish_date",
        "doc_no",
        "business_domain",
        "regulatory_topic",
        "source_url",
        "attachment_url",
        "column",
        "source_site",
        "version_status",
        "effective_date",
        "expiry_date",
        "supersedes_doc_id",
        "superseded_by_doc_id",
        "version_group",
    ):
        if extra.get(key) is not None:
            merged[key] = extra[key]
    return merged


def _allowed_doc_ids(
    source_type: str | None = None,
    doc_id: str | None = None,
    publisher: str | None = None,
    publish_date_from: str | None = None,
    publish_date_to: str | None = None,
    business_domain: str | None = None,
    regulatory_topic: str | None = None,
    doc_no: str | None = None,
    column: str | None = None,
    source_site: str | None = None,
    version_status: str | None = None,
    effective_date_from: str | None = None,
    effective_date_to: str | None = None,
    version_group: str | None = None,
    has_version_relation: bool | None = None,
    has_source_url: bool | None = None,
    article_no: str | None = None,
) -> set[str] | None:
    if not any(
        [
            publisher,
            publish_date_from,
            publish_date_to,
            business_domain,
            regulatory_topic,
            doc_no,
            column,
            source_site,
            version_status,
            effective_date_from,
            effective_date_to,
            version_group,
            has_version_relation is not None,
            has_source_url is not None,
            article_no,
        ]
    ):
        return {doc_id} if doc_id else None
    rows = get_manifest()
    metadata = get_document_metadata()
    rows = [_merge_document_metadata(row, metadata) for row in rows]
    if source_type:
        rows = [row for row in rows if row.get("source_type") == source_type]
    if doc_id:
        rows = [row for row in rows if row.get("doc_id") == doc_id]
    rows = _filter_document_rows(
        rows,
        publisher=publisher,
        publish_date_from=publish_date_from,
        publish_date_to=publish_date_to,
        business_domain=business_domain,
        regulatory_topic=regulatory_topic,
        doc_no=doc_no,
        column=column,
        source_site=source_site,
        version_status=version_status,
        effective_date_from=effective_date_from,
        effective_date_to=effective_date_to,
        version_group=version_group,
        has_version_relation=has_version_relation,
        has_source_url=has_source_url,
        article_no=article_no,
    )
    return {row["doc_id"] for row in rows}


def _filter_document_rows(
    rows: list[dict[str, Any]],
    publisher: str | None = None,
    publish_date_from: str | None = None,
    publish_date_to: str | None = None,
    business_domain: str | None = None,
    regulatory_topic: str | None = None,
    doc_no: str | None = None,
    column: str | None = None,
    source_site: str | None = None,
    version_status: str | None = None,
    effective_date_from: str | None = None,
    effective_date_to: str | None = None,
    version_group: str | None = None,
    has_version_relation: bool | None = None,
    has_source_url: bool | None = None,
    article_no: str | None = None,
) -> list[dict[str, Any]]:
    filtered = rows
    if publisher:
        filtered = [row for row in filtered if _text_contains(row.get("publisher"), publisher)]
    if business_domain:
        filtered = [row for row in filtered if _text_contains(row.get("business_domain"), business_domain)]
    if regulatory_topic:
        filtered = [row for row in filtered if _text_contains(row.get("regulatory_topic"), regulatory_topic)]
    if doc_no:
        filtered = [row for row in filtered if _text_contains(row.get("doc_no"), doc_no)]
    if column:
        filtered = [row for row in filtered if _text_contains(row.get("column"), column)]
    if source_site:
        filtered = [row for row in filtered if _text_contains(row.get("source_site"), source_site)]
    if version_status:
        filtered = [row for row in filtered if _text_contains(row.get("version_status") or "unknown", version_status)]
    if version_group:
        filtered = [row for row in filtered if _text_contains(row.get("version_group"), version_group)]
    if publish_date_from:
        filtered = [row for row in filtered if _date_value(row.get("publish_date")) >= publish_date_from]
    if publish_date_to:
        filtered = [row for row in filtered if _date_value(row.get("publish_date")) <= publish_date_to]
    if effective_date_from:
        filtered = [row for row in filtered if _date_value(row.get("effective_date")) >= effective_date_from]
    if effective_date_to:
        filtered = [row for row in filtered if _date_value(row.get("effective_date")) <= effective_date_to]
    if has_version_relation is not None:
        filtered = [
            row
            for row in filtered
            if bool(row.get("supersedes_doc_id") or row.get("superseded_by_doc_id")) is has_version_relation
        ]
    if has_source_url is not None:
        filtered = [row for row in filtered if bool(row.get("source_url")) is has_source_url]
    if article_no:
        doc_ids = {
            row.get("doc_id")
            for row in load_text_units()
            if row.get("doc_id") and _text_contains(row.get("article_no"), article_no)
        }
        filtered = [row for row in filtered if row.get("doc_id") in doc_ids]
    return filtered


def _text_contains(value: Any, query: str | None) -> bool:
    if not query:
        return True
    return norm_text(query) in norm_text(value)


def _list_text_contains(value: Any, query: str | None) -> bool:
    if not query:
        return True
    if isinstance(value, list):
        return any(_text_contains(item, query) for item in value)
    return _text_contains(value, query)


def _date_value(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "0000-00-00"


def _evidence_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metadata.get(key)
        for key in (
            "publisher",
            "publish_date",
            "doc_no",
            "business_domain",
            "regulatory_topic",
            "source_url",
            "attachment_url",
            "column",
            "source_site",
            "version_status",
            "effective_date",
            "expiry_date",
            "supersedes_doc_id",
            "superseded_by_doc_id",
            "version_group",
        )
        if metadata.get(key) is not None
    }


def _apply_version_policy(
    results: list[dict[str, Any]],
    prefer_current: bool = True,
    include_superseded: bool = True,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for result in results:
        status = str(result.get("version_status") or "unknown").strip().lower() or "unknown"
        if status == "superseded" and not include_superseded:
            continue
        item = dict(result)
        base_score = float(item.get("score") or 0.0)
        adjustment = 0.0
        if prefer_current:
            if status == "current":
                adjustment += 0.3
            elif status == "superseded":
                adjustment -= 0.6
        item["score"] = round(max(base_score + adjustment, 0.0), 4)
        item["version_policy"] = {
            "version_status": status,
            "prefer_current": prefer_current,
            "include_superseded": include_superseded,
            "score_adjustment": round(adjustment, 4),
        }
        ranked.append(item)
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked


def _text_position(chunk: dict[str, Any]) -> dict[str, Any]:
    if chunk.get("unit_id"):
        return {
            "unit_id": chunk.get("unit_id"),
            "unit_index": chunk.get("unit_index"),
            "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk.get("chunk_index"),
            "page_no": chunk.get("page_no"),
            "section_path": chunk.get("section_path"),
            "article_no": chunk.get("article_no"),
        }
    return {"chunk_id": chunk["chunk_id"], "chunk_index": chunk["chunk_index"]}


def _score_norm_query(query_norm: str, text_norm: str) -> float:
    if not query_norm or not text_norm:
        return 0.0
    score = ngram_coverage(query_norm, text_norm)
    if query_norm in text_norm:
        score += 1.0
    token_hits = 0
    for token in _query_tokens(query_norm):
        if token in text_norm:
            token_hits += 1
    if token_hits:
        score += min(token_hits * 0.15, 0.6)
    return score


def _query_tokens(query_norm: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for ch in query_norm:
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            current += ch
        else:
            if current:
                tokens.append(current)
            current = ""
    if current:
        tokens.append(current)
    if len(tokens) == 1 and len(tokens[0]) > 4:
        text = tokens[0]
        tokens.extend(text[i : i + 4] for i in range(0, len(text) - 3, 4))
    return tokens


def _prefilter_records(query: str, records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    q = norm_text(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for record in records:
        hay = norm_text(f"{record.get('title', '')}{record.get('file_name', '')}{record.get('period', '')}")
        score = ngram_coverage(q, hay)
        if q and q in hay:
            score += 2.0
        scored.append((score, record))
    scored.sort(key=lambda x: x[0], reverse=True)
    positive = [record for score, record in scored if score > 0]
    return positive[:limit] if positive else [record for _, record in scored[:limit]]


def _search_text_record(query: str, record: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    try:
        text = extract_text(str(path.resolve()))
    except Exception as exc:
        return [{"doc_id": record["doc_id"], "source": record["local_path"], "score": 0, "error": str(exc)}]
    q = norm_text(query)
    rows: list[dict[str, Any]] = []
    for idx, sent in enumerate(split_sentences(text)):
        sent_norm = norm_text(sent)
        score = ngram_coverage(q, sent_norm)
        if q in sent_norm:
            score += 1.0
        if score > 0.35:
            rows.append(
                {
                    "doc_id": record["doc_id"],
                    "source_type": record["source_type"],
                    "source_title": record["title"],
                    "source": record["local_path"],
                    "position": {"sentence_index": idx},
                    "score": round(score, 4),
                    "text": sent[:1000],
                }
            )
    return rows


def _search_excel_record(query: str, record: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    q = norm_text(query)
    rows: list[dict[str, Any]] = []
    try:
        facts = parse_xlsx(str(path.resolve()))
    except Exception as exc:
        return [{"doc_id": record["doc_id"], "source": record["local_path"], "score": 0, "error": str(exc)}]
    for fact in facts:
        hay = norm_text(f"{record['title']}{fact.sheet_name}{fact.row_header}{fact.col_header}{fact.value_raw}")
        score = 0.0
        if q and q in hay:
            score += 1.0
        score += ngram_coverage(q, hay)
        if score > 0.35:
            rows.append(
                {
                    "doc_id": record["doc_id"],
                    "source_type": "excel",
                    "source_title": record["title"],
                    "source": record["local_path"],
                    "position": {
                        "sheet_name": fact.sheet_name,
                        "cell_ref": fact.cell_ref,
                        "row_header": fact.row_header,
                        "col_header": fact.col_header,
                    },
                    "score": round(score, 4),
                    "text": f"{fact.row_header} / {fact.col_header} = {fact.value_raw}",
                    "value_raw": fact.value_raw,
                    "unit": fact.unit,
                }
            )
    return rows


def run_eval(scope: str = "all") -> dict[str, Any]:
    if scope == "excel":
        return {"scope": scope, **evaluate_excel()["summary"]}
    if scope == "text":
        return {"scope": scope, **evaluate_text()["summary"]}
    if scope != "all":
        raise ValueError("scope must be one of: all, excel, text")
    excel = evaluate_excel()
    text = evaluate_text()
    total = excel["summary"]["total"] + text["summary"]["total"]
    correct = excel["summary"]["correct"] + text["summary"]["correct"]
    return {
        "scope": "all",
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0,
        "excel": excel["summary"],
        "text": text["summary"],
    }


def kb_status() -> dict[str, Any]:
    if KB_STATS_PATH.exists():
        payload = {"available": True, **__import__("json").loads(KB_STATS_PATH.read_text(encoding="utf-8"))}
        if DOCUMENT_METADATA_PATH.exists():
            payload["document_metadata"] = _count_jsonl(DOCUMENT_METADATA_PATH)
            payload["document_metadata_path"] = to_project_ref(DOCUMENT_METADATA_PATH)
        if TEXT_UNITS_PATH.exists():
            payload["text_units"] = _count_jsonl(TEXT_UNITS_PATH)
            payload["text_units_path"] = to_project_ref(TEXT_UNITS_PATH)
        if vector_index_available():
            payload["vector_index"] = True
            if TEXT_VECTOR_INDEX_PATH.exists():
                payload["text_vectors"] = _count_jsonl(TEXT_VECTOR_INDEX_PATH)
                payload["text_vector_index_path"] = to_project_ref(TEXT_VECTOR_INDEX_PATH)
            if TABLE_VECTOR_INDEX_PATH.exists():
                payload["table_row_vectors"] = _count_jsonl(TABLE_VECTOR_INDEX_PATH)
                payload["table_vector_index_path"] = to_project_ref(TABLE_VECTOR_INDEX_PATH)
        return payload
    return {"available": False, "message": "run `python -m jinrong.cli build-kb --qa-only` first"}


def _count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def openapi_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Jinrong Trusted RAG API", "version": "0.1.0"},
        "paths": {
            "/health": {"get": {"summary": "Health check"}},
            "/ask": {"post": {"summary": "Ask a question or replay a QA id"}},
            "/search": {"post": {"summary": "Search source-backed evidence"}},
            "/documents": {"get": {"summary": "List indexed documents"}},
            "/documents/{doc_id}": {"get": {"summary": "Get one document metadata record"}},
            "/kb/status": {"get": {"summary": "Get processed RAG knowledge base status"}},
            "/eval": {"post": {"summary": "Run QA evaluation"}},
            "/eval/acceptance": {"get": {"summary": "Get final holdout acceptance report"}},
            "/eval/trusted/summary": {"get": {"summary": "Get trusted QA evaluation summary report"}},
            "/eval/trusted/{case_type}": {"get": {"summary": "Get one trusted QA evaluation type report"}},
        },
    }
