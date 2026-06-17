"""Rule-based question type scoring (no LLM)."""

from __future__ import annotations

import re

from bypass_question.models import ParsedQuestion, ScoredQuestion

FIB_RE = re.compile(r"_{2,}|fill\s+in\s+the\s+blank", re.IGNORECASE)
MATCH_RE = re.compile(r"match\s+the|column\s+[ab]", re.IGNORECASE)
INTEGER_RE = re.compile(
    r"\bhow\s+many\b|\bnumber\s+of\b|\bmeasures?\s+\d+\b|\b\d+\s+on\s+this\s+scale\b",
    re.IGNORECASE,
)
LIST_NAME_RE = re.compile(
    r"^(name|list|which|suggest|state)\b", re.IGNORECASE
)
EXPLAIN_RE = re.compile(
    r"\bexplain\b|\bdescribe\b|\bwrite\b|\bdiagram\b|\bparagraph\b|\blines\b",
    re.IGNORECASE,
)
STATEMENT_RE = re.compile(r"^[A-Z].*[a-z]\.$")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_question(q: ParsedQuestion) -> ScoredQuestion:
    stem = q.stem.strip()
    lower = stem.lower()

    scq = 0.35
    mcq = 0.35
    integer = 0.1

    if FIB_RE.search(stem):
        scq = 0.92
        mcq = 0.45
        integer = 0.08
    elif "?" not in stem and STATEMENT_RE.match(stem):
        scq = 0.88
        mcq = 0.28
        integer = 0.05
    elif MATCH_RE.search(stem):
        scq = 0.45
        mcq = 0.82
        integer = 0.1
    elif INTEGER_RE.search(stem):
        scq = 0.25
        mcq = 0.45
        integer = 0.78
    elif LIST_NAME_RE.search(stem):
        scq = 0.42
        mcq = 0.72
        integer = 0.18
    elif EXPLAIN_RE.search(stem):
        scq = 0.22
        mcq = 0.38
        integer = 0.06
    elif "?" in stem:
        scq = 0.4
        mcq = 0.55
        integer = 0.15

    scores = {
        "scq": _clamp(scq),
        "mcq": _clamp(mcq),
        "integer": _clamp(integer),
    }
    recommended = max(scores, key=scores.get)
    confidence = scores[recommended]

    return ScoredQuestion(
        question_id=q.question_id,
        stem=q.stem,
        line_start=q.line_start,
        line_end=q.line_end,
        scores=scores,
        recommended_type=recommended,
        confidence=confidence,
    )
