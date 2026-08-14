from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import MANIFEST_PATH
from .qa_data import load_qa
from .utils import read_jsonl


EVIDENCE_PATH = re.compile(r"(?:data/raw/nfra_page_attachments_500/|wendang/data/)([^；;]+)")


def audit_qa_data(qa_path: Path, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    items = load_qa(qa_path)
    manifest = read_jsonl(manifest_path)
    by_file_name = {str(row.get("file_name")): row for row in manifest if row.get("file_name")}
    unresolved_ids: list[str] = []
    ambiguous_ids: list[str] = []
    old_path_ids: list[str] = []
    body_evidence_ids: list[str] = []
    resolved = 0

    for item in items:
        evidence = item.evidence.replace("\\", "/")
        match = EVIDENCE_PATH.search(evidence)
        if "data/raw/" in evidence:
            old_path_ids.append(item.id)
        if not match:
            body_evidence_ids.append(item.id)

        candidates = find_qa_candidates(item.file_label, item.source_title, match.group(1) if match else None, manifest, by_file_name)
        if len(candidates) == 1:
            resolved += 1
        elif len(candidates) > 1:
            ambiguous_ids.append(item.id)
        else:
            unresolved_ids.append(item.id)

    required_structured_fields = ["doc_id", "local_path", "source_url", "tags", "gold_evidence"]
    return {
        "status": "passed" if not unresolved_ids and not ambiguous_ids and not old_path_ids and not body_evidence_ids else "blocked",
        "qa_path": qa_path.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "total": len(items),
        "resolved_unique": resolved,
        "ambiguous": len(ambiguous_ids),
        "unresolved": len(unresolved_ids),
        "old_path_prefix": len(old_path_ids),
        "body_text_evidence": len(body_evidence_ids),
        "missing_structured_fields": required_structured_fields,
        "sample_ids": {
            "ambiguous": ambiguous_ids[:10],
            "unresolved": unresolved_ids[:10],
            "old_path_prefix": old_path_ids[:10],
            "body_text_evidence": body_evidence_ids[:10],
        },
    }


def find_qa_candidates(
    file_label: str,
    source_title: str,
    evidence_file_name: str | None,
    manifest: list[dict[str, Any]],
    by_file_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if evidence_file_name and evidence_file_name in by_file_name:
        return [by_file_name[evidence_file_name]]
    label_stem = Path(file_label).stem.strip().casefold()
    title = source_title.strip().casefold()
    matches = []
    for row in manifest:
        file_name = str(row.get("file_name") or "")
        row_title = str(row.get("title") or "").strip().casefold()
        stem_without_id = re.sub(r"^\d+_", "", Path(file_name).stem).casefold()
        if label_stem and (stem_without_id == label_stem or row_title == label_stem):
            matches.append(row)
        elif title and row_title == title:
            matches.append(row)
    return list({str(row.get("doc_id")): row for row in matches}.values())


def audit_to_json(qa_path: Path, manifest_path: Path = MANIFEST_PATH) -> str:
    return json.dumps(audit_qa_data(qa_path, manifest_path), ensure_ascii=False, indent=2)
