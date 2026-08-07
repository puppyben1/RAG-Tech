from jinrong.governance import assess_evidence_authority, audit_version_rows, evidence_authority


def test_authority_requires_source_and_confirmed_version() -> None:
    assert evidence_authority({"version_status": "current", "source_url": "https://example.test"})["authoritative"]
    assert not evidence_authority({"version_status": "unknown", "source_url": "https://example.test"})["authoritative"]
    assert not evidence_authority({"version_status": "current"})["authoritative"]


def test_authority_summary_is_explicit() -> None:
    summary = assess_evidence_authority([{"version_status": "current", "source_url": "https://example.test"}])
    assert summary["authoritative"] is True
    assert summary["status_counts"] == {"current": 1}


def test_version_audit_rejects_bad_relations() -> None:
    report = audit_version_rows(
        [
            {"doc_id": "a", "version_status": "bad", "supersedes_doc_id": "missing"},
            {"doc_id": "b", "version_status": "current", "superseded_by_doc_id": "b"},
        ]
    )
    assert report["invalid_status_count"] == 1
    assert report["dangling_relation_count"] == 1
    assert report["self_relation_count"] == 1

