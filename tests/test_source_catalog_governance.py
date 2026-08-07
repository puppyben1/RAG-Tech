import csv
import json

import pytest

import jinrong.source_catalog as source_catalog
from jinrong.source_catalog import CATALOG_FIELDS, enrich_manifest_from_source_catalog, validate_source_catalog


def _write_manifest(path) -> None:
    path.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "sha256": "abc",
                "file_name": "one.pdf",
                "title": "One",
                "source_type": "pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_catalog(path, **updates) -> None:
    row = {field: "" for field in CATALOG_FIELDS}
    row.update({"doc_id": "doc-1", "sha256": "abc", "file_name": "one.pdf", "title": "One"})
    row.update(updates)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def test_authority_claim_requires_review_provenance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(source_catalog, "to_project_ref", lambda path: path.name)
    manifest = tmp_path / "manifest.jsonl"
    catalog = tmp_path / "catalog.csv"
    report = tmp_path / "validation.json"
    _write_manifest(manifest)
    _write_catalog(catalog, source_url="https://example.invalid/source", version_status="current")

    result = validate_source_catalog(catalog, manifest_path=manifest, report_path=report)

    assert result["valid"] is False
    assert result["url_warning_count"] == 1
    assert result["review_issue_count"] == 4


def test_reviewed_not_applicable_snapshot_is_valid(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(source_catalog, "to_project_ref", lambda path: path.name)
    manifest = tmp_path / "manifest.jsonl"
    catalog = tmp_path / "catalog.csv"
    report = tmp_path / "validation.json"
    _write_manifest(manifest)
    _write_catalog(
        catalog,
        source_url="https://www.gov.cn/source",
        version_status="not_applicable",
        period="2026-01",
        source_evidence="official publication page",
        version_evidence="point-in-time statistics",
        reviewed_by="reviewer-1",
        reviewed_at="2026-08-06T12:00:00+08:00",
    )

    result = validate_source_catalog(catalog, manifest_path=manifest, report_path=report)

    assert result["valid"] is True


def test_automated_proof_can_replace_manual_reviewer(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(source_catalog, "to_project_ref", lambda path: path.name)
    manifest = tmp_path / "manifest.jsonl"
    catalog = tmp_path / "catalog.csv"
    report = tmp_path / "validation.json"
    _write_manifest(manifest)
    _write_catalog(
        catalog,
        source_url="https://www.gov.cn/source",
        attachment_url="https://www.gov.cn/source.pdf",
        version_status="current",
        source_evidence="official attachment hash match",
        version_evidence="official effective-date record",
        proof_type="official_attachment_hash",
        verification_method="automated_url_and_sha256",
        verified_at="2026-08-07T12:00:00+08:00",
        proof_evidence="sha256=abc",
    )

    result = validate_source_catalog(catalog, manifest_path=manifest, report_path=report)

    assert result["valid"] is True


def test_enrichment_rejects_invalid_catalog(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(source_catalog, "to_project_ref", lambda path: path.name)
    manifest = tmp_path / "manifest.jsonl"
    catalog = tmp_path / "catalog.csv"
    _write_manifest(manifest)
    _write_catalog(catalog, source_url="placeholder", version_status="current")

    with pytest.raises(ValueError, match="blocking issue"):
        enrich_manifest_from_source_catalog(
            catalog,
            manifest_path=manifest,
            output_path=tmp_path / "enriched.jsonl",
            report_path=tmp_path / "enrichment.json",
        )

    assert not (tmp_path / "enriched.jsonl").exists()
