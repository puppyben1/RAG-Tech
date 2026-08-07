from __future__ import annotations

import hashlib
import json
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .path_refs import ProjectPathError, to_project_ref
from .source_catalog import _read_catalog, _write_catalog
from .utils import ensure_dir, norm_text


OFFICIAL_SUFFIXES = ("gov.cn", "gov.hk", "gov.mo")


def verify_source_catalog(
    source_catalog_path: Path,
    raw_root: Path,
    output_path: Path,
    timeout: int = 30,
    verified_catalog_path: Path | None = None,
) -> dict[str, Any]:
    rows = _read_catalog(source_catalog_path)
    results = [_verify_row(row, raw_root, timeout) for row in rows]
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "catalog_path": to_project_ref(source_catalog_path),
        "raw_root": _project_ref_or_none(raw_root),
        "rows": len(results),
        "status_counts": status_counts,
        "results": results,
        "import_allowed": all(result["status"] == "verified" for result in results) if results else False,
    }
    if verified_catalog_path is not None:
        if not report["import_allowed"]:
            raise ValueError("verified catalog requires every source row to be verified")
        if verified_catalog_path.resolve() == source_catalog_path.resolve():
            raise ValueError("verified catalog output must differ from candidate catalog")
        _write_verified_catalog(rows, results, output_path, verified_catalog_path, report["generated_at"])
        report["verified_catalog_path"] = to_project_ref(verified_catalog_path)
    ensure_dir(output_path.parent)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output_path": to_project_ref(output_path), **report}


