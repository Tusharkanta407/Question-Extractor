"""Format Foundation document as question-bank .mmd text."""

from __future__ import annotations

import re

from foundation.models import FoundationDocument, FoundationQuestion, QuestionOption

_LINE = "─" * 72
_HEADER_EQ = "=" * 70


def _clean_latex(text: str) -> str:
    text = re.sub(r"\$\$([^$]+)\$\$", r"\1", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\xrightarrow\{[^}]*\}", " -> ", text)
    text = re.sub(r"\\longrightarrow", " -> ", text)
    text = re.sub(r"\\rightarrow", " -> ", text)
    text = re.sub(r"\\_", "_", text)
    text = re.sub(r"\\\s+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _type_label(qtype: str) -> str:
    return qtype.replace("_", " ")


def _format_options(options: list[QuestionOption], indent: str = "  ") -> list[str]:
    return [f"{indent}({o.label}) {_clean_latex(o.text)}" for o in options]


def _format_question(q: FoundationQuestion, seq: int) -> list[str]:
    lines: list[str] = []
    label = _type_label(q.question_type)
    stem = _clean_latex(q.stem.replace("\n", " "))
    lines.append(f"Q{seq}. [{label}]  {stem}")

    opts = q.options or q.shared_options
    lines.extend(_format_options(opts))

    if q.column_a:
        lines.append("  Column I")
        lines.extend(_format_options(q.column_a, indent="    "))
    if q.column_b:
        lines.append("  Column II")
        lines.extend(_format_options(q.column_b, indent="    "))

    if q.answer_key:
        ak = q.answer_key
        if q.question_type in ("MCQ", "MCQ_MULTI", "ASSERTION_REASON") and len(ak) == 1:
            ak = f"({ak.lower()})"
        lines.append(f"  ► Correct Answer: {ak}")
    if q.explanation:
        src = " [LLM]" if q.answer_source == "llm" else ""
        lines.append(f"  ★ Explanation{src}: {_clean_latex(q.explanation)}")

    return lines


def format_question_bank(doc: FoundationDocument) -> str:
    title_upper = doc.title.upper()
    if "QUESTION BANK" not in title_upper:
        title_line = f"  {title_upper} - QUESTION BANK"
    else:
        title_line = f"  {title_upper}"

    parts: list[str] = [
        _HEADER_EQ,
        title_line,
        f"  Foundation {doc.subject} | Class {doc.class_level}",
        f"  Total Questions: {len(doc.questions)}",
        _HEADER_EQ,
        "",
    ]

    current_section = ""
    seq = 0

    for q in doc.questions:
        section_label = q.section
        if q.exercise:
            section_label = f"{q.exercise} › {section_label}"
        if q.subsection:
            section_label = f"{q.subsection} › {section_label}"

        if section_label != current_section:
            current_section = section_label
            parts.extend(["", _LINE, f"  SECTION: {q.section.upper()}", _LINE, ""])
            if q.directions:
                parts.append(f"  {q.directions}")
                parts.append("")
            if q.passage:
                parts.append(f"  Passage: {_clean_latex(q.passage)}")
                parts.append("")

        seq += 1
        parts.extend(_format_question(q, seq))
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def output_filename(stem: str, ext: str = "mmd") -> str:
    base = stem.replace("_qa", "")
    return f"{base}_question_bank.{ext.lstrip('.')}"
