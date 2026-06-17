"""Rule-based question type classifier (no LLM)."""

from __future__ import annotations

import re

FIB_RE = re.compile(r"\\_\\_\\_\\_|____|fill\s+in\s+the\s+blank", re.IGNORECASE)
TICK_RE = re.compile(r"tick\s+the\s+correct|choose\s+the\s+correct|select\s+the\s+correct", re.IGNORECASE)
MATCH_RE = re.compile(r"match\s+the|column\s+[ab]", re.IGNORECASE)
ACTIVITY_RE = re.compile(r"activity\s+\d", re.IGNORECASE)
PROJECT_RE = re.compile(r"\bproject\b", re.IGNORECASE)
INTEGER_RE = re.compile(r"integer|numerical\s+value", re.IGNORECASE)
PASSAGE_RE = re.compile(r"passage\s+based|read\s+the\s+paragraph", re.IGNORECASE)


def classify_from_header(header: str) -> str | None:
    h = header.lower()
    if FIB_RE.search(h):
        return "FIB"
    if TICK_RE.search(h):
        return "SCQ"
    if MATCH_RE.search(h):
        return "MATCH"
    if INTEGER_RE.search(h):
        return "INTEGER"
    if PASSAGE_RE.search(h):
        return "PASSAGE"
    return None


def classify_question(
    section: str,
    stem: str,
    *,
    has_options: bool = False,
    has_roman_options: bool = False,
    has_match_columns: bool = False,
    header_hint: str = "",
) -> str:
    hint = classify_from_header(header_hint or stem)
    if hint:
        return hint

    sec = section.lower()
    if ACTIVITY_RE.search(sec):
        return "ACTIVITY"
    if "extended learning" in sec:
        return "PROJECT" if PROJECT_RE.search(stem) else "ACTIVITY"
    if has_match_columns or MATCH_RE.search(stem):
        return "MATCH"
    if FIB_RE.search(stem):
        return "FIB"
    if has_roman_options or (has_options and TICK_RE.search(stem)):
        return "SCQ"
    if has_options:
        return "SCQ"
    if INTEGER_RE.search(stem):
        return "INTEGER"
    if "?" in stem or re.search(r"^(write|explain|name|define|describe|list)", stem, re.I):
        return "SAQ"
    return "SUBJECTIVE"
