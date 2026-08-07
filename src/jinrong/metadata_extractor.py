from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .config import DOCUMENT_METADATA_PATH, MANIFEST_ENRICHED_PATH, MANIFEST_PATH, METADATA_EXTRACTION_REPORT, TEXT_CHUNKS_PATH
from .manifest import build_manifest
from .path_refs import to_project_ref
from .utils import ensure_dir, norm_text, read_jsonl, write_jsonl


PUBLISHERS = [
    "国家金融监督管理总局",
    "中国银行保险监督管理委员会",
    "中国银保监会",
    "中国银行业监督管理委员会",
    "中国人民银行",
    "国务院",
    "财政部",
    "财政部办公厅",
    "金融监管总局办公厅",
    "银监会",
    "银保监会",
]

DOMAIN_RULES = [
    ("监管统计", ["统计", "报表", "总资产", "总负债", "保费收入", "监管统计"]),
    ("保险经营统计", ["保险业经营情况表", "人身险公司经营情况表", "财产险公司经营情况表", "财产保险公司经营情况表"]),
    ("保险资金运用", ["资金运用情况表"]),
    ("绿色金融", ["绿色信贷", "绿色金融", "节能环保"]),
    ("银行函证", ["函证", "询证函"]),
    ("资本管理", ["资本", "偿付能力", "最低资本", "资本充足"]),
    ("消费者权益保护", ["消费者权益", "消保", "投诉"]),
    ("反洗钱", ["反洗钱", "洗钱"]),
    ("支付结算", ["支付", "结算", "账户"]),
    ("普惠金融", ["普惠", "小微", "涉农"]),
    ("行政许可", ["行政许可", "许可事项", "准入"]),
    ("风险管理", ["风险分类", "风险管理", "内控", "不良"]),
]

REGULATORY_STATISTICS_TITLE_KEYWORDS = [
    "银行业总资产",
    "总资产、总负债",
    "全国各地区原保险保费收入",
    "保险业经营情况表",
    "人身险公司经营情况表",
    "财产险公司经营情况表",
    "财产保险公司经营情况表",
    "商业银行主要监管指标",
    "商业银行主要指标分机构类",
    "普惠型小微企业贷款",
    "普惠型涉农贷款",
    "偿付能力状况表",
    "资金运用情况表",
    "监管统计信息发布日程",
    "监管统计信息披露日程",
    "机构范围",
    "指标解释",
]

EXCEL_DEFAULT_PUBLISHER = "国家金融监督管理总局"
EXCEL_LEGACY_PUBLISHER = "中国银行保险监督管理委员会"


def build_document_metadata(
    manifest_path: Path = MANIFEST_PATH,
    chunks_path: Path = TEXT_CHUNKS_PATH,
    output_path: Path = DOCUMENT_METADATA_PATH,
    report_path: Path = METADATA_EXTRACTION_REPORT,
) -> dict[str, Any]:
    if manifest_path == MANIFEST_PATH and MANIFEST_ENRICHED_PATH.exists():
        manifest_path = MANIFEST_ENRICHED_PATH
    if not manifest_path.exists():
        build_manifest()
    manifest = read_jsonl(manifest_path)
    first_text = _first_text_by_doc(chunks_path)
    rows = [extract_document_metadata(record, first_text.get(record["doc_id"], "")) for record in manifest]
    write_jsonl(output_path, rows)
    report = _build_report(rows, output_path)
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def extract_document_metadata(record: dict[str, Any], first_text: str = "") -> dict[str, Any]:
    source = "\n".join([record.get("file_name", ""), record.get("title", ""), first_text[:3000]])
    extracted_publisher, publisher_evidence = _extract_publisher(source)
    extracted_doc_no, doc_no_evidence = _extract_doc_no(source)
    extracted_publish_date, publish_date_evidence = _extract_publish_date(source)
    extracted_domain, extracted_topic = _classify_domain(record, first_text)
    publisher = record.get("publisher") or extracted_publisher
    doc_no = record.get("doc_no") or extracted_doc_no
    publish_date = record.get("publish_date") or extracted_publish_date
    business_domain = record.get("business_domain") or extracted_domain
    regulatory_topic = record.get("regulatory_topic") or extracted_topic
    if record.get("publisher"):
        publisher_evidence = "verified source catalog"
    if record.get("doc_no"):
        doc_no_evidence = "verified source catalog"
    if record.get("publish_date"):
        publish_date_evidence = "verified source catalog"
    column = record.get("column") or _infer_column(record, business_domain)
    if not publisher:
        publisher, publisher_evidence = _infer_publisher_from_record(record)
    return {
        "doc_id": record["doc_id"],
        "title": record.get("title"),
        "file_name": record.get("file_name"),
        "sha256": record.get("sha256"),
        "source_type": record.get("source_type"),
        "file_ext": record.get("file_ext"),
        "period": record.get("period"),
        "publisher": publisher,
        "publish_date": publish_date,
        "doc_no": doc_no,
        "business_domain": business_domain,
        "regulatory_topic": regulatory_topic,
        "source_url": record.get("source_url"),
        "attachment_url": record.get("attachment_url"),
        "column": column,
        "source_site": record.get("source_site"),
        "version_status": record.get("version_status") or "unknown",
        "effective_date": record.get("effective_date"),
        "expiry_date": record.get("expiry_date"),
        "supersedes_doc_id": record.get("supersedes_doc_id"),
        "superseded_by_doc_id": record.get("superseded_by_doc_id"),
        "version_group": record.get("version_group"),
        "source_evidence": record.get("source_evidence"),
        "version_evidence": record.get("version_evidence"),
        "version_evidence_url": record.get("version_evidence_url"),
        "proof_type": record.get("proof_type"),
        "verification_method": record.get("verification_method"),
        "verified_at": record.get("verified_at"),
        "proof_evidence": record.get("proof_evidence"),
        "reviewed_by": record.get("reviewed_by"),
        "reviewed_at": record.get("reviewed_at"),
        "metadata_evidence": {
            "publisher": publisher_evidence,
            "publish_date": publish_date_evidence,
            "doc_no": doc_no_evidence,
        },
    }


