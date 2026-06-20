"""Export Foundation document to .docx format."""

from __future__ import annotations

import random
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from foundation.models import FoundationDocument, FoundationQuestion, QuestionOption

_NONNEG_NUMERIC_RE = re.compile(r"^\+?\d+(\.\d+)?$")


def _is_nonneg_numeric(value: str) -> bool:
    return bool(_NONNEG_NUMERIC_RE.match(value.strip()))


def _build_fib_pool(doc: FoundationDocument) -> list[str]:
    return [
        q.answer_key.strip()
        for q in doc.questions
        if q.question_type == "FIB"
        and (q.answer_key or "").strip()
        and not _is_nonneg_numeric(q.answer_key.strip())
    ]


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
        correct_display = f"({correct_label})"

    return q_type, opts, correct_display


def _clean_latex(text: str) -> str:
    text = re.sub(r"\$\$([^$]+)\$\$", r"\1", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\rightarrow|\\longrightarrow|\\xrightarrow\{[^}]*\}", " -> ", text)
    text = re.sub(r"\\\s+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def export_docx(doc: FoundationDocument, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    docx = Document()

    # Title
    title = docx.add_heading(doc.title, level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = docx.add_paragraph(f"Foundation {doc.subject} | Class {doc.class_level}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    fib_pool = _build_fib_pool(doc)
    current_section = ""
    seq = 0

    for q in doc.questions:
        section_label = q.section

        if section_label != current_section:
            current_section = section_label
            docx.add_heading(q.section, level=2)

            if q.directions:
                p = docx.add_paragraph(q.directions)
                p.runs[0].italic = True

            if q.passage:
                docx.add_paragraph(f"Passage: {_clean_latex(q.passage)}")

        was_fib = q.question_type == "FIB"
        q_type, opts, correct_display = _resolve_question(q, fib_pool)
        seq += 1

        # Question stem
        stem_text = _clean_latex(q.stem.replace("\n", " "))
        p = docx.add_paragraph()
        run = p.add_run(f"Q{seq}. [{q_type}]  {stem_text}")
        run.bold = True

        # Options
        for opt in opts:
            docx.add_paragraph(
                f"  ({opt.label}) {_clean_latex(opt.text)}",
                style="List Bullet"
            )

        # Column A / B (matching type)
        if q.column_a:
            docx.add_paragraph("  Column I")
            for opt in q.column_a:
                docx.add_paragraph(f"    ({opt.label}) {_clean_latex(opt.text)}")
        if q.column_b:
            docx.add_paragraph("  Column II")
            for opt in q.column_b:
                docx.add_paragraph(f"    ({opt.label}) {_clean_latex(opt.text)}")

        # Correct answer
        if correct_display:
            p = docx.add_paragraph()
            run = p.add_run(f"► Correct Answer: {correct_display}")
            run.font.color.rgb = RGBColor(0x00, 0x80, 0x00)
            run.bold = True

        # Explanation
        if q.explanation:
            src = " [LLM]" if q.answer_source == "llm" else ""
            p = docx.add_paragraph()
            run = p.add_run(f"★ Explanation{src}: {_clean_latex(q.explanation)}")
            run.font.color.rgb = RGBColor(0x44, 0x44, 0x88)
            run.italic = True

    docx.save(out_path)
    return out_path
