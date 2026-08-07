# CR-20260806: Source Review Workflow

Status: Verified  
Priority: P0-C  
Created: 2026-08-06

## Goal

Turn the source gap worklist into an auditable human-review workflow without guessing metadata.

## Changes

- Added source/version evidence, reviewer, and review timestamp fields to catalog and worklist schemas.
- Added `not_applicable` for period-based statistical snapshots.
- Rejected placeholder or malformed URLs.
- Required provenance for any authority claim.
- Blocked manifest enrichment, SQLite import, and CLI validation success when catalog validation fails.

## Non-goals

This change does not populate the 500 records, crawl websites, or assert that existing source metadata is correct.

## Verification

Focused tests cover invalid placeholders, missing provenance, valid reviewed snapshots, and enrichment rejection. The full test suite is the acceptance command.

