"""Parse Foundation questions zone into structured questions."""

from __future__ import annotations

import re

from foundation.models import FoundationQuestion, QuestionOption
from foundation.preprocess import preprocess
from foundation.regex import (
    COLUMN_I_RE,
    COLUMN_II_RE,
    COLUMN_LABEL_RE,
    DIRECTIONS_RE,
    MCQ_OPTION_RE,
    NUMBERED_Q_RE,
    PASSAGE_HEADER_RE,
    PLAIN_EXERCISE_RE,
    PLAIN_SUBSECTION_RE,
    QUESTION_SECTION_RE,
    REASON_RE,
    ROMAN_SUB_RE,
    SECTION_HEADER_RE,
    SHARED_OPTION_RE,
    SKIP_SECTION_RE,
    SUBSECTION_RE,
)


def is_question_section(title: str) -> bool:
    return bool(QUESTION_SECTION_RE.search(title))


def is_exercise_header(title: str) -> bool:
    return bool(re.match(r"Exercise\s+\d+", title, re.IGNORECASE))


def normalize_section(title: str) -> str:
    title = title.replace("\\&", "&").replace("\\\\", "")
    return re.sub(r"\s+", " ", title).strip().lower()


def infer_question_type(section: str, directions: str, *, has_options: bool) -> str:
    s = section.lower()
    d = directions.lower()
    if "assertion" in s:
        return "ASSERTION_REASON"
    if "fill in" in s:
        return "FIB"
    if "true" in s and "false" in s:
        return "TRUE_FALSE"
    if "match" in s:
        return "MATCH"
    if "passage" in s and "case" not in s:
        return "PASSAGE"
    if "case study" in s:
        return "CASE_STUDY"
    if "integer" in s or "numerical" in s:
        return "INTEGER"
    if "very short" in s:
        return "VSA"
    if "short answer" in s:
        return "SA"
    if "long answer" in s:
        return "LA"
    if "text - book" in s or "text-book" in s:
        return "TEXTBOOK"
    if "multiple choice" in s or "mcq" in s:
        if "one or more" in d:
            return "MCQ_MULTI"
        return "MCQ"
    if has_options:
        return "MCQ"
    return "DESCRIPTIVE"


def _section_key(exercise: str, subsection: str, section: str) -> str:
    return f"{exercise}|{subsection}|{normalize_section(section)}"


class _Draft:
    __slots__ = (
        "qnum", "sub_id", "stem_lines", "options", "column_a", "column_b", "line_start"
    )

    def __init__(self) -> None:
        self.qnum = 0
        self.sub_id = ""
        self.stem_lines: list[str] = []
        self.options: list[QuestionOption] = []
        self.column_a: list[QuestionOption] = []
        self.column_b: list[QuestionOption] = []
        self.line_start = 0

    def clear(self) -> None:
        self.qnum = 0
        self.sub_id = ""
        self.stem_lines = []
        self.options = []
        self.column_a = []
        self.column_b = []
        self.line_start = 0


def _is_continuation(stripped: str, *, in_question: bool) -> bool:
    if not stripped:
        return False
    if SECTION_HEADER_RE.match(stripped):
        return False
    if DIRECTIONS_RE.match(stripped):
        return False
    if NUMBERED_Q_RE.match(stripped):
        return False
    if MCQ_OPTION_RE.match(stripped):
        return False
    if ROMAN_SUB_RE.match(stripped):
        return False
    if COLUMN_I_RE.match(stripped) or COLUMN_II_RE.match(stripped):
        return False
    if COLUMN_LABEL_RE.match(stripped):
        return False
    if SHARED_OPTION_RE.match(stripped):
        return False
    if PASSAGE_HEADER_RE.match(stripped):
        return False
    return in_question or stripped.startswith("$") or stripped.startswith("\\")


def _make_qid(qnum: int, sub_id: str) -> str:
    return f"Q{qnum}{sub_id}" if sub_id else f"Q{qnum}"


def _finalize_draft(
    draft: _Draft,
    *,
    exercise: str,
    subsection: str,
    section: str,
    directions: str,
    shared_options: list[QuestionOption],
    passage: str,
    line_end: int,
) -> FoundationQuestion | None:
    stem = "\n".join(draft.stem_lines).strip()
    if not stem and not draft.options:
        return None

    opts = draft.options or list(shared_options)
    qtype = infer_question_type(section, directions, has_options=bool(opts))

    return FoundationQuestion(
        qnum=draft.qnum,
        qid=_make_qid(draft.qnum, draft.sub_id),
        question_type=qtype,
        exercise=exercise,
        subsection=subsection,
        section=section,
        stem=stem,
        options=list(draft.options),
        shared_options=list(shared_options) if not draft.options else [],
        column_a=list(draft.column_a),
        column_b=list(draft.column_b),
        passage=passage,
        directions=directions,
        line_start=draft.line_start,
        line_end=line_end,
    )


