import json

from fastapi.testclient import TestClient

from jinrong.api import routes
from jinrong.api.app import create_app


class _AskResponse:
    def to_json(self) -> str:
        return json.dumps({"answer": "ok", "evidence": []})


def test_api_smoke(monkeypatch) -> None:
    monkeypatch.setattr(routes, "ask", lambda **kwargs: _AskResponse())
    monkeypatch.setattr(
        routes,
        "search_evidence",
        lambda **kwargs: {"query": kwargs["query"], "total": 0, "top_k": kwargs["top_k"], "results": []},
    )
    monkeypatch.setattr(
        routes,
        "list_documents",
        lambda **kwargs: {"total": 0, "limit": kwargs["limit"], "offset": kwargs["offset"], "documents": []},
    )
    monkeypatch.setattr(routes, "kb_status", lambda: {"available": False})
    monkeypatch.setattr(
        routes,
        "load_trusted_report",
        lambda case_type: {"available": False, "case_type": case_type},
    )
    monkeypatch.setattr(routes, "load_acceptance_report", lambda: {"available": False, "final_passed": False})
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/ask", json={"question": "smoke"}).status_code == 200
    assert client.post("/search", json={"query": "smoke"}).json()["results"] == []
    assert client.get("/documents").json()["documents"] == []
    assert client.get("/kb/status").json() == {"available": False}
    assert client.get("/eval/trusted/summary").json() == {"available": False, "case_type": "summary"}
    assert client.get("/eval/trusted/open_fact").json()["available"] is False
    assert client.get("/eval/acceptance").json() == {"available": False, "final_passed": False}


def test_api_validation_contract() -> None:
    client = TestClient(create_app())
    assert client.post("/search", json={"query": "", "top_k": 51}).status_code == 422
