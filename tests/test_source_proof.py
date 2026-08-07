from __future__ import annotations

import json
from pathlib import Path

from jinrong import source_proof
from jinrong.source_proof import verify_source_catalog


def test_source_proof_matches_local_hash_and_keeps_unmatched_current_claim_pending(tmp_path: Path, monkeypatch) -> None:
    raw_root = tmp_path / "wendang"
    raw_root.mkdir()
    local = raw_root / "sample.pdf"
    local.write_bytes(b"official attachment")
    sha = source_proof._sha256(local)
    catalog = tmp_path / "candidate.jsonl"
    catalog.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "sha256": sha,
                "file_name": local.name,
                "title": "Sample",
                "source_url": "https://example.gov.cn/page",
                "attachment_url": "https://example.gov.cn/sample.pdf",
                "version_status": "current",
                "version_evidence": "effective clause",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        source_proof,
        "_verify_url",
        lambda value, timeout, expected_sha256=None, expected_text=None: {
            "url": value,
            "official_host": True,
            "status_code": 200,
            "bytes": 1,
            "sha256": expected_sha256,
            "sha256_match": True,
            "text_matches": [],
            "error": None,
        },
    )
    monkeypatch.setattr(source_proof, "to_project_ref", lambda path: str(path))
    report = verify_source_catalog(catalog, raw_root, tmp_path / "proof.json")

    assert report["status_counts"] == {"needs_review": 1}
    assert report["import_allowed"] is False
    assert report["results"][0]["checks"]["local_file"]["sha256_match"] is True
    assert "version_evidence_not_matched" in report["results"][0]["reasons"]


def test_source_proof_accepts_machine_verified_current_claim(tmp_path: Path, monkeypatch) -> None:
    raw_root = tmp_path / "wendang"
    raw_root.mkdir()
    local = raw_root / "sample.pdf"
    local.write_bytes(b"official attachment")
    sha = source_proof._sha256(local)
    catalog = tmp_path / "candidate.jsonl"
    catalog.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "sha256": sha,
                "file_name": local.name,
                "title": "Sample",
                "source_url": "https://www.nfra.gov.cn/page?docId=1",
                "attachment_url": "https://www.nfra.gov.cn/sample.pdf",
                "version_status": "current",
                "effective_date": "2026-01-01",
                "version_evidence": "official effective clause",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        source_proof,
        "_verify_url",
        lambda value, timeout, expected_sha256=None, expected_text=None: {
            "url": value,
            "official_host": True,
            "status_code": 200,
            "bytes": 1,
            "sha256": expected_sha256,
            "sha256_match": True,
            "text_matches": [],
            "error": None,
        },
    )
    monkeypatch.setattr(
        source_proof,
        "_verify_nfra_metadata",
        lambda row, timeout: {"identity_match": True, "effective_date_match": True},
    )
    monkeypatch.setattr(source_proof, "to_project_ref", lambda path: str(path))

    verified_catalog = tmp_path / "verified.jsonl"
    report = verify_source_catalog(
        catalog,
        raw_root,
        tmp_path / "proof.json",
        verified_catalog_path=verified_catalog,
    )

    assert report["status_counts"] == {"verified": 1}
    assert report["import_allowed"] is True
    assert report["results"][0]["proof_type"] == "official_metadata_attachment_and_version"
    verified_row = json.loads(verified_catalog.read_text(encoding="utf-8"))
    assert verified_row["verification_method"] == "automated_official_metadata_url_sha256"
    assert verified_row["reviewed_by"] == ""
    assert "proof.json" in verified_row["proof_evidence"]


def test_source_proof_rejects_missing_local_file(tmp_path: Path, monkeypatch) -> None:
    catalog = tmp_path / "candidate.jsonl"
    catalog.write_text(json.dumps({"doc_id": "doc-1", "file_name": "missing.pdf"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(source_proof, "to_project_ref", lambda path: str(path))
    monkeypatch.setattr(source_proof, "_verify_url", lambda *args, **kwargs: {"official_host": False, "status_code": None, "sha256_match": False})

    report = verify_source_catalog(catalog, tmp_path / "wendang", tmp_path / "proof.json")

    assert report["import_allowed"] is False
    assert report["results"][0]["checks"]["local_file"]["found"] is False
