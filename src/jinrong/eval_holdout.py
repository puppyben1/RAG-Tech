from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .path_refs import ProjectPathError, to_project_ref
from .utils import ensure_dir, norm_text, read_jsonl


REQUIRED_FIELDS = {"id", "type", "question", "answerable"}
REQUIRED_TYPES = {"open_fact", "table_lookup", "refusal", "compliance_judgement", "text_then_table", "multi_hop"}
REQUIRED_CATEGORIES = {"制度事实", "条款阈值", "业务流程", "统计取数", "跨文件场景判断", "不可回答负例"}
MIN_CASES_PER_CATEGORY = 5


def approve_eval_holdout(
    holdout_path: Path,
    output_path: Path,
    reviewer: str,
    reviewed_at: str,
    case_ids: list[str],
) -> dict[str, Any]:
    """Stamp explicitly reviewed holdout cases into a new JSONL file."""
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    if holdout_path.resolve() == output_path.resolve():
        raise ValueError("approved output must differ from holdout input")
    _parse_reviewed_at(reviewed_at)
    selected = {str(case_id).strip() for case_id in case_ids if str(case_id).strip()}
    if not selected:
        raise ValueError("at least one case_id is required")
    rows = read_jsonl(holdout_path)
    matched = {str(row.get("id")) for row in rows if str(row.get("id")) in selected}
    missing = sorted(selected - matched)
    if missing:
        raise ValueError(f"case_id not found in holdout: {', '.join(missing)}")
    selected_gold_issues = [issue for row in rows if str(row.get("id")) in selected for issue in _gold_issues(row)]
    if selected_gold_issues:
        raise ValueError(f"selected holdout gold is incomplete: {len(selected_gold_issues)} issue(s)")
    for row in rows:
        if str(row.get("id")) in selected:
            row["review_status"] = "reviewed"
            row["reviewed_by"] = reviewer
            row["reviewed_at"] = reviewed_at
    ensure_dir(output_path.parent)
    _write_jsonl(output_path, rows)
    return {
        "input_path": _project_ref_or_none(holdout_path),
        "output_path": _project_ref_or_none(output_path),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "approved_case_ids": sorted(selected),
        "pending_case_ids": sorted(str(row.get("id")) for row in rows if row.get("review_status") != "reviewed"),
    }


