"""Format Foundation document as question-bank .mmd text."""

from __future__ import annotations

import re
import random

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


_NONNEG_NUMERIC_RE = re.compile(r"^\+?\d+(\.\d+)?$")


def _is_nonneg_numeric(value: str) -> bool:
    return bool(_NONNEG_NUMERIC_RE.match(value.strip()))


def _build_fib_options(correct: str, pool: list[str]) -> tuple[list[QuestionOption], str]:
    """Build 4 MCQ options. Correct answer placed randomly in (a-d)."""
    distractors = [p for p in pool if p.lower() != correct.lower()]
    random.shuffle(distractors)
    distractors = distractors[:3]
    while len(distractors) < 3:
        distractors.append("___")

    labels = ["a", "b", "c", "d"]
    correct_pos = random.randint(0, 3)
    options: list[QuestionOption] = []
    di = 0
    for i, label in enumerate(labels):
        if i == correct_pos:
            options.append(QuestionOption(label=label, text=correct))
        else:
            options.append(QuestionOption(label=label, text=distractors[di]))
            di += 1
    return options, labels[correct_pos]


def _build_fib_pool(doc: FoundationDocument) -> list[str]:
    return [
        q.answer_key.strip()
        for q in doc.questions
        if q.question_type == "FIB"
        and (q.answer_key or "").strip()
        and not _is_nonneg_numeric(q.answer_key.strip())
    ]


def _resolve_question(
    q: FoundationQuestion, fib_pool: list[str]
) -> tuple[str, list[QuestionOption], str]:
    """Returns (effective_type, effective_options, correct_display)."""
    answer_key = (q.answer_key or "").strip()
    q_type = q.question_type
    opts = list(q.options or q.shared_options)
    correct_display = answer_key

    if q_type == "FIB" and answer_key and not _is_nonneg_numeric(answer_key):
        q_type = "SCQ"
        opts, correct_label = _build_fib_options(answer_key, fib_pool)
        correct_display = correct_label  # letter like "b"

    return q_type, opts, correct_display


def _format_options(options: list[QuestionOption], indent: str = "  ") -> list[str]:
    return [f"{indent}({o.label}) {_clean_latex(o.text)}" for o in options]


def _format_question(q: FoundationQuestion, seq: int, fib_pool: list[str]) -> list[str]:
    lines: list[str] = []
    was_fib = q.question_type == "FIB"

    q_type, opts, correct_display = _resolve_question(q, fib_pool)
    label = _type_label(q_type)
    stem = _clean_latex(q.stem.replace("\n", " "))
    lines.append(f"Q{seq}. [{label}]  {stem}")

    lines.extend(_format_options(opts))

    if q.column_a:
        lines.append("  Column I")
        lines.extend(_format_options(q.column_a, indent="    "))
    if q.column_b:
        lines.append("  Column II")
        lines.extend(_format_options(q.column_b, indent="    "))

    if correct_display:
        if was_fib and q_type == "SCQ":
            lines.append(f"  ► Correct Answer: ({correct_display})")
        else:
            lines.append(f"  ► Correct Answer: {correct_display}")

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

    fib_pool = _build_fib_pool(doc)
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
        parts.extend(_format_question(q, seq, fib_pool))
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def output_filename(stem: str, ext: str = "mmd") -> str:
    base = stem.replace("_qa", "")
    return f"{base}_question_bank.{ext.lstrip('.')}"
