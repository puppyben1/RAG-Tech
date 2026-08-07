# Source and Version Trust Policy

This is the P0-C policy for authority claims. It governs answer wording and evidence eligibility; it does not invent metadata.

## Version states

`current` is confirmed applicable, `superseded` is confirmed replaced, `unknown` is not verified, and `not_applicable` is reserved for point-in-time statistical snapshots with an explicit period. Any other input is normalized to `unknown` and reported as invalid by audit.

An evidence item is authoritative only when it has `source_url` or `attachment_url` and its state is `current` or `not_applicable`. `superseded` may be returned for historical comparison but is excluded from authoritative answers by default. `unknown` may support exploratory search but must cause refusal or an explicit non-authoritative downgrade.

Version relations must point to existing `doc_id` values, cannot self-reference, and a version group may have at most one `current` item. Conflicts are audit failures.

## Missing source data

Empty source fields remain `null`; placeholder URLs are forbidden. Until an authorized proof record confirms a URL and version state, the document remains non-authoritative. Proof may be an official attachment hash match, an official page metadata match, an organizer authorization, a reproducible download log, or manual review. Manual proof must retain reviewer and review timestamp; every enrichment decision must retain its evidence and verification method.

## Current enforcement

Open RAG answers evaluate the returned evidence with this policy. If no evidence is authoritative, the response uses the existing refusal route and does not claim a confirmed regulatory answer. `/search` remains available for discovery and exposes version/source metadata when present.
