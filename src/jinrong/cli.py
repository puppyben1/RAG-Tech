from __future__ import annotations

import argparse
import json

from .ask import ask
from pathlib import Path

from .config import EXCEL_EVAL_REPORT, MANIFEST_PATH, RAW_DATA_DIR, TRUSTED_EVAL_REPORT, TRUSTED_EVAL_SUMMARY_REPORT
from .db import database_status, import_processed_jsonl, import_source_catalog_to_db
from .eval_excel import evaluate_excel
from .eval_retrieval import evaluate_retrieval
from .eval_text import TEXT_EVAL_REPORT, evaluate_text
from .eval_trusted import evaluate_trusted, evaluate_trusted_by_type, write_trusted_summary_report
from .knowledge_base import build_knowledge_base
from .manifest import build_manifest
from .metadata_extractor import build_document_metadata
from .metadata_quality import build_metadata_quality_report
from .retrieval_eval_builder import build_retrieval_eval_set
from .services import kb_status, list_documents, run_eval, search_evidence
from .source_catalog import enrich_manifest_from_source_catalog, export_source_catalog_template, validate_source_catalog
from .source_worklist import build_source_gap_worklist
from .structure_parser import build_text_units
from .table_semantics import enhance_table_rows
from .vector_index import build_vector_index
from .version_audit import build_version_audit_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="jinrong", description="Trusted RAG MVP commands.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("build-manifest", help="Scan wendang/data and build processed manifest.")
    sub.add_parser("build-metadata", help="Extract document metadata such as publisher, doc_no, dates, and domains.")
    metadata_audit_parser = sub.add_parser("metadata-audit", help="Build metadata coverage and missing-field audit report.")
    metadata_audit_parser.add_argument("--no-store-db", action="store_true", help="Do not store the audit report in SQLite.")
    version_audit_parser = sub.add_parser("version-audit", help="Build source/version traceability audit report.")
    version_audit_parser.add_argument("--no-store-db", action="store_true", help="Do not store the audit report in SQLite.")
    sub.add_parser("build-text-units", help="Build page/section/article level text units from text chunks.")
    sub.add_parser("enhance-table-rows", help="Add indicator, period, header, and cell structure fields to table rows.")
    sub.add_parser("build-vector-index", help="Build local hashed embedding indexes for hybrid retrieval.")
    import_db_parser = sub.add_parser("import-db", help="Import processed JSONL knowledge base into SQLite.")
    import_db_parser.add_argument("--reset", action="store_true", help="Clear imported SQLite tables before importing.")
    sub.add_parser("db-status", help="Show SQLite production database status.")
    source_template_parser = sub.add_parser("export-source-template", help="Export a CSV template for source URL enrichment.")
    source_template_parser.add_argument("--output", help="Output CSV path.")
    source_worklist_parser = sub.add_parser("source-gap-worklist", help="Build a prioritized source/version enrichment worklist.")
    source_worklist_parser.add_argument("--output", help="Output CSV path.")
    source_worklist_parser.add_argument("--limit", type=int, help="Export only the top N rows.")
    validate_source_parser = sub.add_parser("validate-source-catalog", help="Validate a source URL catalog before merging.")
    validate_source_parser.add_argument("--source-catalog", required=True, help="CSV/JSONL/JSON catalog to validate.")
    import_source_parser = sub.add_parser("import-source-catalog", help="Validate and store a source URL catalog in SQLite.")
    import_source_parser.add_argument("--source-catalog", required=True, help="CSV/JSONL/JSON catalog to import.")
    import_source_parser.add_argument("--reset-catalog", action="store_true", help="Clear previous entries for the same catalog path.")
    enrich_parser = sub.add_parser("enrich-manifest", help="Merge source URL catalog into manifest_enriched.jsonl.")
    enrich_parser.add_argument("--source-catalog", required=True, help="CSV/JSONL/JSON catalog with source_url and attachment_url.")
    enrich_parser.add_argument("--output", help="Output enriched manifest JSONL path.")
    kb_parser = sub.add_parser("build-kb", help="Build processed text chunks and table cells for RAG search.")
    kb_parser.add_argument("--qa-only", action="store_true", help="Build only files referenced by QA数据.xlsx.")
    kb_parser.add_argument("--resume", action="store_true", help="Skip files already marked successful in kb_build_state.jsonl.")
    kb_parser.add_argument("--retry-failed", action="store_true", help="Rebuild only files marked failed in kb_build_state.jsonl.")
    kb_parser.add_argument("--limit", type=int, help="Process at most N manifest records, useful for smoke tests.")
    sub.add_parser("eval-excel", help="Run deterministic Excel QA evaluation.")
    sub.add_parser("eval-text", help="Run deterministic Word/PDF MCQ evaluation.")
    sub.add_parser("eval-all", help="Run Excel and Word/PDF evaluations.")
    retrieval_eval_parser = sub.add_parser("eval-retrieval", help="Run evidence retrieval evaluation.")
    retrieval_eval_parser.add_argument("--retrieval", choices=["bm25", "hybrid"], default="hybrid")
    retrieval_eval_parser.add_argument("--rerank", action="store_true")
    retrieval_eval_parser.add_argument("--top-k", type=int, default=5)
    trusted_eval_parser = sub.add_parser("eval-trusted", help="Run trusted QA evaluation across factual, table, refusal, compliance, and multi-hop cases.")
    trusted_eval_parser.add_argument("--eval-path", help="Trusted eval JSONL path.")
    trusted_eval_parser.add_argument("--report", help="Output report JSON path.")
    trusted_eval_parser.add_argument("--limit", type=int, help="Evaluate only the first N trusted cases.")
    trusted_eval_parser.add_argument("--case-type", help="Evaluate one trusted case type, or all for grouped reports.")
    trusted_summary_parser = sub.add_parser("eval-trusted-summary", help="Build a summary report from trusted eval type reports.")
    trusted_summary_parser.add_argument("--report", help="Output summary report JSON path.")
    build_retrieval_eval_parser = sub.add_parser("build-retrieval-eval", help="Build a validated evidence retrieval eval set.")
    build_retrieval_eval_parser.add_argument("--target-size", type=int, default=60)
    build_retrieval_eval_parser.add_argument("--retrieval", choices=["bm25", "hybrid"], default="hybrid")
    build_retrieval_eval_parser.add_argument("--rerank", action="store_true")
    ask_parser = sub.add_parser("ask", help="Ask a question or replay one QA id.")
    ask_parser.add_argument("--qa-id", help="QA id such as Q001.")
    ask_parser.add_argument("--question", help="Question text.")
    ask_parser.add_argument("--options-json", help='Optional MCQ options JSON, e.g. {"A":"...","B":"..."}')
    serve_parser = sub.add_parser("serve", help="Run a lightweight HTTP API.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)
    search_parser = sub.add_parser("search", help="Search evidence.")
    search_parser.add_argument("query")
    search_parser.add_argument("--source-type", choices=["excel", "word", "pdf"])
    search_parser.add_argument("--doc-id")
    search_parser.add_argument("--publisher")
    search_parser.add_argument("--publish-date-from")
    search_parser.add_argument("--publish-date-to")
    search_parser.add_argument("--business-domain")
    search_parser.add_argument("--regulatory-topic")
    search_parser.add_argument("--doc-no")
    search_parser.add_argument("--column")
    search_parser.add_argument("--source-site")
    search_parser.add_argument("--version-status")
    search_parser.add_argument("--effective-date-from")
    search_parser.add_argument("--effective-date-to")
    search_parser.add_argument("--version-group")
    search_parser.add_argument("--has-version-relation", action="store_true")
    search_parser.add_argument("--indicator")
    search_parser.add_argument("--period")
    search_parser.add_argument("--has-source-url", action="store_true")
    search_parser.add_argument("--article-no")
    search_parser.add_argument("--retrieval", choices=["bm25", "hybrid"], default="bm25")
    search_parser.add_argument("--rerank", action="store_true")
    search_parser.add_argument("--no-prefer-current", action="store_true", help="Disable current-version score boost.")
    search_parser.add_argument("--exclude-superseded", action="store_true", help="Filter out superseded evidence.")
    search_parser.add_argument("--top-k", type=int, default=5)
    docs_parser = sub.add_parser("documents", help="List documents.")
    docs_parser.add_argument("--source-type", choices=["excel", "word", "pdf"])
    docs_parser.add_argument("--file-ext")
    docs_parser.add_argument("--query")
    docs_parser.add_argument("--publisher")
    docs_parser.add_argument("--publish-date-from")
    docs_parser.add_argument("--publish-date-to")
    docs_parser.add_argument("--business-domain")
    docs_parser.add_argument("--regulatory-topic")
    docs_parser.add_argument("--doc-no")
    docs_parser.add_argument("--column")
    docs_parser.add_argument("--source-site")
    docs_parser.add_argument("--version-status")
    docs_parser.add_argument("--effective-date-from")
    docs_parser.add_argument("--effective-date-to")
    docs_parser.add_argument("--version-group")
    docs_parser.add_argument("--has-version-relation", action="store_true")
    docs_parser.add_argument("--has-source-url", action="store_true")
    docs_parser.add_argument("--article-no")
    docs_parser.add_argument("--limit", type=int, default=10)
    docs_parser.add_argument("--offset", type=int, default=0)
    sub.add_parser("kb-status", help="Show processed RAG knowledge base status.")

    args = parser.parse_args()
    if args.command == "build-manifest":
        records = build_manifest(RAW_DATA_DIR, MANIFEST_PATH)
        print(json.dumps({"manifest": str(MANIFEST_PATH), "count": len(records)}, ensure_ascii=False, indent=2))
    elif args.command == "export-source-template":
        output_path = Path(args.output) if args.output else None
        payload = export_source_catalog_template(output_path=output_path) if output_path else export_source_catalog_template()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "source-gap-worklist":
        output_path = Path(args.output) if args.output else None
        payload = (
            build_source_gap_worklist(output_path=output_path, limit=args.limit)
            if output_path
            else build_source_gap_worklist(limit=args.limit)
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "validate-source-catalog":
        print(json.dumps(validate_source_catalog(Path(args.source_catalog)), ensure_ascii=False, indent=2))
    elif args.command == "import-source-catalog":
        print(
            json.dumps(
                import_source_catalog_to_db(Path(args.source_catalog), reset_catalog=args.reset_catalog),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "enrich-manifest":
        output_path = Path(args.output) if args.output else None
        payload = (
            enrich_manifest_from_source_catalog(Path(args.source_catalog), output_path=output_path)
            if output_path
            else enrich_manifest_from_source_catalog(Path(args.source_catalog))
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "build-metadata":
        print(json.dumps(build_document_metadata(), ensure_ascii=False, indent=2))
    elif args.command == "metadata-audit":
        print(json.dumps(build_metadata_quality_report(store_db=not args.no_store_db), ensure_ascii=False, indent=2))
    elif args.command == "version-audit":
        print(json.dumps(build_version_audit_report(store_db=not args.no_store_db), ensure_ascii=False, indent=2))
    elif args.command == "build-text-units":
        print(json.dumps(build_text_units(), ensure_ascii=False, indent=2))
    elif args.command == "enhance-table-rows":
        print(json.dumps(enhance_table_rows(), ensure_ascii=False, indent=2))
    elif args.command == "build-vector-index":
        print(json.dumps(build_vector_index(), ensure_ascii=False, indent=2))
    elif args.command == "import-db":
        print(json.dumps(import_processed_jsonl(reset=args.reset), ensure_ascii=False, indent=2))
    elif args.command == "db-status":
        print(json.dumps(database_status(), ensure_ascii=False, indent=2))
    elif args.command == "build-kb":
        print(
            json.dumps(
                build_knowledge_base(
                    qa_only=args.qa_only,
                    resume=args.resume,
                    retry_failed=args.retry_failed,
                    limit=args.limit,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "eval-excel":
        payload = evaluate_excel()
        print(json.dumps({"report": str(EXCEL_EVAL_REPORT), **payload["summary"]}, ensure_ascii=False, indent=2))
    elif args.command == "eval-text":
        payload = evaluate_text()
        print(json.dumps({"report": str(TEXT_EVAL_REPORT), **payload["summary"]}, ensure_ascii=False, indent=2))
    elif args.command == "eval-all":
        excel = evaluate_excel()
        text = evaluate_text()
        total = excel["summary"]["total"] + text["summary"]["total"]
        correct = excel["summary"]["correct"] + text["summary"]["correct"]
        payload = {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total else 0,
            "excel_report": str(EXCEL_EVAL_REPORT),
            "text_report": str(TEXT_EVAL_REPORT),
            "excel": excel["summary"],
            "text": text["summary"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "eval-retrieval":
        print(
            json.dumps(
                evaluate_retrieval(retrieval=args.retrieval, rerank=args.rerank, top_k=args.top_k),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "eval-trusted":
        eval_path = Path(args.eval_path) if args.eval_path else None
        report_path = Path(args.report) if args.report else TRUSTED_EVAL_REPORT
        if args.case_type == "all":
            payload = evaluate_trusted_by_type(eval_path=eval_path) if eval_path else evaluate_trusted_by_type()
        else:
            payload = (
                evaluate_trusted(eval_path=eval_path, report_path=report_path, limit=args.limit, case_type=args.case_type)
                if eval_path
                else evaluate_trusted(report_path=report_path, limit=args.limit, case_type=args.case_type)
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "eval-trusted-summary":
        report_path = Path(args.report) if args.report else TRUSTED_EVAL_SUMMARY_REPORT
        payload = write_trusted_summary_report(report_path=report_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "build-retrieval-eval":
        print(
            json.dumps(
                build_retrieval_eval_set(target_size=args.target_size, retrieval=args.retrieval, rerank=args.rerank),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "ask":
        options = json.loads(args.options_json) if args.options_json else None
        response = ask(question=args.question, options=options, qa_id=args.qa_id)
        print(response.to_json())
    elif args.command == "serve":
        try:
            from .api.app import run_server
        except ImportError:
            from .api_server import run_server

        run_server(args.host, args.port)
    elif args.command == "search":
        print(
            json.dumps(
                search_evidence(
                    args.query,
                    source_type=args.source_type,
                    doc_id=args.doc_id,
                    publisher=args.publisher,
                    publish_date_from=args.publish_date_from,
                    publish_date_to=args.publish_date_to,
                    business_domain=args.business_domain,
                    regulatory_topic=args.regulatory_topic,
                    doc_no=args.doc_no,
                    column=args.column,
                    source_site=args.source_site,
                    version_status=args.version_status,
                    effective_date_from=args.effective_date_from,
                    effective_date_to=args.effective_date_to,
                    version_group=args.version_group,
                    has_version_relation=True if args.has_version_relation else None,
                    indicator=args.indicator,
                    period=args.period,
                    has_source_url=True if args.has_source_url else None,
                    article_no=args.article_no,
                    retrieval=args.retrieval,
                    rerank=args.rerank,
                    prefer_current=not args.no_prefer_current,
                    include_superseded=not args.exclude_superseded,
                    top_k=args.top_k,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "documents":
        print(
            json.dumps(
                list_documents(
                    source_type=args.source_type,
                    file_ext=args.file_ext,
                    query=args.query,
                    publisher=args.publisher,
                    publish_date_from=args.publish_date_from,
                    publish_date_to=args.publish_date_to,
                    business_domain=args.business_domain,
                    regulatory_topic=args.regulatory_topic,
                    doc_no=args.doc_no,
                    column=args.column,
                    source_site=args.source_site,
                    version_status=args.version_status,
                    effective_date_from=args.effective_date_from,
                    effective_date_to=args.effective_date_to,
                    version_group=args.version_group,
                    has_version_relation=True if args.has_version_relation else None,
                    has_source_url=True if args.has_source_url else None,
                    article_no=args.article_no,
                    limit=args.limit,
                    offset=args.offset,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "kb-status":
        print(json.dumps(kb_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
