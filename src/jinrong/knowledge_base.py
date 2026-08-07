from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from .config import (
    INTERMEDIATE_DIR,
    KB_BUILD_ERRORS_PATH,
    KB_BUILD_STATE_PATH,
    KB_STATS_PATH,
    MANIFEST_PATH,
    TABLE_CELLS_PATH,
    TABLE_ROWS_PATH,
    TEXT_CHUNKS_PATH,
)
from .excel_parser import parse_excel
from .manifest import build_manifest
from .path_refs import resolve_project_ref, to_project_ref
from .qa_data import load_qa
from .text_parser import extract_text, split_sentences
from .utils import append_jsonl, ensure_dir, norm_text, read_jsonl


def build_knowledge_base(
    manifest_path: Path = MANIFEST_PATH,
    chunks_path: Path = TEXT_CHUNKS_PATH,
    cells_path: Path = TABLE_CELLS_PATH,
    table_rows_path: Path = TABLE_ROWS_PATH,
    stats_path: Path = KB_STATS_PATH,
    qa_only: bool = False,
    resume: bool = False,
    retry_failed: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    if not manifest_path.exists():
        build_manifest()
    manifest = read_jsonl(manifest_path)
    if qa_only:
        manifest = _filter_manifest_to_qa_files(manifest)
    if retry_failed:
        manifest = _filter_manifest_to_failed_files(manifest)
    if limit is not None:
        manifest = manifest[:limit]

    if not resume:
        _reset_outputs(chunks_path, cells_path, table_rows_path, KB_BUILD_STATE_PATH, KB_BUILD_ERRORS_PATH)

    completed = _load_completed_state(KB_BUILD_STATE_PATH) if resume else set()
    run_errors: list[dict[str, Any]] = []
    processed = 0
    skipped = 0
    for record in manifest:
        state_key = _state_key(record)
        if state_key in completed:
            skipped += 1
            continue
        path = resolve_project_ref(record["local_path"])
        if not path.exists():
            error = _error_record(record, "load_file", FileNotFoundError("file not found"))
            run_errors.append(error)
            append_jsonl(KB_BUILD_STATE_PATH, _state_record(record, "failed", error=error))
            continue
        try:
            text_count = 0
            cell_count = 0
            warning: str | None = None
            if record["source_type"] in {"word", "pdf"}:
                resolved_path, warning = _resolve_text_input(path)
                text_count = _write_rows(chunks_path, _build_text_chunks(record, resolved_path))
            elif record["source_type"] == "excel":
                resolved_path = _resolve_excel_input(path)
                cell_rows = _build_table_cells(record, resolved_path)
                cell_count = _write_rows(cells_path, cell_rows)
                _write_rows(table_rows_path, _build_table_rows(record, cell_rows))
            else:
                warning = f"unsupported source_type: {record['source_type']}"
            status = "success_with_warning" if warning else "success"
            append_jsonl(
                KB_BUILD_STATE_PATH,
                _state_record(record, status, text_chunks=text_count, table_cells=cell_count, warning=warning),
            )
            processed += 1
        except Exception as exc:
            error = _error_record(record, "parse", exc)
            run_errors.append(error)
            append_jsonl(KB_BUILD_STATE_PATH, _state_record(record, "failed", error=error))

    all_errors = _collect_errors(KB_BUILD_STATE_PATH)
    ensure_dir(KB_BUILD_ERRORS_PATH.parent)
    KB_BUILD_ERRORS_PATH.write_text(json.dumps(all_errors, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = {
        "documents": len(manifest),
        "processed_documents": processed,
        "skipped_documents": skipped,
        "text_chunks": _count_jsonl(chunks_path),
        "table_cells": _count_jsonl(cells_path),
        "table_rows": _count_jsonl(table_rows_path),
        "errors": all_errors[:100],
        "error_count": len(all_errors),
        "chunks_path": to_project_ref(chunks_path),
        "cells_path": to_project_ref(cells_path),
        "table_rows_path": to_project_ref(table_rows_path),
        "state_path": to_project_ref(KB_BUILD_STATE_PATH),
        "errors_path": to_project_ref(KB_BUILD_ERRORS_PATH),
        "qa_only": qa_only,
        "resume": resume,
        "retry_failed": retry_failed,
    }
    ensure_dir(stats_path.parent)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def _filter_manifest_to_qa_files(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qa_items = load_qa()
    labels = {Path(item.file_label).stem for item in qa_items}
    selected: list[dict[str, Any]] = []
    for record in manifest:
        stem = Path(record["file_name"]).stem
        if any(label and label in stem for label in labels):
            selected.append(record)
    return selected


def _filter_manifest_to_failed_files(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not KB_BUILD_STATE_PATH.exists():
        return []
    failed_doc_ids = {
        row.get("doc_id")
        for row in read_jsonl(KB_BUILD_STATE_PATH)
        if row.get("status") == "failed" and row.get("doc_id")
    }
    return [record for record in manifest if record["doc_id"] in failed_doc_ids]


def _reset_outputs(*paths: Path) -> None:
    for path in paths:
        ensure_dir(path.parent)
        path.write_text("", encoding="utf-8")


def _load_completed_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for row in read_jsonl(path):
        if row.get("status") in {"success", "success_with_warning"}:
            completed.add(f"{row.get('doc_id')}:{row.get('sha256')}")
    return completed


def _state_key(record: dict[str, Any]) -> str:
    return f"{record.get('doc_id')}:{record.get('sha256')}"


def _state_record(
    record: dict[str, Any],
    status: str,
    text_chunks: int = 0,
    table_cells: int = 0,
    warning: str | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "doc_id": record["doc_id"],
        "sha256": record.get("sha256"),
        "file_name": record.get("file_name"),
        "file_ext": record.get("file_ext"),
        "source_type": record.get("source_type"),
        "status": status,
        "text_chunks": text_chunks,
        "table_cells": table_cells,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if warning:
        row["warning"] = warning
    if error:
        row["error"] = error
    return row


def _error_record(record: dict[str, Any], stage: str, exc: Exception) -> dict[str, Any]:
    return {
        "doc_id": record.get("doc_id"),
        "file_name": record.get("file_name"),
        "file_ext": record.get("file_ext"),
        "source_type": record.get("source_type"),
        "stage": stage,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "retryable": True,
    }


def _collect_errors(state_path: Path) -> list[dict[str, Any]]:
    if not state_path.exists():
        return []
    errors: list[dict[str, Any]] = []
    for row in read_jsonl(state_path):
        error = row.get("error")
        if row.get("status") == "failed" and isinstance(error, dict):
            errors.append(error)
    return errors


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        append_jsonl(path, row)
    return len(rows)


def _resolve_text_input(path: Path) -> tuple[Path, str | None]:
    if path.suffix.lower() != ".doc":
        return path, None
    converted = _convert_with_libreoffice(path, "docx")
    if converted:
        return converted, None
    return path, "LibreOffice not available; used binary .doc fallback extraction"


def _resolve_excel_input(path: Path) -> Path:
    if path.suffix.lower() == ".xlsx":
        return path
    if path.suffix.lower() == ".xls":
        converted = _convert_with_libreoffice(path, "xlsx")
        if converted:
            return converted
        return path
    raise RuntimeError(f"unsupported excel extension: {path.suffix}")


def _convert_with_libreoffice(path: Path, target_ext: str) -> Path | None:
    profile = os.getenv("JINRONG_PARSER_PROFILE", "portable").strip().lower()
    if profile == "portable":
        return None
    if profile != "libreoffice":
        raise RuntimeError(f"unsupported parser profile: {profile}")
    executable = os.getenv("JINRONG_LIBREOFFICE_EXECUTABLE", "").strip()
    expected_version = os.getenv("JINRONG_LIBREOFFICE_VERSION", "").strip()
    if not executable or not expected_version:
        raise RuntimeError(
            "libreoffice profile requires JINRONG_LIBREOFFICE_EXECUTABLE and JINRONG_LIBREOFFICE_VERSION"
        )
    soffice = Path(executable)
    if not soffice.is_file():
        raise RuntimeError(f"configured LibreOffice executable not found: {executable}")
    version = subprocess.run(
        [str(soffice), "--version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if expected_version not in version:
        raise RuntimeError(f"LibreOffice version mismatch: expected {expected_version}, got {version}")
    output_dir = INTERMEDIATE_DIR / "converted" / target_ext
    ensure_dir(output_dir)
    subprocess.run(
        [
            str(soffice),
            "--headless",
            "--convert-to",
            target_ext,
            "--outdir",
            str(output_dir),
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    converted = output_dir / f"{path.stem}.{target_ext}"
    return converted if converted.exists() else None


def _build_text_chunks(record: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    text = extract_text(str(path.resolve()))
    sentences = split_sentences(text)
    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    chunk_index = 0
    for sent in sentences:
        if not sent.strip():
            continue
        next_text = "\n".join(buffer + [sent])
        if buffer and len(next_text) > 900:
            chunks.append(_chunk_record(record, path, chunk_index, "\n".join(buffer)))
            chunk_index += 1
            buffer = [sent]
        else:
            buffer.append(sent)
    if buffer:
        chunks.append(_chunk_record(record, path, chunk_index, "\n".join(buffer)))
    return chunks


def _chunk_record(record: dict[str, Any], path: Path, chunk_index: int, text: str) -> dict[str, Any]:
    row = {
        "chunk_id": f"{record['doc_id']}_chunk_{chunk_index:04d}",
        "doc_id": record["doc_id"],
        "source_type": record["source_type"],
        "source_title": record["title"],
        "file_name": record["file_name"],
        "local_path": record["local_path"],
        "chunk_index": chunk_index,
        "text": text[:2000],
        "norm_text": norm_text(text[:2000]),
    }
    parsed_ref = to_project_ref(path)
    if parsed_ref != record["local_path"]:
        row["parsed_path"] = parsed_ref
    return row


def _build_table_cells(record: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact in parse_excel(str(path.resolve())):
        if not _keep_table_fact(fact):
            continue
        rows.append(
            {
                "cell_id": f"{record['doc_id']}_{fact.sheet_name}_{fact.cell_ref}",
                "doc_id": record["doc_id"],
                "source_type": "excel",
                "source_title": record["title"],
                "file_name": record["file_name"],
                "local_path": record["local_path"],
                "parsed_path": to_project_ref(path) if to_project_ref(path) != record["local_path"] else None,
                "sheet_name": fact.sheet_name,
                "cell_ref": fact.cell_ref,
                "row_index": fact.row_index,
                "col_index": fact.col_index,
                "row_header": fact.row_header,
                "col_header": fact.col_header,
                "unit": fact.unit,
                "value_raw": fact.value_raw,
                "value_num": fact.value_num,
                "text": f"{record['title']} {fact.sheet_name} {fact.row_header} {fact.col_header} {fact.value_raw}",
                "norm_text": norm_text(f"{record['title']}{fact.sheet_name}{fact.row_header}{fact.col_header}{fact.value_raw}"),
            }
        )
    return rows


def _build_table_rows(record: dict[str, Any], cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for cell in cells:
        key = (str(cell["sheet_name"]), int(cell["row_index"]), str(cell["row_header"]))
        grouped.setdefault(key, []).append(cell)

    rows: list[dict[str, Any]] = []
    for (sheet_name, row_index, row_header), group in grouped.items():
        group.sort(key=lambda item: int(item.get("col_index") or 0))
        facts = []
        cell_refs = []
        values = []
        for cell in group:
            col_header = cell.get("col_header") or cell.get("cell_ref")
            value_raw = cell.get("value_raw")
            facts.append(f"{col_header}={value_raw}({cell.get('cell_ref')})")
            cell_refs.append(cell.get("cell_ref"))
            values.append(value_raw)
        text = (
            f"文件：{record['title']}\n"
            f"工作表：{sheet_name}\n"
            f"行：{row_header}\n"
            f"数据：{'，'.join(facts)}"
        )
        unit = next((cell.get("unit") for cell in group if cell.get("unit")), None)
        headers: list[str] = []
        periods: list[str] = []
        structured_cells: list[dict[str, Any]] = []
        for cell in group:
            header = str(cell.get("col_header") or cell.get("cell_ref") or "").strip()
            period = _period_from_col_header(header)
            if header and header not in headers:
                headers.append(header)
            if period and period not in periods:
                periods.append(period)
            structured_cells.append(
                {
                    "cell_ref": cell.get("cell_ref"),
                    "col_index": cell.get("col_index"),
                    "header": header,
                    "period": period,
                    "value": cell.get("value_raw"),
                    "value_num": cell.get("value_num"),
                }
            )
        rows.append(
            {
                "row_id": f"{record['doc_id']}_{sheet_name}_{row_index}",
                "doc_id": record["doc_id"],
                "source_type": "excel",
                "source_title": record["title"],
                "file_name": record["file_name"],
                "local_path": record["local_path"],
                "sheet_name": sheet_name,
                "row_index": row_index,
                "row_header": row_header,
                "indicator": row_header,
                "unit": unit,
                "headers": headers,
                "periods": periods,
                "cells": structured_cells,
                "cell_refs": cell_refs,
                "values": values,
                "text": text,
                "semantic_text": f"{record['title']} {sheet_name} {row_header} {' '.join(periods)} {unit or ''}".strip(),
                "norm_text": norm_text(text),
            }
        )
    return rows


def _period_from_col_header(header: str) -> str | None:
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
            value = header.split(sep, 1)[0].strip()
            return value or None
    return header.strip()


def _keep_table_fact(fact: Any) -> bool:
    if fact.row_index > 500 or fact.col_index > 30:
        return False
    raw = str(fact.value_raw)
    if raw.startswith("#"):
        return False
    row_header = norm_text(fact.row_header)
    col_header = norm_text(fact.col_header)
    if not row_header or row_header.startswith("注"):
        return False
    if not col_header or "#REF" in col_header:
        return False
    return True


@lru_cache(maxsize=8)
def load_text_chunks(path: Path = TEXT_CHUNKS_PATH) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


@lru_cache(maxsize=8)
def load_table_cells(path: Path = TABLE_CELLS_PATH) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


@lru_cache(maxsize=8)
def load_table_rows(path: Path = TABLE_ROWS_PATH) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


def kb_available() -> bool:
    return TEXT_CHUNKS_PATH.exists() or TABLE_CELLS_PATH.exists() or TABLE_ROWS_PATH.exists()
