from pydantic import ValidationError
import pytest

from jinrong.api.schemas import AskRequest, EvalRequest, SearchRequest


def test_search_request_defaults_and_bounds() -> None:
    payload = SearchRequest(query="capital", source_type="excel")
    assert payload.retrieval == "bm25"
    assert payload.top_k == 5
    with pytest.raises(ValidationError):
        SearchRequest(query="")
    with pytest.raises(ValidationError):
        SearchRequest(query="x", top_k=51)


def test_request_enums_are_closed() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="x", retrieval="semantic")
    with pytest.raises(ValidationError):
        EvalRequest(scope="trusted")


def test_ask_request_preserves_nullable_fields() -> None:
    request = AskRequest()
    assert request.qa_id is None
    assert request.question is None
    assert request.options is None

