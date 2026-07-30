from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .config import RAW_DATA_DIR
from .qa_data import QAItem
from .text_parser import extract_text, split_sentences
from .utils import norm_text


@dataclass
class TextAnswerResult:
    answer: str | None
    answer_text: Any | None
    evidence: str
    confidence: str
    debug: str | None = None


def find_source_file(item: QAItem, data_dir: Path = RAW_DATA_DIR) -> Path | None:
    label = Path(item.file_label)
    label_stem = norm_text(label.stem)
    title = norm_text(item.source_title)
    candidates = sorted(p for p in data_dir.iterdir() if p.is_file())
    same_ext = [p for p in candidates if p.suffix.lower() == label.suffix.lower()] or candidates
    scored: list[tuple[int, Path]] = []
    for p in same_ext:
        stem = norm_text(p.stem)
        score = 0
        if label_stem and label_stem in stem:
            score += 1000 + len(label_stem)
        label_parts = [part for part in re_split_label(label.stem) if len(norm_text(part)) >= 2]
        if label_parts and all(norm_text(part) in stem for part in label_parts):
            score += 600 + sum(len(norm_text(part)) for part in label_parts)
        if label_parts:
            score += sum(40 for part in label_parts if norm_text(part) in stem)
        if title and title in stem:
            score += 100 + len(title)
        if score:
            scored.append((score, p))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], len(x[1].name)))
    return scored[0][1]


def re_split_label(text: str) -> list[str]:
    import re

    return [p for p in re.split(r"[_：:（）()\s]+", text) if p]


def option_parts(option: Any) -> list[str]:
    text = str(option)
    parts = [p.strip() for p in text.split("；") if p.strip()]
    return parts or [text.strip()]


def score_option(option: Any, text_norm: str) -> tuple[int, list[str]]:
    matched: list[str] = []
    score = 0
    for part in option_parts(option):
        p = norm_text(part)
        if not p:
            continue
        if p in text_norm:
            score += len(p) + 200
            matched.append(part)
        else:
            coverage = ngram_coverage(p, text_norm)
            clause_hits = 0
            for seg in split_clause(p):
                if len(seg) >= 6 and seg in text_norm:
                    clause_hits += len(seg)
            part_score = int(coverage * 300) + clause_hits
            if coverage >= 0.65:
                matched.append(part)
            score += part_score
    return score, matched


def split_clause(text: str) -> list[str]:
    seps = "，。、；：（）()"
    parts = [text]
    for sep in seps:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(sep))
        parts = next_parts
    return [p for p in parts if p]


def ngram_coverage(needle: str, haystack: str, n: int = 3) -> float:
    if not needle or not haystack:
        return 0.0
    if len(needle) < n:
        return 1.0 if needle in haystack else 0.0
    grams = {needle[i : i + n] for i in range(len(needle) - n + 1)}
    if not grams:
        return 0.0
    hits = sum(1 for gram in grams if gram in haystack)
    coverage = hits / len(grams)
    if coverage >= 0.5:
        return coverage
    # Last-resort fuzzy match on a compact prefix-sized window.
    best = 0.0
    window = min(max(len(needle) * 2, 80), 240)
    step = max(window // 3, 30)
    for start in range(0, max(len(haystack) - window + 1, 1), step):
        ratio = SequenceMatcher(None, needle, haystack[start : start + window]).ratio()
        if ratio > best:
            best = ratio
    return max(coverage, best)


def nearest_evidence(text: str, option: Any) -> str:
    sentences = split_sentences(text)
    parts = option_parts(option)
    for part in parts:
        target = norm_text(part)
        for sent in sentences:
            if target and target in norm_text(sent):
                return sent
    for part in parts:
        clauses = split_clause(norm_text(part))
        for sent in sentences:
            sent_norm = norm_text(sent)
            if any(len(c) >= 8 and c in sent_norm for c in clauses):
                return sent
    best_sentence = ""
    best_score = 0.0
    for part in parts:
        target = norm_text(part)
        for sent in sentences:
            score = ngram_coverage(target, norm_text(sent))
            if score > best_score:
                best_score = score
                best_sentence = sent
    if best_score >= 0.45:
        return best_sentence
    return ""


def solve_text_mcq(item: QAItem, data_dir: Path = RAW_DATA_DIR) -> TextAnswerResult:
    path = find_source_file(item, data_dir)
    if path is None:
        return TextAnswerResult(None, None, "", "low", "file not found")
    text = extract_text(str(path.resolve()))
    text_norm = norm_text(text)
    scores: list[tuple[int, str, Any, list[str]]] = []
    for key, option in item.options.items():
        score, matched = score_option(option, text_norm)
        scores.append((score, key, option, matched))
    scores.sort(key=lambda x: x[0], reverse=True)
    if not scores or scores[0][0] == 0:
        return TextAnswerResult(None, None, "", "low", f"no option matched in {path.name}")
    if len(scores) > 1 and scores[0][0] == scores[1][0]:
        return TextAnswerResult(None, None, "", "low", f"tie {scores[0][0]} in {path.name}")
    evidence = nearest_evidence(text, scores[0][2])
    if not evidence and scores[0][3]:
        evidence = "；".join(scores[0][3])
    return TextAnswerResult(scores[0][1], scores[0][2], f"{path}；{evidence}", "medium")
