from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import TABLE_CELLS_PATH, TABLE_ROWS_PATH, TABLE_SEMANTICS_REPORT
from .path_refs import to_project_ref
from .utils import ensure_dir, norm_text, read_jsonl, write_jsonl


def enhance_table_rows(
    table_rows_path: Path = TABLE_ROWS_PATH,
    table_cells_path: Path = TABLE_CELLS_PATH,
    output_path: Path = TABLE_ROWS_PATH,
    report_path: Path = TABLE_SEMANTICS_REPORT,
) -> dict[str, Any]:
    rows = read_jsonl(table_rows_path)
    cells = read_jsonl(table_cells_path)
    cell_index = _group_cells(cells)
    enhanced: list[dict[str, Any]] = []
    rows_with_cells = 0
    rows_with_periods = 0
    rows_with_headers = 0
    rows_with_indicator = 0

    for row in rows:
        group = cell_index.get(_row_key(row), [])
        enriched = dict(row)
        indicator = _infer_indicator(row)
        headers = _headers(group)
        periods = _periods(group)
        structured_cells = _structured_cells(group)
        if indicator:
            enriched["indicator"] = indicator
            rows_with_indicator += 1
        if headers:
            enriched["headers"] = headers
            rows_with_headers += 1
        if periods:
            enriched["periods"] = periods
            rows_with_periods += 1
        if structured_cells:
            enriched["cells"] = structured_cells
            rows_with_cells += 1
        enriched["semantic_text"] = _semantic_text(enriched)
        enhanced.append(enriched)

    write_jsonl(output_path, enhanced)
    report = {
        "table_rows_path": to_project_ref(output_path),
        "table_cells_path": to_project_ref(table_cells_path),
        "table_rows": len(enhanced),
        "rows_with_indicator": rows_with_indicator,
        "rows_with_headers": rows_with_headers,
        "rows_with_periods": rows_with_periods,
        "rows_with_cells": rows_with_cells,
        "indicator_coverage": rows_with_indicator / len(enhanced) if enhanced else 0,
        "headers_coverage": rows_with_headers / len(enhanced) if enhanced else 0,
        "periods_coverage": rows_with_periods / len(enhanced) if enhanced else 0,
        "cells_coverage": rows_with_cells / len(enhanced) if enhanced else 0,
    }
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _group_cells(cells: list[dict[str, Any]]) -> dict[tuple[str, str, int, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, int, str], list[dict[str, Any]]] = {}
    for cell in cells:
        key = (
            str(cell.get("doc_id") or ""),
            str(cell.get("sheet_name") or ""),
            int(cell.get("row_index") or 0),
            str(cell.get("row_header") or ""),
        )
        grouped.setdefault(key, []).append(cell)
    for group in grouped.values():
        group.sort(key=lambda item: int(item.get("col_index") or 0))
    return grouped


def _row_key(row: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(row.get("doc_id") or ""),
        str(row.get("sheet_name") or ""),
        int(row.get("row_index") or 0),
        str(row.get("row_header") or ""),
    )


def _infer_indicator(row: dict[str, Any]) -> str | None:
    row_header = str(row.get("row_header") or "").strip()
    if row_header and not norm_text(row_header).startswith("注"):
        return row_header
    return None


def _headers(cells: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for cell in cells:
        header = str(cell.get("col_header") or "").strip()
        if header and header not in seen:
            seen.add(header)
            values.append(header)
    return values


def _periods(cells: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for cell in cells:
        header = str(cell.get("col_header") or "").strip()
        period = _period_from_header(header)
        if period and period not in seen:
            seen.add(period)
            values.append(period)
    return values


def _structured_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    structured: list[dict[str, Any]] = []
    for cell in cells:
        header = str(cell.get("col_header") or "").strip()
        structured.append(
            {
                "cell_ref": cell.get("cell_ref"),
                "col_index": cell.get("col_index"),
                "header": header,
                "period": _period_from_header(header),
                "value": cell.get("value_raw"),
                "value_num": cell.get("value_num"),
            }
        )
    return structured


def _period_from_header(header: str) -> str | None:
    if not header:
        return None
    month_match = re.search(r"(20\d{2}年\s*\d{1,2}月)", header)
    if month_match:
        return month_match.group(1).replace(" ", "")
    quarter_match = re.search(r"(20\d{2}年\s*(?:[一二三四1-4]季度|[1-4]季度|[一二三四]季))", header)
    if quarter_match:
        return quarter_match.group(1).replace(" ", "")
    year_match = re.search(r"(20\d{2}年)", header)
    if year_match:
        return year_match.group(1)
    for sep in ("-", "－", "—", "_"):
        if sep in header:
            left = header.split(sep, 1)[0].strip()
            if left:
                return left
    return header


def _semantic_text(row: dict[str, Any]) -> str:
    pieces = [
        str(row.get("source_title") or ""),
        str(row.get("sheet_name") or ""),
        str(row.get("indicator") or row.get("row_header") or ""),
        " ".join(str(item) for item in row.get("periods") or []),
        str(row.get("unit") or ""),
    ]
    return " ".join(piece for piece in pieces if piece).strip()