def _write_verified_catalog(
    rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    proof_report_path: Path,
    output_path: Path,
    verified_at: str,
) -> None:
    result_by_doc = {str(result["doc_id"]): result for result in results}
    verified_rows: list[dict[str, Any]] = []
    for source_row in rows:
        row = dict(source_row)
        result = result_by_doc[str(row.get("doc_id") or "")]
        checks = result["checks"]
        row.update(
            {
                "proof_type": result["proof_type"],
                "verification_method": "automated_official_metadata_url_sha256",
                "verified_at": verified_at,
                "proof_evidence": json.dumps(
                    {
                        "report": to_project_ref(proof_report_path),
                        "local_sha256": checks["local_file"]["sha256"],
                        "attachment_sha256": checks["attachment_url"]["sha256"],
                        "source_metadata_url": checks["source_metadata"].get("url"),
                        "version_evidence_url": checks["version_evidence_url"].get("url"),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "reviewed_by": "",
                "reviewed_at": "",
            }
        )
        verified_rows.append(row)
    _write_catalog(output_path, verified_rows)


def _verify_row(row: dict[str, Any], raw_root: Path, timeout: int) -> dict[str, Any]:
    doc_id = str(row.get("doc_id") or "")
    checks: dict[str, Any] = {}
    local_matches = list(raw_root.rglob(str(row.get("file_name") or ""))) if row.get("file_name") else []
    local_path = local_matches[0] if len(local_matches) == 1 else None
    checks["local_file"] = {
        "found": bool(local_path),
        "unique": len(local_matches) == 1,
        "sha256": _sha256(local_path) if local_path else None,
        "expected_sha256": row.get("sha256"),
        "sha256_match": bool(local_path and _sha256(local_path) == row.get("sha256")),
    }
    checks["source_url"] = _verify_url(row.get("source_url"), timeout, expected_text=[row.get("title"), row.get("doc_no")])
    checks["source_metadata"] = _verify_nfra_metadata(row, timeout)
    checks["attachment_url"] = _verify_url(
        row.get("attachment_url"),
        timeout,
        expected_sha256=row.get("sha256"),
        expected_text=[],
    )
    raw_page_identity = all(checks["source_url"].get("text_matches") or [])
    metadata_identity = checks["source_metadata"].get("identity_match", False)
    source_ok = (
        checks["local_file"]["sha256_match"]
        and checks["source_url"]["official_host"]
        and checks["source_url"]["status_code"] == 200
        and (raw_page_identity or metadata_identity)
        and checks["attachment_url"]["official_host"]
        and checks["attachment_url"]["status_code"] == 200
        and checks["attachment_url"]["sha256_match"]
    )
    checks["version_evidence_url"] = _verify_version_evidence_url(
        row.get("version_evidence_url"), row.get("effective_date"), timeout
    )
    attachment_hash_ok = checks["local_file"]["sha256_match"] and checks["attachment_url"]["sha256_match"]
    version_evidence = bool(str(row.get("version_evidence") or "").strip())
    version_claim = row.get("version_status") or "unknown"
    version_date_ok = bool(
        checks["source_metadata"].get("effective_date_match")
        or checks["version_evidence_url"].get("effective_date_match")
    )
    version_ok = version_claim in {"unknown", "not_applicable"} or (version_evidence and version_date_ok)
    automated_ok = source_ok and version_ok
    status = "verified" if automated_ok else "needs_review"
    reasons = []
    if not source_ok:
        reasons.append("automated_proof_incomplete")
    if checks["source_url"].get("status_code") == 200 and not (raw_page_identity or metadata_identity):
        reasons.append("source_page_identity_not_matched")
    if not version_evidence:
        reasons.append("missing_version_evidence")
    if version_claim in {"current", "superseded"} and not version_date_ok:
        reasons.append("version_evidence_not_matched")
    return {
        "doc_id": doc_id,
        "status": status,
        "proof_type": "official_metadata_attachment_and_version" if automated_ok else ("official_attachment_hash" if attachment_hash_ok else "incomplete"),
        "reasons": reasons,
        "checks": checks,
        "version_status_claim": row.get("version_status") or "unknown",
        "effective_date_claim": row.get("effective_date") or None,
    }


def _verify_nfra_metadata(row: dict[str, Any], timeout: int) -> dict[str, Any]:
    source_url = str(row.get("source_url") or "").strip()
    parsed = urlparse(source_url)
    doc_ids = parse_qs(parsed.query).get("docId", [])
    result: dict[str, Any] = {
        "url": None,
        "status_code": None,
        "identity_match": False,
        "title_match": False,
        "doc_no_match": False,
        "publish_date_match": False,
        "attachment_url_match": False,
        "effective_date_match": False,
        "error": None,
    }
    if parsed.hostname != "www.nfra.gov.cn" or len(doc_ids) != 1 or not doc_ids[0].isdigit():
        result["error"] = "NFRA docId metadata is not available for this source URL"
        return result
    metadata_url = f"https://www.nfra.gov.cn/cn/static/data/DocInfo/SelectByDocId/data_docId={doc_ids[0]}.json"
    result["url"] = metadata_url
    try:
        request = Request(metadata_url, headers={"User-Agent": "JinrongTrustedRAG/0.1 source-proof"})
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            result["status_code"] = int(response.status)
            payload = json.load(response)
        data = payload.get("data") or {}
        attachments = data.get("attachmentInfoVOList") or []
        attachment_text = " ".join(
            str(value or "")
            for attachment in attachments
            for value in (attachment.get("title"), attachment.get("urlOtherName"))
        )
        visible = " ".join(
            [
                str(data.get("docTitle") or ""),
                str(data.get("documentNo") or ""),
                str(data.get("publishDate") or ""),
                _html_text(str(data.get("docClob") or "")),
                attachment_text,
            ]
        )
        result["title_match"] = _contains_identity(visible, row.get("title"))
        result["doc_no_match"] = _contains_identity(visible, row.get("doc_no"))
        publish_date = str(row.get("publish_date") or "").strip()
        result["publish_date_match"] = not publish_date or str(data.get("publishDate") or "").startswith(publish_date)
        attachment_path = urlparse(str(row.get("attachment_url") or "")).path
        result["attachment_url_match"] = bool(attachment_path and attachment_path in attachment_text)
        result["effective_date_match"] = _effective_date_matches(
            visible,
            row.get("effective_date"),
            publish_date,
        )
        result["identity_match"] = all(
            result[key]
            for key in ("title_match", "doc_no_match", "publish_date_match", "attachment_url_match")
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
    return result


def _verify_version_evidence_url(value: Any, effective_date: Any, timeout: int) -> dict[str, Any]:
    if not str(value or "").strip():
        return {"url": None, "official_host": False, "status_code": None, "effective_date_match": False, "error": None}
    check = _verify_url(value, timeout, expected_text=_date_text_variants(effective_date))
    return {
        "url": check["url"],
        "official_host": check["official_host"],
        "status_code": check["status_code"],
        "effective_date_match": bool(check["official_host"] and check["status_code"] == 200 and any(check["text_matches"])),
        "error": check["error"],
    }


def _verify_url(
    value: Any,
    timeout: int,
    expected_sha256: str | None = None,
    expected_text: list[Any] | None = None,
) -> dict[str, Any]:
    url = str(value or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    result: dict[str, Any] = {
        "url": url or None,
        "official_host": bool(host and (host in OFFICIAL_SUFFIXES or host.endswith(tuple(f".{suffix}" for suffix in OFFICIAL_SUFFIXES)))),
        "status_code": None,
        "bytes": None,
        "sha256": None,
        "sha256_match": expected_sha256 is None,
        "text_matches": [],
        "error": None,
    }
    if not url or parsed.scheme != "https" or not result["official_host"]:
        result["error"] = "https URL on an allowed official domain is required"
        return result
    try:
        request = Request(url, headers={"User-Agent": "JinrongTrustedRAG/0.1 source-proof"})
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            data = response.read()
            result["status_code"] = int(response.status)
            result["bytes"] = len(data)
            result["sha256"] = _bytes_sha256(data)
            if expected_sha256:
                result["sha256_match"] = result["sha256"] == expected_sha256
            if expected_text:
                text = norm_text(data.decode("utf-8", errors="ignore"))
                result["text_matches"] = [bool(value and norm_text(value) in text) for value in expected_text]
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        result["error"] = str(exc)
    return result


def _sha256(path: Path | None) -> str | None:
    if not path or not path.is_file():
        return None
    with path.open("rb") as handle:
        return _stream_sha256(handle)


def _bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stream_sha256(handle: Any) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return " ".join(parser.parts)


def _identity_text(value: Any) -> str:
    return "".join(character.casefold() for character in norm_text(value) if character.isalnum())


def _contains_identity(haystack: Any, needle: Any) -> bool:
    normalized_needle = _identity_text(needle)
    return bool(normalized_needle and normalized_needle in _identity_text(haystack))


def _date_text_variants(value: Any) -> list[str]:
    raw = str(value or "").strip()
    parts = raw.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return [raw] if raw else []
    year, month, day = (int(part) for part in parts)
    return [raw, f"{year}年{month}月{day}日", f"{year} 年 {month} 月 {day} 日"]


def _effective_date_matches(text: str, effective_date: Any, publish_date: str) -> bool:
    variants = _date_text_variants(effective_date)
    normalized = _identity_text(text)
    if any(_identity_text(value) in normalized for value in variants):
        return True
    return bool(str(effective_date or "").strip() == publish_date and _identity_text("自公布之日起施行") in normalized)


def _project_ref_or_none(path: Path) -> str | None:
    try:
        return to_project_ref(path)
    except ProjectPathError:
        return None
