from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Any, Iterable

from .utils import ensure_dir, read_jsonl


PATTERNS = {
    "mainland_id": re.compile(r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)"),
    "mobile_phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "email": re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    "account_number": re.compile(r"(?<![\d.])\d{16,19}(?![\d.])"),
}
PHONE_CONTEXT = ("手机", "电话", "联系方式", "联系电话", "联系人")
ACCOUNT_CONTEXT = ("账号", "银行账号", "银行卡号", "卡号", "存款账号", "结算账户号", "交易账号")
SAFE_DISPOSITIONS = {"false_positive", "authorized_public_template"}


def scan_sensitive_information(
    text_units_path: Path,
    table_cells_path: Path,
    report_path: Path,
    *,
    decisions_path: Path | None = None,
) -> dict[str, Any]:
    salt = secrets.token_bytes(32)
    candidates: list[dict[str, Any]] = []
    records_scanned = 0
    for source_kind, rows in (
        ("text_unit", read_jsonl(text_units_path)),
        ("table_cell", read_jsonl(table_cells_path)),
    ):
        for row in rows:
            records_scanned += 1
            text, context = _scan_text_and_context(source_kind, row)
            source_id = str(row.get("unit_id") or row.get("cell_id") or "")
            for rule, pattern in PATTERNS.items():
                for match in pattern.finditer(text):
                    if rule == "mobile_phone" and not _has_context(text, context, match.start(), match.end(), PHONE_CONTEXT):
                        continue
                    if rule == "account_number" and not _has_context(text, context, match.start(), match.end(), ACCOUNT_CONTEXT):
                        continue
                    value = match.group(0)
                    digest = hashlib.sha256(salt + rule.encode("ascii") + b"\0" + value.encode("utf-8")).hexdigest()
                    candidate_id = hashlib.sha256(
                        f"{rule}\0{row.get('doc_id')}\0{source_kind}\0{source_id}\0{match.start()}\0{match.end()}".encode(
                            "utf-8"
                        )
                    ).hexdigest()[:24]
                    candidates.append(
                        {
                            "candidate_id": candidate_id,
                            "rule": rule,
                            "doc_id": row.get("doc_id"),
                            "source_kind": source_kind,
                            "source_id": source_id,
                            "page_no": row.get("page_no"),
                            "article_no": row.get("article_no"),
                            "sheet_name": row.get("sheet_name"),
                            "cell_ref": row.get("cell_ref"),
                            "match_length": len(value),
                            "run_scoped_digest": digest,
                        }
                    )
    candidates = _deduplicate(candidates)
    scan_fingerprint = _candidate_fingerprint(candidates)
    decisions = _load_decisions(decisions_path, scan_fingerprint)
    confirmed = []
    unresolved = []
    for candidate in candidates:
        disposition = decisions.get(candidate["candidate_id"])
        candidate["disposition"] = disposition
        if disposition == "confirmed_sensitive":
            confirmed.append(candidate["candidate_id"])
        elif disposition not in SAFE_DISPOSITIONS:
            unresolved.append(candidate["candidate_id"])
    gate_reasons = []
    if confirmed:
        gate_reasons.append(f"confirmed_sensitive:{len(confirmed)}")
    if unresolved:
        gate_reasons.append(f"sensitive_candidates_unresolved:{len(unresolved)}")
    report = {
        "schema_version": "sensitive_audit_v1",
        "records_scanned": records_scanned,
        "candidate_count": len(candidates),
        "confirmed_sensitive_count": len(confirmed),
        "unresolved_count": len(unresolved),
        "scan_fingerprint": scan_fingerprint,
        "raw_match_values_persisted": False,
        "gate": "passed" if not gate_reasons else "blocked",
        "gate_reasons": gate_reasons,
        "candidates": candidates[:500],
        "candidate_sample_truncated": len(candidates) > 500,
    }
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _scan_text_and_context(source_kind: str, row: dict[str, Any]) -> tuple[str, str]:
    if source_kind == "table_cell":
        value = row.get("value_raw")
        text = "" if value is None else str(value)
        context = " ".join(
            str(row.get(field) or "")
            for field in ("sheet_name", "row_header", "col_header", "unit")
        )
        return text, context
    text = str(row.get("text") or "")
    return text, ""


def _has_context(text: str, row_context: str, start: int, end: int, terms: tuple[str, ...]) -> bool:
    local_context = text[max(0, start - 24) : min(len(text), end + 24)]
    context = f"{local_context} {row_context}"
    return any(term in context for term in terms)


def _deduplicate(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result.setdefault(str(row["candidate_id"]), row)
    return [result[key] for key in sorted(result)]


def _candidate_fingerprint(rows: list[dict[str, Any]]) -> str:
    stable = [
        {key: value for key, value in row.items() if key not in {"run_scoped_digest", "disposition"}}
        for row in rows
    ]
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _load_decisions(path: Path | None, fingerprint: str) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("scan_fingerprint") != fingerprint:
        return {}
    return {
        str(row.get("candidate_id")): str(row.get("disposition"))
        for row in payload.get("decisions") or []
        if row.get("candidate_id")
    }
