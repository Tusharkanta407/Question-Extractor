"""
foundation_qa_extractor.py
==========================
Extract questions from Foundation / exercise-book .mmd files.

Keeps exercise-zone content: MCQs, Assertion & Reason, fill-in-the-blanks,
match-the-following, passage-based, and short/long answer sections.
Skips chapter theory and the Solutions / answer-key section.
"""

from __future__ import annotations

import re
from pathlib import Path

EXERCISE_START_RE = re.compile(r"\\section\*\{Exercise\s+\d+", re.IGNORECASE)
SOLUTIONS_START_RE = re.compile(
    r"\\section\*\{(?:SOLUTIONS|Answer\s*Key|Answers)\b", re.IGNORECASE
)

QUESTION_SECTION_RE = re.compile(
    r"""
      Multiple\s+Choice
    | Assertion\s*(?:\\&|&)\s*Reason
    | Fill\s+in\s+the\s+Blanks
    | True\s*/\s*False
    | Match(?:ing)?\s+(?:the\s+Following|Questions)
    | Multiple\s+Matching
    | Passage\s+Based
    | Case\s+Study
    | Very\s+Short\s+Answer
    | Short\s+Answer
    | Long\s+Answer
    | Reasoning\s+Based
    | Integer(?:\s*/\s*Numerical\s+Value)?\s+Type
    | Numerical\s+Value\s+Type
    | HOTS
    | Exemplar\s+Questions
    | Text\s*-\s*Book\s+Questions
    | Text\s*-\s*Book\s+Exercise
    """,
    re.VERBOSE | re.IGNORECASE,
)

SKIP_SECTION_RE = re.compile(
    r"""
      ^Master\s+Boards$
    | ^Master\s+NCERT
    | ^CONNECTING\s+TOPIC
    | ^Exercise\s+\d+
    | ^SOLUTION$
    | ^REDOX\s+REACTIONS$
    | ^Oxidation\s+Number\s+Method
    | ^Ion\s+Electron\s+Method
    """,
    re.VERBOSE | re.IGNORECASE,
)

DROP_LINE_RE = re.compile(
    r"""
      ^\s*\\begin\{figure\}
    | ^\s*\\end\{figure\}
    | ^\s*\\includegraphics
    | ^\s*\\caption
    | ^\s*!\[
    | ^\s*\\label\{
    | ^\s*\\captionsetup
    """,
    re.VERBOSE | re.IGNORECASE,
)

SECTION_HEADER_RE = re.compile(r"^\\section\*\{(.+)\}$")

NUMBERED_Q_RE = re.compile(r"^(\d+)[\.\)]\s*(.*)")
MCQ_OPTION_RE = re.compile(r"^\(([a-d])\)\s*(.*)$", re.IGNORECASE)
SHARED_OPTION_RE = re.compile(r"^\(([a-d])\)\s+If\b", re.IGNORECASE)
COLUMN_I_RE = re.compile(r"^\(([A-D])\)\s*(.*)$")
COLUMN_II_RE = re.compile(r"^\(([p-t])\)\s*(.*)$", re.IGNORECASE)
SUBPART_RE = re.compile(r"^\(([ivx]+)\)\s*(.*)$", re.IGNORECASE)
DIRECTIONS_RE = re.compile(r"^DIRECTIONS\b", re.IGNORECASE)
REASON_RE = re.compile(r"^Reason\s*:", re.IGNORECASE)
ASSERTION_IN_Q_RE = re.compile(r"Assertion\s*:", re.IGNORECASE)
COLUMN_LABEL_RE = re.compile(r"^Column\s+(I{1,3}|II)\b", re.IGNORECASE)

TABULAR_START_RE = re.compile(r"\\begin\{tabular\}")
TABULAR_END_RE = re.compile(r"\\end\{tabular\}")


