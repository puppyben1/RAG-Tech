from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .config import REPORTS_DIR, TEXT_CHUNKS_PATH, TEXT_UNITS_PATH
from .path_refs import to_project_ref
from .utils import ensure_dir, norm_text, read_jsonl, write_jsonl


TEXT_UNITS_REPORT = REPORTS_DIR / "text_units_report.json"

HEADING_PATTERNS = [
    ("chapter", re.compile(r"^第[一二三四五六七八九十百\d]+章\s*.*")),
    ("section", re.compile(r"^第[一二三四五六七八九十百\d]+节\s*.*")),
    ("article", re.compile(r"^第[一二三四五六七八九十百\d]+条\s*.*")),
    ("cn_number", re.compile(r"^[一二三四五六七八九十]+、.*")),
    ("paren_number", re.compile(r"^（[一二三四五六七八九十\d]+）.*")),
]


def build_text_units(
    chunks_path: Path = TEXT_CHUNKS_PATH,
    output_path: Path = TEXT_UNITS_PATH,
    report_path: Path = TEXT_UNITS_REPORT,
) -> dict[str, Any]:
    chunks = read_jsonl(chunks_path) if chunks_path.exists() else []
    units: list[dict[str, Any]] = []
    by_doc: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        by_doc.setdefault(chunk["doc_id"], []).append(chunk)
    for doc_chunks in by_doc.values():
        doc_chunks.sort(key=lambda row: int(row.get("chunk_index") or 0))
        units.extend(_units_for_document(doc_chunks))
    write_jsonl(output_path, units)
    report = _build_report(units, output_path)
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _units_for_document(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    section_stack: dict[str, str] = {}
    unit_index = 0
    for chunk in chunks:
        for page_no, page_text in _split_pages(str(chunk.get("text", ""))):
            blocks = _split_blocks(page_text)
            buffer: list[str] = []
            current_article: str | None = None
            for block in blocks:
                heading = _heading_line(block)
                heading_type = _heading_type(heading)
                if heading_type:
                    if buffer:
                        units.append(_unit_record(chunk, unit_index, page_no, section_stack, current_article, "\n".join(buffer)))
                        unit_index += 1
                        buffer = []
                    _update_sections(section_stack, heading_type, heading)
                    current_article = section_stack.get("article")
                    buffer.append(block)
                else:
                    buffer.append(block)
                    if _buffer_too_large(buffer):
                        units.append(_unit_record(chunk, unit_index, page_no, section_stack, current_article, "\n".join(buffer)))
                        unit_index += 1
                        buffer = []
            if buffer:
                units.append(_unit_record(chunk, unit_index, page_no, section_stack, current_article, "\n".join(buffer)))
                unit_index += 1
    return units


def _split_pages(text: str) -> list[tuple[int | None, str]]:
    matches = list(re.finditer(r"\[page\s+(\d+)\]", text, flags=re.IGNORECASE))
    if not matches:
        return [(None, text)]
    pages: list[tuple[int | None, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[start:end].strip()))
    return pages


def _split_blocks(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if _heading_type(line) and current:
            blocks.append("\n".join(current))
            current = [line]
            continue
        current.append(line)
        if len("".join(current)) >= 450 or line.endswith(("。", "；", "：")):
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return [block for block in blocks if norm_text(block)]


def _heading_type(text: str) -> str | None:
    compact = text.strip()
    for name, pattern in HEADING_PATTERNS:
        if pattern.match(compact):
            return name
    return None


def _heading_line(text: str) -> str:
    return text.strip().splitlines()[0].strip() if text.strip() else ""


def _update_sections(section_stack: dict[str, str], heading_type: str, heading: str) -> None:
    if heading_type == "chapter":
        section_stack.clear()
        section_stack["chapter"] = heading
    elif heading_type == "section":
        section_stack.pop("article", None)
        section_stack["section"] = heading
    elif heading_type == "article":
        section_stack["article"] = heading
    elif heading_type in {"cn_number", "paren_number"}:
        section_stack["clause"] = heading[:80]


def _unit_record(
    chunk: dict[str, Any],
    unit_index: int,
    page_no: int | None,
    section_stack: dict[str, str],
    article_no: str | None,
    text: str,
) -> dict[str, Any]:
    section_path = " / ".join(
        section_stack[key]
        for key in ("chapter", "section", "article", "clause")
        if section_stack.get(key)
    )
    return {
        "unit_id": f"{chunk['doc_id']}_unit_{unit_index:04d}",
        "doc_id": chunk["doc_id"],
        "source_type": chunk.get("source_type"),
        "source_title": chunk.get("source_title"),
        "file_name": chunk.get("file_name"),
        "local_path": chunk.get("local_path"),
        "chunk_id": chunk.get("chunk_id"),
        "chunk_index": chunk.get("chunk_index"),
        "unit_index": unit_index,
        "page_no": page_no,
        "section_path": section_path or None,
        "article_no": _article_no(article_no),
        "text": text[:2000],
        "norm_text": norm_text(text[:2000]),
    }


def _article_no(article: str | None) -> str | None:
    if not article:
        return None
    match = re.match(r"^(第[一二三四五六七八九十百\d]+条)", article)
    return match.group(1) if match else None


def _buffer_too_large(buffer: list[str]) -> bool:
    return len("\n".join(buffer)) >= 700


def _build_report(units: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    by_type = Counter(unit.get("source_type") for unit in units)
    return {
        "output_path": to_project_ref(output_path),
        "text_units": len(units),
        "with_page_no": sum(1 for unit in units if unit.get("page_no") is not None),
        "with_section_path": sum(1 for unit in units if unit.get("section_path")),
        "with_article_no": sum(1 for unit in units if unit.get("article_no")),
        "by_source_type": dict(by_type),
    }
