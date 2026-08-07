from collections import Counter

from jinrong.metadata_extractor import extract_document_metadata
from jinrong.source_worklist import _missing_fields, _worklist_row


def test_metadata_and_worklist_preserve_sha256() -> None:
    metadata = extract_document_metadata(
        {
            "doc_id": "doc-1",
            "title": "Example",
            "file_name": "example.pdf",
            "file_ext": ".pdf",
            "source_type": "pdf",
            "sha256": "abc123",
        }
    )

    row = _worklist_row(metadata, Counter(), Counter())

    assert metadata["sha256"] == "abc123"
    assert row["sha256"] == "abc123"


def test_machine_proof_replaces_manual_signature_in_worklist() -> None:
    doc = {
        "source_url": "https://official/page",
        "attachment_url": "https://official/file",
        "source_site": "Official",
        "publish_date": "2026-01-01",
        "version_status": "current",
        "effective_date": "2026-01-01",
        "source_evidence": "official page",
        "version_evidence": "effective clause",
        "proof_type": "official_metadata_attachment_and_version",
        "verification_method": "automated_official_metadata_url_sha256",
        "verified_at": "2026-08-07T12:00:00+08:00",
        "proof_evidence": "bound proof report",
        "reviewed_by": None,
        "reviewed_at": None,
    }

    assert _missing_fields(doc) == []
