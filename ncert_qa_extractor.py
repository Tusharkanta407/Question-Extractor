"""
ncert_qa_extractor.py
=====================
Extract questions from NCERT-style textbook .mmd files (Class 6-10).

Keeps: Activities, Exercises, Extended Learning sections.
Skips: theory narrative, KEYWORDS, WHAT YOU HAVE LEARNT, Did You Know.
"""

from __future__ import annotations

import re
from pathlib import Path

from models import ExtractedDocument, Question, QuestionOption
from question_classifier import classify_question

SECTION_HEADER_RE = re.compile(r"^\\section\*\{(.+)\}$")

EXTRACT_SECTION_RE = re.compile(
    r"Activity\s+\d|Exercises|Extended\s+Learning",
    re.IGNORECASE,
)

SKIP_SECTION_RE = re.compile(
    r"KEYWORDS|WHAT YOU HAVE LEARNT|Did You Know|Friendly Microorganisms|"
    r"Making of Curd|Commercial Use|Medicinal Use|Vaccine|Food Preservation|"
    r"Chemical Method|Preservation by|Heat and Cold|Storage and Packing|"
    r"Cleaning the Environment|Disease causing|Food Poisoning|Increasing Soil",
    re.IGNORECASE,
)

DROP_LINE_RE = re.compile(
    r"^\s*\\begin\{|^\s*\\end\{|^\s*\\includegraphics|^\s*!\[|^\s*\\caption",
    re.IGNORECASE,
)

NUMBERED_Q_RE = re.compile(r"^(\d+)\.\s+(.*)")
LETTER_PART_RE = re.compile(r"^\(([a-z])\)\s*(.*)$", re.IGNORECASE)
ROMAN_PART_RE = re.compile(r"^\((i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3})\)\s*(.*)$", re.IGNORECASE)
MATCH_COL_A_RE = re.compile(r"^\(([ivx]+)\)\s*(.*)$", re.IGNORECASE)
MATCH_COL_B_RE = re.compile(r"^\(([a-g])\)\s*(.*)$", re.IGNORECASE)
ACTIVITY_HEADER_RE = re.compile(r"\\section\*\{(Activity\s+[\d.]+)\}", re.IGNORECASE)
THEORY_AFTER_ACTIVITY_RE = re.compile(
    r"^(These |Microorganisms are classified|Viruses are also|You have learnt|"
    r"Yeast reproduces|This is the smell|You often see large|Microorganisms are harmful|"
    r"Microorganisms play an important)",
    re.IGNORECASE,
)


def is_ncert_format(text: str) -> bool:
    if re.search(r"\\section\*\{Exercises\}", text, re.IGNORECASE):
        return True
    if (
        re.search(r"\\section\*\{Activity\s+\d+", text, re.IGNORECASE)
        and re.search(r"\\subsection\*\{", text)
    ):
        return True
    return False


def extract_title(text: str) -> str:
    m = re.search(r"\\section\*\{(\d+[\.\uFF0E]\s*\d*[^}]*)\}", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\\subsection\*\{([^}]+)\}", text)
    if m:
        return m.group(1).strip()
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:120].strip()


def remove_figure_blocks(text: str) -> str:
    text = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\\begin\{table\}.*?\\end\{table\}", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text


