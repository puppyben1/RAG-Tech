from __future__ import annotations

import argparse
import json
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .ask import ask
from .eval_acceptance import load_acceptance_report
from .eval_trusted import load_trusted_report
from .services import get_document, kb_status, list_documents, openapi_spec, run_eval, search_evidence


class AskHandler(BaseHTTPRequestHandler):
    server_version = "JinrongTrustedRAG/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/openapi.json":
            self._send_json(openapi_spec())
            return
        if parsed.path == "/kb/status":
            self._send_json(kb_status())
            return
        if parsed.path == "/eval/trusted/summary":
            self._send_json(load_trusted_report("summary"))
            return
        if parsed.path == "/eval/acceptance":
            self._send_json(load_acceptance_report())
            return
        if parsed.path.startswith("/eval/trusted/"):
            case_type = parsed.path.rsplit("/", 1)[-1]
            self._send_json(load_trusted_report(case_type))
            return
        if parsed.path == "/documents":
            params = parse_qs(parsed.query)
            self._send_json(
                list_documents(
                    source_type=_first(params, "source_type"),
                    file_ext=_first(params, "file_ext"),
                    query=_first(params, "query"),
                    publisher=_first(params, "publisher"),
                    publish_date_from=_first(params, "publish_date_from"),
                    publish_date_to=_first(params, "publish_date_to"),
                    business_domain=_first(params, "business_domain"),
                    regulatory_topic=_first(params, "regulatory_topic"),
                    doc_no=_first(params, "doc_no"),
                    column=_first(params, "column"),
                    source_site=_first(params, "source_site"),
                    version_status=_first(params, "version_status"),
                    effective_date_from=_first(params, "effective_date_from"),
                    effective_date_to=_first(params, "effective_date_to"),
                    version_group=_first(params, "version_group"),
                    has_version_relation=_optional_bool(_first(params, "has_version_relation")),
                    has_source_url=_optional_bool(_first(params, "has_source_url")),
                    article_no=_first(params, "article_no"),
                    limit=int(_first(params, "limit") or 50),
                    offset=int(_first(params, "offset") or 0),
                )
            )
            return
        if parsed.path.startswith("/documents/"):
            doc_id = parsed.path.rsplit("/", 1)[-1]
            doc = get_document(doc_id)
            self._send_json(doc if doc else {"error": "document not found"}, status=200 if doc else 404)
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/ask", "/search", "/eval"}:
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
            if parsed.path == "/ask":
                response = ask(
                    question=payload.get("question"),
                    options=payload.get("options"),
                    qa_id=payload.get("qa_id"),
                )
                self._send_json(json.loads(response.to_json()))
                return
            if parsed.path == "/search":
                self._send_json(
                    search_evidence(
                        query=payload["query"],
                        source_type=payload.get("source_type"),
                        doc_id=payload.get("doc_id"),
                        publisher=payload.get("publisher"),
                        publish_date_from=payload.get("publish_date_from"),
                        publish_date_to=payload.get("publish_date_to"),
                        business_domain=payload.get("business_domain"),
                        regulatory_topic=payload.get("regulatory_topic"),
                        doc_no=payload.get("doc_no"),
                        column=payload.get("column"),
                        source_site=payload.get("source_site"),
                        version_status=payload.get("version_status"),
                        effective_date_from=payload.get("effective_date_from"),
                        effective_date_to=payload.get("effective_date_to"),
                        version_group=payload.get("version_group"),
                        has_version_relation=payload.get("has_version_relation"),
                        indicator=payload.get("indicator"),
                        period=payload.get("period"),
                        has_source_url=payload.get("has_source_url"),
                        article_no=payload.get("article_no"),
                        retrieval=payload.get("retrieval", "bm25"),
                        rerank=bool(payload.get("rerank", False)),
                        prefer_current=_payload_bool(payload.get("prefer_current"), default=True),
                        include_superseded=_payload_bool(payload.get("include_superseded"), default=True),
                        top_k=int(payload.get("top_k", 5)),
                    )
                )
                return
            if parsed.path == "/eval":
                self._send_json(run_eval(scope=payload.get("scope", "all")))
                return
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AskHandler)
    print(f"Serving Jinrong Trusted RAG API at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Trusted RAG HTTP API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    run_server(args.host, args.port)


def _first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    return values[0] if values else None


def _optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in {"1", "true", "yes", "y"}


def _payload_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return bool(value)


if __name__ == "__main__":
    main()