def extract_title(text: str) -> str:
    m = re.search(r"\\section\*\{(\d+\.\s*[^}]+)\}", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\\title\{\s*\n?(.+?)\n?\}", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def remove_figure_blocks(text: str) -> str:
    return re.sub(
        r"\\begin\{figure\}.*?\\end\{figure\}", "", text, flags=re.DOTALL | re.IGNORECASE
    )


def flatten_tabular(text: str) -> str:
    """Convert simple LaTeX tables into plain lines."""
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


def _clean_table_line(line: str) -> str:
    line = re.sub(r"\\hline\b", "", line)
    line = line.replace("\\\\", " | ")
    line = re.sub(r"\\multicolumn\{[^}]+\}\{[^}]+\}\{([^}]*)\}", r"\1", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def preprocess(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = remove_figure_blocks(text)
    text = flatten_tabular(text)
    lines = [ln for ln in text.splitlines() if not DROP_LINE_RE.match(ln)]
    return "\n".join(lines)


def slice_exercise_zone(text: str) -> str:
    m_start = EXERCISE_START_RE.search(text)
    if not m_start:
        return text
    zone = text[m_start.start() :]
    m_end = SOLUTIONS_START_RE.search(zone)
    if m_end:
        zone = zone[: m_end.start()]
    return zone


def split_sections(text: str) -> list[tuple[str | None, list[str]]]:
    """Return list of (section_title, lines) including plain blocks with title=None."""
    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw in text.splitlines():
        m = SECTION_HEADER_RE.match(raw.strip())
        if m:
            if current_lines or current_title is not None:
                sections.append((current_title, current_lines))
            current_title = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(raw)

    if current_lines or current_title is not None:
        sections.append((current_title, current_lines))
    return sections


def is_question_section(title: str | None) -> bool:
    if not title:
        return False
    if SKIP_SECTION_RE.search(title):
        return False
    return bool(QUESTION_SECTION_RE.search(title))


def is_passage_section(title: str | None) -> bool:
    return bool(title and title.strip().lower() == "passage")


def is_column_ii_section(title: str | None) -> bool:
    return bool(title and re.match(r"Column\s+II\b", title, re.IGNORECASE))


def _flush(blocks: list[str], buf: list[str]) -> None:
    if buf:
        text = "\n".join(buf).strip()
        if text:
            blocks.append(text)
        buf.clear()


def _is_continuation(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if NUMBERED_Q_RE.match(s):
        return False
    if MCQ_OPTION_RE.match(s):
        return False
    if COLUMN_I_RE.match(s):
        return False
    if COLUMN_II_RE.match(s):
        return False
    if SUBPART_RE.match(s):
        return False
    if DIRECTIONS_RE.match(s):
        return False
    if SECTION_HEADER_RE.match(s):
        return False
    if COLUMN_LABEL_RE.match(s):
        return False
    if SHARED_OPTION_RE.match(s):
        return False
    return True


def parse_section_lines(title: str, lines: list[str]) -> list[str]:
    blocks: list[str] = []
    buf: list[str] = []
    in_shared_options = title and "assertion" in title.lower()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if re.match(r"^Passage\s+Based\s+Questions\b", stripped, re.IGNORECASE):
            _flush(blocks, buf)
            blocks.append(f"\\section*{{{stripped}}}")
            continue

        if DIRECTIONS_RE.match(stripped):
            _flush(blocks, buf)
            blocks.append(stripped)
            continue

        if COLUMN_LABEL_RE.match(stripped):
            _flush(blocks, buf)
            blocks.append(stripped)
            continue

        m_q = NUMBERED_Q_RE.match(stripped)
        if m_q:
            _flush(blocks, buf)
            buf.append(stripped)
            continue

        if MCQ_OPTION_RE.match(stripped):
            if buf:
                buf.append(stripped)
            else:
                _flush(blocks, buf)
                blocks.append(stripped)
            continue

        if COLUMN_I_RE.match(stripped) or COLUMN_II_RE.match(stripped):
            _flush(blocks, buf)
            blocks.append(stripped)
            continue

        if SUBPART_RE.match(stripped):
            if buf:
                buf.append(stripped)
            else:
                _flush(blocks, buf)
                buf.append(stripped)
            continue

        if in_shared_options and SHARED_OPTION_RE.match(stripped):
            _flush(blocks, buf)
            blocks.append(stripped)
            continue

        if REASON_RE.match(stripped) and buf and ASSERTION_IN_Q_RE.search(buf[0]):
            buf.append(stripped)
            continue

        if buf and _is_continuation(line):
            buf.append(stripped)
            continue

        if is_passage_section(title):
            buf.append(stripped)
            continue

    _flush(blocks, buf)
    return blocks


def parse_passage_based_block(title: str, lines: list[str]) -> list[str]:
    """Handle 'Passage Based Questions' text block before \\section*{Passage}."""
    blocks: list[str] = [f"\\section*{{{title}}}"]
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.lower().startswith("passage based"):
            blocks.append(stripped)
    return blocks


def extract_blocks(text: str) -> list[str]:
    text = preprocess(slice_exercise_zone(text))
    sections = split_sections(text)
    output: list[str] = []
    carry_passage_header: list[str] = []

    for title, lines in sections:
        if title and SKIP_SECTION_RE.search(title):
            continue

        if title and title.lower().startswith("passage based"):
            carry_passage_header = parse_passage_based_block(title, lines)
            continue

        if is_passage_section(title):
            if carry_passage_header:
                output.extend(carry_passage_header)
                carry_passage_header = []
            output.append(f"\\section*{{{title}}}")
            passage_text = "\n".join(ln.strip() for ln in lines if ln.strip())
            if passage_text:
                output.append(passage_text)
            continue

        if is_column_ii_section(title):
            if output:
                output.append(f"\\section*{{{title}}}")
            for raw in lines:
                stripped = raw.strip()
                if stripped and COLUMN_II_RE.match(stripped):
                    output.append(stripped)
            continue

        if not is_question_section(title):
            continue

        output.append(f"\\section*{{{title}}}")
        output.extend(parse_section_lines(title, lines))

    return output


def process_text(text: str) -> str:
    title = extract_title(text)
    blocks = extract_blocks(text)
    if not blocks:
        return ""

    parts: list[str] = []
    if title:
        parts.append(f"\\title{{\n{title}\n}}")
    parts.extend(blocks)
    return "\n\n".join(parts) + "\n"


def process_file(input_path: Path, output_dir: Path | None = None) -> Path:
    text = input_path.read_text(encoding="utf-8")
    result = process_text(text)
    out_dir = output_dir or input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{input_path.stem}_qa{input_path.suffix}"
    out_path.write_text(result, encoding="utf-8")
    return out_path


def is_foundation_format(text: str) -> bool:
    if EXERCISE_START_RE.search(text):
        return True
    if re.search(r"\\section\*\{Multiple\s+Choice", text, re.IGNORECASE):
        return True
    if re.search(r"DIRECTIONS\s*:.*multiple\s+choice", text, re.IGNORECASE):
        return True
    return False