def preprocess(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = remove_figure_blocks(text)
    lines = [ln for ln in text.splitlines() if not DROP_LINE_RE.match(ln)]
    text = "\n".join(lines)
    text = re.sub(r"(\\section\*\{[^}]+\})", r"\n\n\1\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    title: str | None = None
    lines: list[str] = []

    for raw in text.splitlines():
        m = SECTION_HEADER_RE.match(raw.strip())
        if m:
            if lines or title is not None:
                sections.append((title, lines))
            title = m.group(1).strip()
            lines = []
        elif raw.strip() or lines:
            lines.append(raw)

    if lines or title is not None:
        sections.append((title, lines))
    return sections


def is_extract_section(title: str | None) -> bool:
    if not title:
        return False
    if SKIP_SECTION_RE.search(title):
        return False
    return bool(EXTRACT_SECTION_RE.search(title))


def _make_id(section: str, number: str, sub_part: str | None, idx: int) -> str:
    sec = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-")[:30]
    sp = f"-{sub_part}" if sub_part else ""
    return f"{sec}-q{number}{sp}" if number else f"{sec}-item{idx}"


def _join_lines(lines: list[str]) -> str:
    return "\n".join(ln.strip() for ln in lines if ln.strip()).strip()


def _trim_activity_lines(lines: list[str]) -> list[str]:
    trimmed: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("\\subsection*{") or stripped.startswith("\\section*{Activity"):
            break
        if stripped.startswith("Fig.") and trimmed:
            break
        if trimmed and any("?" in ln or "？" in ln for ln in trimmed):
            if THEORY_AFTER_ACTIVITY_RE.match(stripped) and not stripped.startswith(">"):
                break
        trimmed.append(stripped if not stripped.startswith(">") else stripped.lstrip("> ").strip())
    return trimmed


def parse_activity(section: str, lines: list[str], start_idx: int) -> Question:
    body_lines = _trim_activity_lines(lines)
    stem = _join_lines(body_lines)
    qtype = classify_question(section, stem)
    return Question(
        id=_make_id(section, "", None, start_idx),
        section=section,
        number="",
        type=qtype,
        stem=stem,
        raw_text=f"\\section*{{{section}}}\n\n{stem}",
        flags={"partial": not stem, "needs_review": False, "convertible": qtype == "SUBJECTIVE"},
    )


def _split_numbered_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if NUMBERED_Q_RE.match(stripped) and current:
            blocks.append(current)
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        blocks.append(current)
    return blocks


def parse_exercise_block(block: list[str], section: str, idx: int) -> list[Question]:
    m = NUMBERED_Q_RE.match(block[0])
    if not m:
        return []

    number = m.group(1)
    header = m.group(2).strip()
    rest = block[1:]
    group_type = classify_question(section, header, header_hint=header)
    questions: list[Question] = []

    if group_type == "FIB":
        for line in rest:
            lm = LETTER_PART_RE.match(line)
            if lm:
                stem = f"{header} ({lm.group(1)}) {lm.group(2)}".strip()
                questions.append(Question(
                    id=_make_id(section, number, lm.group(1).lower(), idx + len(questions)),
                    section=section,
                    number=number,
                    sub_part=lm.group(1).lower(),
                    type="FIB",
                    stem=stem,
                    raw_text=line,
                    flags={"partial": False, "needs_review": False, "convertible": False},
                ))
        return questions

    if group_type == "SCQ":
        current_letter: str | None = None
        current_stem = header
        current_options: list[QuestionOption] = []
        buf_stem: list[str] = []

        def flush_scq() -> None:
            nonlocal current_letter, current_options, buf_stem
            if current_letter is None:
                return
            stem_text = " ".join(buf_stem).strip() or current_stem
            questions.append(Question(
                id=_make_id(section, number, current_letter, idx + len(questions)),
                section=section,
                number=number,
                sub_part=current_letter,
                type="SCQ",
                stem=stem_text,
                options=list(current_options),
                raw_text=_join_lines(buf_stem + [f"({o.label}) {o.text}" for o in current_options]),
                flags={"partial": len(current_options) < 2, "needs_review": False, "convertible": False},
            ))
            current_options = []
            buf_stem = []

        for line in rest:
            lm = LETTER_PART_RE.match(line)
            rm = ROMAN_PART_RE.match(line)
            if lm:
                flush_scq()
                current_letter = lm.group(1).lower()
                buf_stem = [lm.group(2).strip()] if lm.group(2).strip() else []
            elif rm and current_letter:
                current_options.append(QuestionOption(rm.group(1).lower(), rm.group(2).strip()))
            elif current_letter and buf_stem is not None:
                buf_stem.append(line)
        flush_scq()
        return questions

    if group_type == "MATCH":
        col_a: list[QuestionOption] = []
        col_b: list[QuestionOption] = []
        for line in rest:
            if line.strip() in ("A", "B"):
                continue
            ma = MATCH_COL_A_RE.match(line)
            mb = MATCH_COL_B_RE.match(line)
            if ma:
                col_a.append(QuestionOption(ma.group(1).lower(), ma.group(2).strip()))
            elif mb:
                col_b.append(QuestionOption(mb.group(1).lower(), mb.group(2).strip()))

        questions.append(Question(
            id=_make_id(section, number, None, idx),
            section=section,
            number=number,
            type="MATCH",
            stem=header,
            match_column_a=col_a,
            match_column_b=col_b,
            raw_text=_join_lines(block),
            flags={"partial": not col_a or not col_b, "needs_review": False, "convertible": False},
        ))
        return questions

    # SAQ / subjective
    stem = header
    if rest:
        stem = _join_lines([header] + rest)
    qtype = classify_question(section, stem)
    questions.append(Question(
        id=_make_id(section, number, None, idx),
        section=section,
        number=number,
        type=qtype,
        stem=stem,
        raw_text=_join_lines(block),
        flags={"partial": False, "needs_review": False, "convertible": qtype in ("SAQ", "SUBJECTIVE")},
    ))
    return questions


def parse_numbered_section(section: str, lines: list[str], start_idx: int) -> list[Question]:
    questions: list[Question] = []
    for i, block in enumerate(_split_numbered_blocks(lines)):
        m = NUMBERED_Q_RE.match(block[0])
        if not m:
            continue
        number = m.group(1)
        stem = _join_lines(block)
        qtype = classify_question(section, m.group(2))
        questions.append(Question(
            id=_make_id(section, number, None, start_idx + i),
            section=section,
            number=number,
            type=qtype,
            stem=stem,
            raw_text=stem,
            flags={"partial": False, "needs_review": False, "convertible": qtype in ("SAQ", "SUBJECTIVE", "PROJECT")},
        ))
    return questions


def extract_activities(processed: str, start_idx: int) -> tuple[list[Question], int]:
    questions: list[Question] = []
    matches = list(ACTIVITY_HEADER_RE.finditer(processed))
    idx = start_idx

    for i, m in enumerate(matches):
        section = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(processed)
        chunk = processed[start:end]
        chunk = re.split(r"\\subsection\*\{", chunk, maxsplit=1)[0]
        lines = chunk.splitlines()
        questions.append(parse_activity(section, lines, idx))
        idx += 1

    return questions, idx


def extract_document(text: str, source_file: str = "") -> ExtractedDocument:
    processed = preprocess(text)
    title = extract_title(text)
    questions: list[Question] = []
    idx = 0

    act_questions, idx = extract_activities(processed, idx)
    questions.extend(act_questions)

    for sec_title, lines in split_sections(processed):
        if not is_extract_section(sec_title):
            continue

        if sec_title and re.search(r"Activity\s+\d", sec_title, re.IGNORECASE):
            continue
        elif sec_title and re.search(r"Exercises", sec_title, re.IGNORECASE):
            for block in _split_numbered_blocks(lines):
                parsed = parse_exercise_block(block, sec_title, idx)
                questions.extend(parsed)
                idx += len(parsed)
        elif sec_title and re.search(r"Extended\s+Learning", sec_title, re.IGNORECASE):
            parsed = parse_numbered_section(sec_title, lines, idx)
            questions.extend(parsed)
            idx += len(parsed)

    return ExtractedDocument(
        title=title,
        source_format="ncert",
        source_file=source_file,
        questions=questions,
    )


def document_to_mmd(doc: ExtractedDocument) -> str:
    parts: list[str] = []
    if doc.title:
        parts.append(f"\\title{{\n{doc.title}\n}}")

    current_section = ""
    for q in doc.questions:
        if q.section != current_section:
            current_section = q.section
            parts.append(f"\\section*{{{current_section}}}")

        block_lines = [q.raw_text or q.stem]
        if q.options:
            block_lines.extend(f"({o.label}) {o.text}" for o in q.options)
        if q.match_column_a:
            block_lines.append("Column A")
            block_lines.extend(f"({o.label}) {o.text}" for o in q.match_column_a)
        if q.match_column_b:
            block_lines.append("Column B")
            block_lines.extend(f"({o.label}) {o.text}" for o in q.match_column_b)
        parts.append("\n".join(block_lines))

    return "\n\n".join(parts) + "\n" if parts else ""


def process_text(text: str) -> str:
    return document_to_mmd(extract_document(text))
