from jinrong.metadata_extractor import extract_document_metadata


def test_verified_catalog_metadata_takes_precedence_over_body_extraction() -> None:
    record = {
        "doc_id": "nfra_397",
        "title": "银行函证工作操作指引",
        "file_name": "银行函证工作操作指引.docx",
        "sha256": "abc",
        "source_type": "word",
        "file_ext": ".docx",
        "publisher": "财政部办公厅、金融监管总局办公厅",
        "publish_date": "2024-02-22",
        "doc_no": "财办会〔2024〕2号",
        "business_domain": "银行函证",
        "regulatory_topic": "函证",
        "source_url": "https://www.nfra.gov.cn/page",
        "attachment_url": "https://www.nfra.gov.cn/file.docx",
        "version_status": "current",
        "effective_date": "2024-07-01",
        "source_evidence": "official attachment hash",
        "version_evidence": "official effective clause",
        "proof_type": "official_metadata_attachment_and_version",
        "verification_method": "automated_official_metadata_url_sha256",
        "verified_at": "2026-08-07T12:00:00+08:00",
        "proof_evidence": "bound proof report",
    }

    result = extract_document_metadata(record, "正文引用财会〔2022〕39号，并出现 2022年12月1日。")

    assert result["publisher"] == record["publisher"]
    assert result["publish_date"] == record["publish_date"]
    assert result["doc_no"] == record["doc_no"]
    assert result["proof_type"] == record["proof_type"]
    assert result["proof_evidence"] == record["proof_evidence"]
    assert result["metadata_evidence"]["doc_no"] == "verified source catalog"
