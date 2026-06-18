"""Parse Foundation SOLUTIONS zone and pair with questions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from foundation.models import FoundationQuestion
from foundation.preprocess import preprocess
from foundation.questions_parser import is_exercise_header, is_question_section, normalize_section
from foundation.regex import (
    ANSWER_LINE_RE,
    DIRECTIONS_RE,
    PLAIN_EXERCISE_RE,
    PLAIN_SUBSECTION_RE,
    SECTION_HEADER_RE,
    SKIP_SECTION_RE,
    SUBSECTION_RE,
)


@dataclass
class ParsedAnswer:
    qnum: int
    answer_key: str
    explanation: str
    exercise: str
    subsection: str
    section: str


def _parse_answer_body(body: str, section: str) -> tuple[str, str]:
    body = body.strip()
    if not body:
        return "", ""

    sec = section.lower()
    m = re.match(r"^\(([a-d])\)\s*(.*)$", body, re.IGNORECASE | re.DOTALL)
    if m and ("multiple choice" in sec or "assertion" in sec or "mcq" in sec):
        return m.group(1).upper(), m.group(2).strip()

    m = re.match(r"^(\d+)\s*$", body)
    if m and ("integer" in sec or "numerical" in sec):
        return m.group(1), ""

    if body.lower() in ("true", "false") or re.match(r"^(true|false)\s*$", body, re.I):
        return body.strip().title(), ""

    if "→" in body or "->" in body:
        return body.strip(), ""

    if len(body) <= 40 and not body.endswith("."):
        return body.strip(), ""

    return "", body.strip()


def parse_solutions_zone(text: str) -> list[ParsedAnswer]:
    text = preprocess(text)
    lines = text.splitlines()

    exercise = ""
    subsection = ""
    section = ""
    answers: list[ParsedAnswer] = []

    buf_num = 0
    buf_key = ""
    buf_lines: list[str] = []

    def flush(end_line: int) -> None:
        nonlocal buf_num, buf_key, buf_lines
        if not buf_num or not section:
            buf_num = 0
            buf_key = ""
            buf_lines = []
            return
        body = "\n".join(buf_lines).strip()
        key, expl = _parse_answer_body(buf_key + (" " + body if buf_key and body else body), section)
        if not key and buf_key:
            key, expl = _parse_answer_body(buf_key, section)
            if body and not expl:
                expl = body
        elif buf_key and not key:
            key = buf_key.strip()
            expl = body
        elif not key:
            key, expl = _parse_answer_body(body, section)

        answers.append(
            ParsedAnswer(
                qnum=buf_num,
                answer_key=key.strip(),
                explanation=expl.strip(),
                exercise=exercise,
                subsection=subsection,
                section=section,
            )
        )
        buf_num = 0
        buf_key = ""
        buf_lines = []

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue

        if SKIP_SECTION_RE.search(stripped) and not SECTION_HEADER_RE.match(stripped):
            flush(i - 1)
            continue

        if PLAIN_EXERCISE_RE.match(stripped):
            flush(i - 1)
            exercise = stripped
            subsection = ""
            section = ""
            continue

        if PLAIN_SUBSECTION_RE.match(stripped) or SUBSECTION_RE.match(stripped):
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
                continue
            if SUBSECTION_RE.match(title):
                subsection = title
                continue
            if is_question_section(title):
                section = title
                continue
            continue

        if SUBSECTION_RE.match(stripped):
            subsection = stripped
            continue

        if DIRECTIONS_RE.match(stripped):
            continue

        m = ANSWER_LINE_RE.match(stripped)
        if m and section:
            flush(i - 1)
            buf_num = int(m.group(1))
            buf_key = (m.group(2) or "").strip()
            rest = (m.group(3) or "").strip()
            buf_lines = [rest] if rest else []
            continue

        if buf_num and not SECTION_HEADER_RE.match(stripped):
            if ANSWER_LINE_RE.match(stripped):
                flush(i - 1)
                m2 = ANSWER_LINE_RE.match(stripped)
                if m2:
                    buf_num = int(m2.group(1))
                    buf_key = (m2.group(2) or "").strip()
                    rest = (m2.group(3) or "").strip()
                    buf_lines = [rest] if rest else []
                continue
            buf_lines.append(stripped)

    flush(len(lines))
    return answers


def answer_key_tuple(a: ParsedAnswer) -> tuple[str, str, str, int]:
    return (a.exercise, a.subsection, normalize_section(a.section), a.qnum)


def question_key_tuple(q: FoundationQuestion) -> tuple[str, str, str, int]:
    return (q.exercise, q.subsection, normalize_section(q.section), q.qnum)


def pair_answers(
    questions: list[FoundationQuestion],
    answers: list[ParsedAnswer],
) -> tuple[int, int]:
    by_exact: dict[tuple[str, str, str, int], ParsedAnswer] = {}
    by_no_sub: dict[tuple[str, str, int], list[ParsedAnswer]] = {}
    by_section: dict[tuple[str, int], list[ParsedAnswer]] = {}

    for a in answers:
        by_exact[answer_key_tuple(a)] = a
        nk = (a.exercise, normalize_section(a.section), a.qnum)
        by_no_sub.setdefault(nk, []).append(a)
        sk = (normalize_section(a.section), a.qnum)
        by_section.setdefault(sk, []).append(a)

    paired = 0
    for q in questions:
        if q.answer_key:
            continue
        key = question_key_tuple(q)
        ans = by_exact.get(key)
        if not ans:
            nk = (q.exercise, normalize_section(q.section), q.qnum)
            cands = by_no_sub.get(nk, [])
            if len(cands) == 1:
                ans = cands[0]
            elif len(cands) > 1:
                for c in cands:
                    if c.subsection == q.subsection:
                        ans = c
                        break
        if not ans:
            sk = (normalize_section(q.section), q.qnum)
            cands = by_section.get(sk, [])
            if len(cands) == 1:
                ans = cands[0]
        if ans:
            q.answer_key = ans.answer_key
            q.explanation = ans.explanation
            if (q.answer_key or "").strip() or (q.explanation or "").strip():
                q.answer_source = "book"
                paired += 1

    return paired, len(answers)
