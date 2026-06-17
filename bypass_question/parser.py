"""Parse bypass rephrase .mmd files."""

from __future__ import annotations

import re
from pathlib import Path

from bypass_question.models import ParsedBypassFile, ParsedQuestion

SOURCE_HEADER_RE = re.compile(
    r"^%\s*Bypass questions from:\s*(.+?)(?:_QA)?\.mmd\s*$",
    re.IGNORECASE,
)
SUBJECT_HEADER_RE = re.compile(
    r"^%\s*Subject:\s*([^|]+?)(?:\s*\|\s*count:\s*(\d+))?\s*$",
    re.IGNORECASE,
)
QUESTION_HEADER_RE = re.compile(r"^%\s*---\s*(Q[\w]+)\s*---\s*$", re.IGNORECASE)
CLASS_LEVEL_RE = re.compile(r"_c(\d+)_", re.IGNORECASE)


def _subject_abbr(subject: str) -> str:
    mapping = {
        "botany": "BOT",
        "zoology": "ZOO",
        "physics": "PHY",
        "chemistry": "CHE",
        "biology": "BIO",
        "mathematics": "MAT",
        "maths": "MAT",
        "science": "SCI",
    }
    return mapping.get(subject.strip().lower(), subject[:3].upper())


def infer_source(filename: str) -> str:
    stem = Path(filename).stem
    if stem.endswith("_rephrase"):
        stem = stem[: -len("_rephrase")]
    return stem


def infer_class_level(filename: str, source: str) -> int:
    for text in (filename, source):
        m = CLASS_LEVEL_RE.search(text)
        if m:
            return int(m.group(1))
    return 8


def parse_bypass_mmd(text: str, source_file: str = "") -> ParsedBypassFile:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    source = infer_source(source_file) if source_file else ""
    subject = "Science"
    class_level = infer_class_level(source_file, source)

    questions: list[ParsedQuestion] = []
    current_id: str | None = None
    current_stem_lines: list[str] = []
    current_start = 0

    def flush(end_line: int) -> None:
        nonlocal current_id, current_stem_lines, current_start
        if not current_id:
            return
        stem = "\n".join(current_stem_lines).strip()
        if stem:
            questions.append(
                ParsedQuestion(
                    question_id=current_id,
                    stem=stem,
                    line_start=current_start,
                    line_end=end_line,
                )
            )
        current_id = None
        current_stem_lines = []

    for i, raw in enumerate(lines, start=1):
        line = raw.strip()

        m_src = SOURCE_HEADER_RE.match(line)
        if m_src:
            source = Path(m_src.group(1).strip()).stem.replace("_QA", "")
            class_level = infer_class_level(source_file, source)
            continue

        m_sub = SUBJECT_HEADER_RE.match(line)
        if m_sub:
            subject = m_sub.group(1).strip()
            continue

        m_q = QUESTION_HEADER_RE.match(line)
        if m_q:
            flush(i - 1)
            current_id = m_q.group(1)
            current_start = i + 1
            current_stem_lines = []
            continue

        if current_id and line and not line.startswith("%"):
            current_stem_lines.append(raw.rstrip())

    flush(len(lines))

    if not source and source_file:
        source = infer_source(source_file)
        class_level = infer_class_level(source_file, source)

    return ParsedBypassFile(
        source=source,
        subject=subject,
        class_level=class_level,
        source_file=source_file,
        questions=questions,
    )


def make_qid(source: str, subject: str, question_id: str) -> str:
    abbr = _subject_abbr(subject)
    return f"{source}_{abbr}_{question_id}"
