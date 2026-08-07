# API Contracts

JSON is UTF-8. Successful responses are JSON objects. Validation failures use FastAPI's standard HTTP 422 response; missing documents use HTTP 404. Internal or dependency failures use the framework's 500 response and must not be represented as a successful empty result.

## Endpoints

| Method/path | Request | Success response |
| --- | --- | --- |
| GET `/health` | none | `{status: "ok"}` |
| POST `/ask` | `AskRequest` | `question`, `answer`, `answer_text`, `evidence`, `confidence`, `route`, optional `debug` |
| POST `/search` | `SearchRequest` | `query`, `total`, `top_k`, `results` |
| GET `/documents` | documented query filters plus `limit`/`offset` | `total`, `limit`, `offset`, `documents` |
| GET `/documents/{doc_id}` | path ID | one manifest/metadata object or 404 |
| GET `/kb/status` | none | `available` plus build counts/paths when available |
| POST `/eval` | `EvalRequest` | evaluation summary for `all`, `excel`, or `text` |
| GET `/eval/trusted/summary` | none | `{available, case_type: "summary", ...}` |
| GET `/eval/trusted/{case_type}` | trusted case type | `{available, case_type, ...}`; absent report returns `available: false` |
| GET `/eval/acceptance` | none | final holdout report with `available`, `final_passed`, freshness, five metrics, and latency; absent report returns `available: false` |

## Request models

`AskRequest`: optional `qa_id`, optional `question`, optional string map `options`; the service requires at least one of `qa_id` or `question` and returns a normal error when neither is supplied.

`SearchRequest`: required non-empty `query`; `source_type` is `excel|word|pdf`; `retrieval` is `bm25|hybrid`; `rerank`, version/source/date filters are optional; `top_k` is 1..50 and defaults to 5.

`EvalRequest`: `scope` is `all|excel|text`, default `all`.

## Answer semantics

`route` identifies the selected workflow. A refusal has a refusal route, low confidence, no fabricated evidence, and a refusal answer. `answer` and `answer_text` may be `null` when no answer is established. Evidence is always a list; an empty list is meaningful and is not an implicit success claim.
