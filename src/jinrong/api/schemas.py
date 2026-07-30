from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    qa_id: str | None = None
    question: str | None = None
    options: dict[str, str] | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    source_type: Literal["excel", "word", "pdf"] | None = None
    doc_id: str | None = None
    publisher: str | None = None
    publish_date_from: str | None = None
    publish_date_to: str | None = None
    business_domain: str | None = None
    regulatory_topic: str | None = None
    doc_no: str | None = None
    column: str | None = None
    source_site: str | None = None
    version_status: str | None = None
    effective_date_from: str | None = None
    effective_date_to: str | None = None
    version_group: str | None = None
    has_version_relation: bool | None = None
    indicator: str | None = None
    period: str | None = None
    has_source_url: bool | None = None
    article_no: str | None = None
    retrieval: Literal["bm25", "hybrid"] = "bm25"
    rerank: bool = False
    prefer_current: bool = True
    include_superseded: bool = True
    top_k: int = Field(default=5, ge=1, le=50)


class EvalRequest(BaseModel):
    scope: Literal["all", "excel", "text"] = "all"


JsonDict = dict[str, Any]
