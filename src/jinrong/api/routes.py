from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from ..ask import ask
from ..eval_acceptance import load_acceptance_report
from ..eval_trusted import load_trusted_report
from ..services import get_document, kb_status, list_documents, run_eval, search_evidence
from .schemas import AskRequest, EvalRequest, JsonDict, SearchRequest


router = APIRouter()


@router.get("/health")
def health() -> JsonDict:
    return {"status": "ok"}


@router.post("/ask")
def ask_route(payload: AskRequest) -> JsonDict:
    response = ask(question=payload.question, options=payload.options, qa_id=payload.qa_id)
    return json.loads(response.to_json())


@router.post("/search")
def search_route(payload: SearchRequest) -> JsonDict:
    return search_evidence(
        query=payload.query,
        source_type=payload.source_type,
        doc_id=payload.doc_id,
        publisher=payload.publisher,
        publish_date_from=payload.publish_date_from,
        publish_date_to=payload.publish_date_to,
        business_domain=payload.business_domain,
        regulatory_topic=payload.regulatory_topic,
        doc_no=payload.doc_no,
        column=payload.column,
        source_site=payload.source_site,
        version_status=payload.version_status,
        effective_date_from=payload.effective_date_from,
        effective_date_to=payload.effective_date_to,
        version_group=payload.version_group,
        has_version_relation=payload.has_version_relation,
        indicator=payload.indicator,
        period=payload.period,
        has_source_url=payload.has_source_url,
        article_no=payload.article_no,
        retrieval=payload.retrieval,
        rerank=payload.rerank,
        prefer_current=payload.prefer_current,
        include_superseded=payload.include_superseded,
        top_k=payload.top_k,
    )


@router.get("/documents")
def documents_route(
    source_type: str | None = Query(default=None),
    file_ext: str | None = Query(default=None),
    query: str | None = Query(default=None),
    publisher: str | None = Query(default=None),
    publish_date_from: str | None = Query(default=None),
    publish_date_to: str | None = Query(default=None),
    business_domain: str | None = Query(default=None),
    regulatory_topic: str | None = Query(default=None),
    doc_no: str | None = Query(default=None),
    column: str | None = Query(default=None),
    source_site: str | None = Query(default=None),
    version_status: str | None = Query(default=None),
    effective_date_from: str | None = Query(default=None),
    effective_date_to: str | None = Query(default=None),
    version_group: str | None = Query(default=None),
    has_version_relation: bool | None = Query(default=None),
    has_source_url: bool | None = Query(default=None),
    article_no: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> JsonDict:
    return list_documents(
        source_type=source_type,
        file_ext=file_ext,
        query=query,
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
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{doc_id}")
def document_route(doc_id: str) -> JsonDict:
    document = get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.get("/kb/status")
def kb_status_route() -> JsonDict:
    return kb_status()


@router.post("/eval")
def eval_route(payload: EvalRequest) -> JsonDict:
    return run_eval(scope=payload.scope)


@router.get("/eval/trusted/summary")
def trusted_eval_summary_route() -> JsonDict:
    return load_trusted_report("summary")


@router.get("/eval/acceptance")
def acceptance_report_route() -> JsonDict:
    return load_acceptance_report()


@router.get("/eval/trusted/{case_type}")
def trusted_eval_report_route(case_type: str) -> JsonDict:
    return load_trusted_report(case_type)
