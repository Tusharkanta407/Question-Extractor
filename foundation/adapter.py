"""Adapt FoundationDocument for shared export interfaces."""

from __future__ import annotations

import re

from foundation.formatter import format_question_bank
from foundation.models import FoundationDocument, FoundationQuestion
from models import ExtractedDocument, Question, QuestionOption

# Matches a non-negative integer or decimal: 0, 42, 3.5, +7  (no negatives)
_NONNEG_NUMERIC_RE = re.compile(r"^\+?\d+(\.\d+)?$")


def _is_nonneg_numeric(value: str) -> bool:
    """Return True if value is a non-negative integer or decimal number."""
    return bool(_NONNEG_NUMERIC_RE.match(value.strip()))


def _fib_to_scq_options(correct_answer: str) -> list[QuestionOption]:
    """Build MCQ options with correct answer as (a) and blank placeholders for (b)(c)(d)."""
    return [
        QuestionOption(label="a", text=correct_answer),
        QuestionOption(label="b", text="___"),
        QuestionOption(label="c", text="___"),
        QuestionOption(label="d", text="___"),
    ]


def foundation_to_extracted(doc: FoundationDocument) -> ExtractedDocument:
    questions: list[Question] = []
    for i, fq in enumerate(doc.questions):
        opts = [QuestionOption(o.label, o.text) for o in (fq.options or fq.shared_options)]
        stem = fq.stem
        if fq.passage:
            stem = f"[Passage] {fq.passage}\n\n{stem}"

        q_type = fq.question_type
        answer_key = (fq.answer_key or "").strip()
        needs_review = not bool(answer_key)
        convertible = False

        # ── Rule 1: INTEGER — only non-negative numeric answers allowed ──────
        if q_type == "INTEGER" and answer_key:
            if not _is_nonneg_numeric(answer_key):
                # Invalid answer (negative / text) — flag for review, keep type
                needs_review = True

        # ── Rule 2: ALL FIB → convert to SCQ ────────────────────────────────
        elif q_type == "FIB":
            q_type = "SCQ"
            convertible = True
            if answer_key:
                opts = _fib_to_scq_options(answer_key)
                needs_review = True   # distractors (b)(c)(d) need real values
            else:
                needs_review = True

        questions.append(
            Question(
                id=f"foundation-{fq.qid}",
                section=fq.section,
                number=str(fq.qnum),
                type=q_type,
                stem=stem,
                options=opts,
                match_column_a=[QuestionOption(o.label, o.text) for o in fq.column_a],
                match_column_b=[QuestionOption(o.label, o.text) for o in fq.column_b],
                raw_text=stem,
                flags={
                    "partial": False,
                    "needs_review": needs_review,
                    "convertible": convertible,
                },
            )
        )
    return ExtractedDocument(
        title=doc.title,
        source_format="foundation",
        source_file=doc.source_file,
        questions=questions,
    )


def foundation_plain_text(doc: FoundationDocument) -> str:
    return format_question_bank(doc)
