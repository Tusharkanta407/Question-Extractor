"""Preprocess Foundation .mmd source text."""

from __future__ import annotations

import re

from foundation.regex import DROP_LINE_RE, TABULAR_END_RE, TABULAR_START_RE


def remove_figure_blocks(text: str) -> str:
    return re.sub(
        r"\\begin\{figure\}.*?\\end\{figure\}",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def _clean_table_line(line: str) -> str:
    line = re.sub(r"\\hline\b", "", line)
    line = line.replace("\\\\", " | ")
    line = re.sub(r"\\multicolumn\{[^}]+\}\{[^}]+\}\{([^}]*)\}", r"\1", line)
    return re.sub(r"\s+", " ", line).strip()


def flatten_tabular(text: str) -> str:
    out: list[str] = []
    in_table = False
    for line in text.splitlines():
        if TABULAR_START_RE.search(line):
            in_table = True
            rest = TABULAR_START_RE.split(line, maxsplit=1)[-1]
            if rest.strip():
                out.append(_clean_table_line(rest))
            continue
        if TABULAR_END_RE.search(line):
            in_table = False
            before = TABULAR_END_RE.split(line, maxsplit=1)[0]
            if before.strip():
                out.append(_clean_table_line(before))
            continue
        if in_table:
            out.append(_clean_table_line(line))
        else:
            out.append(line)
    return "\n".join(out)


def preprocess(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = remove_figure_blocks(text)
    text = flatten_tabular(text)
    lines = [ln for ln in text.splitlines() if not DROP_LINE_RE.match(ln)]
    return "\n".join(lines)


def extract_title(text: str) -> str:
    m = re.search(r"\\section\*\{(\d+\.\s*[^}]+)\}", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\\title\{\s*\n?(.+?)\n?\}", text, re.DOTALL)
    return m.group(1).strip() if m else "Question Bank"


def infer_subject(title: str, filename: str) -> str:
    blob = f"{title} {filename}".lower()
    mapping = (
        ("chemical", "Chemistry"),
        ("chemistry", "Chemistry"),
        ("physics", "Physics"),
        ("biology", "Biology"),
        ("mathematics", "Mathematics"),
        ("maths", "Mathematics"),
        ("science", "Science"),
    )
    for key, label in mapping:
        if key in blob:
            return label
    return "Science"


def infer_class_level(filename: str, title: str) -> int:
    for text in (filename, title):
        m = re.search(r"_c(\d+)_", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"class\s+(\d+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 10


def split_zones(text: str) -> tuple[str, str]:
    from foundation.regex import EXERCISE_START_RE, SOLUTIONS_START_RE

    m_start = EXERCISE_START_RE.search(text)
    if not m_start:
        return text, ""
    questions_zone = text[m_start.start() :]
    m_end = SOLUTIONS_START_RE.search(questions_zone)
    if m_end:
        solutions_zone = questions_zone[m_end.start() :]
        questions_zone = questions_zone[: m_end.start()]
    else:
        solutions_zone = ""
    return questions_zone, solutions_zone
