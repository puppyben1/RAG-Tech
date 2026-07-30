from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import MANIFEST_PATH, RAW_DATA_DIR, SUPPORTED_EXTENSIONS
from .utils import sha256_file, write_jsonl


@dataclass
class DocumentRecord:
    doc_id: str
    title: str
    file_name: str
    local_path: str
    file_ext: str
    file_size: int
    sha256: str
    source_type: str
    period: str | None = None
    source_url: str | None = None
    attachment_url: str | None = None
    column: str | None = None


def infer_source_type(ext: str) -> str:
    if ext in {".xls", ".xlsx"}:
        return "excel"
    if ext in {".doc", ".docx"}:
        return "word"
    if ext == ".pdf":
        return "pdf"
    return ext.lstrip(".") or "unknown"


def clean_title(file_name: str) -> str:
    stem = Path(file_name).stem
    stem = re.sub(r"^\d+_", "", stem)
    parts = stem.split("_")
    if len(parts) >= 2 and parts[-1]:
        return parts[-1]
    return stem


def infer_period(text: str) -> str | None:
    m = re.search(r"(\d{4}年(?:\d{1,2}月|[一二三四1-4]季度|[1-4]季度)?)", text)
    return m.group(1) if m else None


def build_manifest(raw_data_dir: Path = RAW_DATA_DIR, output_path: Path = MANIFEST_PATH) -> list[DocumentRecord]:
    files = sorted(p for p in raw_data_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    records: list[DocumentRecord] = []
    for idx, path in enumerate(files, start=1):
        ext = path.suffix.lower()
        prefix = path.stem.split("_", 1)[0]
        numeric_prefix = prefix if prefix.isdigit() else f"{idx:03d}"
        title = clean_title(path.name)
        records.append(
            DocumentRecord(
                doc_id=f"nfra_{numeric_prefix}",
                title=title,
                file_name=path.name,
                local_path=str(path.resolve()),
                file_ext=ext,
                file_size=path.stat().st_size,
                sha256=sha256_file(path),
                source_type=infer_source_type(ext),
                period=infer_period(path.name),
            )
        )
    write_jsonl(output_path, (asdict(r) for r in records))
    return records