def _first_text_by_doc(chunks_path: Path) -> dict[str, str]:
    if not chunks_path.exists():
        return {}
    first: dict[str, str] = {}
    for row in read_jsonl(chunks_path):
        doc_id = row.get("doc_id")
        if doc_id and doc_id not in first:
            first[doc_id] = str(row.get("text", ""))
    return first


def _extract_publisher(text: str) -> tuple[str | None, str | None]:
    matches = [publisher for publisher in PUBLISHERS if publisher in text]
    if not matches:
        return None, None
    # Prefer the longest official name when aliases overlap.
    matches.sort(key=len, reverse=True)
    return "、".join(_dedupe(matches[:3])), _evidence_window(text, matches[0])


def _extract_doc_no(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"[\u4e00-\u9fffA-Za-z]{0,12}〔\d{4}〕\s*\d+\s*号",
        r"[\u4e00-\u9fffA-Za-z]{0,12}\[\d{4}\]\s*\d+\s*号",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = re.sub(r"\s+", "", match.group(0))
            return value, _evidence_window(text, match.group(0))
    return None, None


def _extract_publish_date(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not match:
        return None, None
    year, month, day = match.groups()
    value = f"{year}-{int(month):02d}-{int(day):02d}"
    return value, _evidence_window(text, match.group(0))


def _classify_domain(record: dict[str, Any], first_text: str) -> tuple[str, str | None]:
    hay = f"{record.get('title', '')} {record.get('file_name', '')} {first_text[:1000]}"
    title = str(record.get("title", ""))
    if record.get("source_type") == "excel":
        for keyword in REGULATORY_STATISTICS_TITLE_KEYWORDS:
            if keyword in title:
                if "经营情况表" in title:
                    return "保险经营统计", keyword
                if "资金运用" in title:
                    return "保险资金运用", keyword
                return "监管统计", keyword
    for domain, keywords in DOMAIN_RULES:
        for keyword in keywords:
            if keyword in hay:
                return domain, keyword
    return "其他", None


def _infer_column(record: dict[str, Any], business_domain: str) -> str | None:
    if record.get("column"):
        return str(record.get("column"))
    if record.get("source_type") != "excel":
        return None
    title = str(record.get("title", ""))
    if any(keyword in title for keyword in REGULATORY_STATISTICS_TITLE_KEYWORDS):
        return "监管统计数据"
    if business_domain in {"监管统计", "保险经营统计", "保险资金运用", "普惠金融", "资本管理"}:
        return "监管统计数据"
    return None


def _infer_publisher_from_record(record: dict[str, Any]) -> tuple[str | None, str | None]:
    if record.get("source_type") != "excel":
        return None, None
    title = str(record.get("title", ""))
    if not any(keyword in title for keyword in REGULATORY_STATISTICS_TITLE_KEYWORDS):
        return None, None
    period = str(record.get("period") or title)
    publisher = EXCEL_LEGACY_PUBLISHER if re.search(r"20(1\d|2[0-2])", period) else EXCEL_DEFAULT_PUBLISHER
    evidence = f"根据 Excel 监管统计报表标题规则推断：{title}"
    return publisher, evidence


def _evidence_window(text: str, needle: str, radius: int = 80) -> str:
    idx = text.find(needle)
    if idx < 0:
        return needle
    start = max(idx - radius, 0)
    end = min(idx + len(needle) + radius, len(text))
    return text[start:end].replace("\n", " ").strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            rows.append(value)
    return rows


def _build_report(rows: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    total = len(rows)
    by_type = Counter(row.get("source_type") for row in rows)
    by_domain = Counter(row.get("business_domain") for row in rows)
    return {
        "output_path": to_project_ref(output_path),
        "documents": total,
        "publisher_filled": sum(1 for row in rows if row.get("publisher")),
        "publish_date_filled": sum(1 for row in rows if row.get("publish_date")),
        "doc_no_filled": sum(1 for row in rows if row.get("doc_no")),
        "source_url_filled": sum(1 for row in rows if row.get("source_url")),
        "attachment_url_filled": sum(1 for row in rows if row.get("attachment_url")),
        "by_source_type": dict(by_type),
        "by_business_domain": dict(by_domain),
    }