def parse_questions_zone(text: str) -> list[FoundationQuestion]:
    text = preprocess(text)
    lines = text.splitlines()

    exercise = ""
    subsection = ""
    section = ""
    directions = ""
    shared_options: list[QuestionOption] = []
    passage = ""
    in_passage = False

    draft = _Draft()
    questions: list[FoundationQuestion] = []
    global_idx = 0

    def flush(end_line: int) -> None:
        nonlocal global_idx
        q = _finalize_draft(
            draft,
            exercise=exercise,
            subsection=subsection,
            section=section,
            directions=directions,
            shared_options=shared_options,
            passage=passage,
            line_end=end_line,
        )
        if q:
            global_idx += 1
            questions.append(q)
        draft.clear()

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue

        if PLAIN_EXERCISE_RE.match(stripped):
            flush(i - 1)
            exercise = stripped
            subsection = ""
            section = ""
            directions = ""
            shared_options = []
            passage = ""
            in_passage = False
            continue

        if PLAIN_SUBSECTION_RE.match(stripped):
            subsection = stripped
            continue

        m_sec = SECTION_HEADER_RE.match(stripped)
        if m_sec:
            flush(i - 1)
            title = m_sec.group(1).strip()

            if is_exercise_header(title):
                exercise = title
                subsection = ""
                section = ""
                directions = ""
                shared_options = []
                passage = ""
                in_passage = False
                continue

            if SUBSECTION_RE.match(title) or PLAIN_SUBSECTION_RE.match(title):
                subsection = title
                continue

            if SKIP_SECTION_RE.search(title):
                section = ""
                continue

            if title.lower() == "passage":
                in_passage = True
                passage = ""
                continue

            if is_question_section(title):
                section = title
                directions = ""
                shared_options = []
                in_passage = False
                continue

            continue

        if PASSAGE_HEADER_RE.match(stripped):
            in_passage = False
            continue

        if DIRECTIONS_RE.match(stripped):
            directions = stripped
            continue

        if SHARED_OPTION_RE.match(stripped):
            m = MCQ_OPTION_RE.match(stripped)
            if m:
                shared_options.append(QuestionOption(m.group(1).lower(), m.group(2).strip()))
            continue

        if COLUMN_LABEL_RE.match(stripped):
            continue

        m_col_i = COLUMN_I_RE.match(stripped)
        if m_col_i and section and "match" in section.lower():
            draft.column_a.append(QuestionOption(m_col_i.group(1), m_col_i.group(2).strip()))
            continue

        m_col_ii = COLUMN_II_RE.match(stripped)
        if m_col_ii:
            draft.column_b.append(QuestionOption(m_col_ii.group(1).lower(), m_col_ii.group(2).strip()))
            continue

        if in_passage and section:
            passage = (passage + "\n" + stripped).strip() if passage else stripped
            continue

        m_roman = ROMAN_SUB_RE.match(stripped)
        if m_roman and section and "case study" in section.lower():
            flush(i - 1)
            draft.sub_id = f"({m_roman.group(1)})"
            draft.stem_lines = [m_roman.group(2).strip()] if m_roman.group(2).strip() else []
            draft.line_start = i
            continue

        m_q = NUMBERED_Q_RE.match(stripped)
        if m_q and section:
            flush(i - 1)
            draft.qnum = int(m_q.group(1))
            rest = m_q.group(2).strip()
            draft.stem_lines = [rest] if rest else []
            draft.line_start = i

            if REASON_RE.match(rest) and draft.stem_lines:
                pass
            continue

        m_opt = MCQ_OPTION_RE.match(stripped)
        if m_opt and section and draft.qnum:
            draft.options.append(QuestionOption(m_opt.group(1).lower(), m_opt.group(2).strip()))
            continue

        if draft.qnum and REASON_RE.match(stripped):
            draft.stem_lines.append(stripped)
            continue

        if draft.qnum and _is_continuation(stripped, in_question=bool(draft.stem_lines)):
            draft.stem_lines.append(stripped)
            continue

        if section and not draft.qnum and not in_passage:
            m_q2 = NUMBERED_Q_RE.match(stripped)
            if m_q2:
                flush(i - 1)
                draft.qnum = int(m_q2.group(1))
                rest = m_q2.group(2).strip()
                draft.stem_lines = [rest] if rest else []
                draft.line_start = i

    flush(len(lines))
    return questions


def pairing_key(q: FoundationQuestion) -> tuple[str, str, str, int, str]:
    return (
        q.exercise,
        q.subsection,
        normalize_section(q.section),
        q.qnum,
        q.sub_id,
    )