def question_fingerprint(question: str) -> str:
    normalized = "".join(norm_text(question).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def freeze_eval_sets(
    dev_path: Path,
    holdout_path: Path,
    output_dir: Path,
    *,
    source_label: str = "explicit_input",
) -> dict[str, Any]:
    dev = _load_and_validate(dev_path, "dev")
    holdout = _load_and_validate(holdout_path, "holdout")
    dev_fp = {row["question_fingerprint"] for row in dev}
    holdout_fp = {row["question_fingerprint"] for row in holdout}
    for split, rows in (("dev", dev), ("holdout", holdout)):
        duplicate_questions = [
            fingerprint
            for fingerprint, count in Counter(row["question_fingerprint"] for row in rows).items()
            if count > 1
        ]
        if duplicate_questions:
            raise ValueError(f"{split}_duplicate_questions:{len(duplicate_questions)}")
    overlap = sorted(dev_fp & holdout_fp)
    if overlap:
        raise ValueError(f"dev_holdout_question_overlap:{len(overlap)}")
    ids = [row["id"] for row in dev + holdout]
    duplicate_ids = sorted(k for k, v in Counter(ids).items() if v > 1)
    if duplicate_ids:
        raise ValueError(f"duplicate_case_ids:{','.join(duplicate_ids)}")
    ensure_dir(output_dir)
    dev_frozen_path = output_dir / "trusted_eval_dev.frozen.jsonl"
    holdout_frozen_path = output_dir / "trusted_eval_holdout.frozen.jsonl"
    _write_jsonl(dev_frozen_path, dev)
    _write_jsonl(holdout_frozen_path, holdout)
    coverage = _coverage(holdout)
    review_pending = any(r["review_status"] != "reviewed" for r in holdout)
    invalid_review_metadata = [
        r["id"] for r in holdout if r["review_status"] == "reviewed" and not _valid_review_metadata(r)
    ]
    gold_issues = [issue for row in holdout for issue in _gold_issues(row)]
    missing_categories = sorted(category for category, count in coverage.items() if count == 0)
    insufficient_categories = {
        category: count for category, count in coverage.items() if count < MIN_CASES_PER_CATEGORY
    }
    gate_reasons = []
    if review_pending:
        gate_reasons.append("pending_external_review")
    if invalid_review_metadata:
        gate_reasons.append("invalid_review_metadata:" + ",".join(invalid_review_metadata))
    if gold_issues:
        gate_reasons.append(f"incomplete_gold_cases:{len({issue['id'] for issue in gold_issues})}")
    if missing_categories:
        gate_reasons.append("missing_categories")
    if insufficient_categories:
        gate_reasons.append("insufficient_category_samples")
    manifest = {
        "schema_version": "holdout_freeze_v1",
        "frozen_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_label": source_label,
        "dev": _dataset_meta(dev_path, dev),
        "holdout": _dataset_meta(holdout_path, holdout),
        "overlap": {"question_fingerprint_count": 0, "case_id_count": 0},
        "coverage": coverage,
        "minimum_cases_per_category": MIN_CASES_PER_CATEGORY,
        "coverage_complete": not insufficient_categories,
        "missing_categories": missing_categories,
        "insufficient_categories": insufficient_categories,
        "gold_issue_count": len(gold_issues),
        "gold_issue_sample": gold_issues[:20],
        "review_status": "reviewed" if not review_pending and not invalid_review_metadata else "pending_external_review",
        "gate": "blocked" if gate_reasons else "ready_for_evaluation",
        "gate_reasons": gate_reasons,
    }
    _set_path_ref(manifest["dev"], "path", dev_path)
    _set_path_ref(manifest["holdout"], "path", holdout_path)
    _set_path_ref(manifest["dev"], "frozen_path", dev_frozen_path)
    _set_path_ref(manifest["holdout"], "frozen_path", holdout_frozen_path)
    (output_dir / "freeze_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _load_and_validate(path: Path, split: str) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    if not rows:
        raise ValueError(f"{split}_empty")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            raise ValueError(f"{split}_missing_fields:{','.join(sorted(missing))}")
        if row["id"] in seen:
            raise ValueError(f"{split}_duplicate_id:{row['id']}")
        if row["type"] not in REQUIRED_TYPES:
            raise ValueError(f"{split}_invalid_type:{row['type']}")
        if not norm_text(row["question"]):
            raise ValueError(f"{split}_empty_question:{row['id']}")
        seen.add(row["id"])
        item = dict(row)
        item["split"] = split
        item["question_fingerprint"] = question_fingerprint(str(row["question"]))
        item.setdefault("category", _category_for(row))
        item.setdefault("gold_provenance", "human_authored_seed")
        item.setdefault("review_status", "pending_external_review")
        result.append(item)
    return result


def _dataset_meta(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "case_count": len(rows),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "question_fingerprint": hashlib.sha256("\n".join(r["question_fingerprint"] for r in rows).encode()).hexdigest(),
        "question_fingerprints": [r["question_fingerprint"] for r in rows],
    }


def _category_for(row: dict[str, Any]) -> str:
    if row.get("answerable") is False or row.get("type") == "refusal":
        return "不可回答负例"
    mapping = {"table_lookup": "统计取数", "multi_hop": "跨文件场景判断", "text_then_table": "跨文件场景判断", "compliance_judgement": "条款阈值"}
    return mapping.get(row.get("type"), "制度事实")


def _coverage(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(r.get("category") for r in rows)
    return {category: counts.get(category, 0) for category in sorted(REQUIRED_CATEGORIES)}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _set_path_ref(payload: dict[str, Any], key: str, path: Path) -> None:
    try:
        payload[key] = to_project_ref(path)
    except ProjectPathError:
        payload[key] = None
        payload[f"{key}_status"] = "external_input"


def _project_ref_or_none(path: Path) -> str | None:
    try:
        return to_project_ref(path)
    except ProjectPathError:
        return None


def _parse_reviewed_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("reviewed_at must include a timezone")
    return parsed


def _valid_review_metadata(row: dict[str, Any]) -> bool:
    if not str(row.get("reviewed_by") or "").strip():
        return False
    try:
        _parse_reviewed_at(str(row.get("reviewed_at") or ""))
    except ValueError:
        return False
    return True


def _gold_issues(row: dict[str, Any]) -> list[dict[str, str]]:
    case_id = str(row.get("id") or "")
    fields: list[str] = []
    if not isinstance(row.get("answerable"), bool):
        fields.append("answerable")
    answerable = row.get("answerable") is not False
    if row.get("category") not in REQUIRED_CATEGORIES:
        fields.append("category")
    expected_route = str(row.get("expected_route") or "")
    if expected_route != ("rag_open" if answerable else "rag_refusal"):
        fields.append("expected_route")
    if answerable:
        raw_doc_ids = row.get("expected_doc_ids")
        expected_doc_ids = [str(value).strip() for value in raw_doc_ids if str(value).strip()] if isinstance(raw_doc_ids, list) else []
        if not expected_doc_ids:
            fields.append("expected_doc_ids")
        raw_evidence_types = row.get("expected_evidence_types")
        evidence_types = (
            [str(value) for value in raw_evidence_types]
            if isinstance(raw_evidence_types, list)
            else [str(row.get("expected_evidence_type") or "")]
        )
        if not evidence_types or any(value not in {"text_unit", "table_row", "table_cell"} for value in evidence_types):
            fields.append("expected_evidence_type")
        raw_must_contain = row.get("must_contain")
        if not isinstance(raw_must_contain, list) or not [str(value).strip() for value in raw_must_contain if str(value).strip()]:
            fields.append("must_contain")
        raw_critical_entities = row.get("critical_entities")
        if row.get("category") in {"条款阈值", "统计取数"} and (
            not isinstance(raw_critical_entities, list)
            or not [str(value).strip() for value in raw_critical_entities if str(value).strip()]
        ):
            fields.append("critical_entities")
        raw_gold_evidence = row.get("gold_evidence")
        gold_evidence = [value for value in raw_gold_evidence if isinstance(value, dict)] if isinstance(raw_gold_evidence, list) else []
        located_doc_ids = {str(value.get("doc_id") or "") for value in gold_evidence if _has_gold_locator(value)}
        if not expected_doc_ids or not set(expected_doc_ids).issubset(located_doc_ids):
            fields.append("gold_evidence")
    elif not str(row.get("refusal_reason") or "").strip():
        fields.append("refusal_reason")
    return [{"id": case_id, "field": field} for field in fields]


def _has_gold_locator(evidence: dict[str, Any]) -> bool:
    if not str(evidence.get("doc_id") or "").strip():
        return False
    if evidence.get("page_no") is not None or str(evidence.get("article_no") or "").strip():
        return True
    return bool(str(evidence.get("sheet_name") or "").strip() and str(evidence.get("cell_ref") or "").strip())
