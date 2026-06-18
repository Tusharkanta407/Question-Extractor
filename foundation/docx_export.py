"""Export Foundation question bank to .docx."""

from __future__ import annotations

from io import BytesIO

from foundation.formatter import _clean_latex, _type_label
from foundation.models import FoundationDocument, FoundationQuestion


def document_to_docx_bytes(doc: FoundationDocument) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor

    d = Document()
    title = doc.title.upper()
    if "QUESTION BANK" not in title:
        title = f"{title} - QUESTION BANK"

    h = d.add_heading(title, level=0)
    h.runs[0].font.size = Pt(16)

    sub = d.add_paragraph(
        f"Foundation {doc.subject} | Class {doc.class_level} | "
        f"Total Questions: {len(doc.questions)}"
    )
    sub.runs[0].font.size = Pt(11)
    sub.runs[0].font.color.rgb = RGBColor(0x5C, 0x6B, 0x7A)

    current_section = ""
    seq = 0

    for q in doc.questions:
        if q.section != current_section:
            current_section = q.section
            d.add_paragraph()
            sec = d.add_heading(q.section, level=1)
            sec.runs[0].font.size = Pt(13)
            if q.directions:
                p = d.add_paragraph(q.directions)
                p.runs[0].italic = True
                p.runs[0].font.size = Pt(9)
            if q.passage:
                p = d.add_paragraph(f"Passage: {_clean_latex(q.passage)}")
                p.runs[0].font.size = Pt(10)

        seq += 1
        _add_question(d, q, seq)

    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def _add_question(d, q: FoundationQuestion, seq: int) -> None:
    from docx.shared import Pt, RGBColor

    label = _type_label(q.question_type)
    p = d.add_paragraph()
    run = p.add_run(f"Q{seq}. [{label}]  ")
    run.bold = True
    run.font.size = Pt(11)
    p.add_run(_clean_latex(q.stem.replace("\n", " "))).font.size = Pt(11)

    opts = q.options or q.shared_options
    for o in opts:
        op = d.add_paragraph(f"({o.label}) {_clean_latex(o.text)}", style="List Bullet")
        op.paragraph_format.left_indent = Pt(18)
        op.runs[0].font.size = Pt(10)

    if q.column_a:
        d.add_paragraph("Column I").runs[0].bold = True
        for o in q.column_a:
            d.add_paragraph(f"({o.label}) {_clean_latex(o.text)}", style="List Bullet")
    if q.column_b:
        d.add_paragraph("Column II").runs[0].bold = True
        for o in q.column_b:
            d.add_paragraph(f"({o.label}) {_clean_latex(o.text)}", style="List Bullet")

    if q.answer_key:
        ak = q.answer_key
        if q.question_type in ("MCQ", "MCQ_MULTI", "ASSERTION_REASON") and len(ak) == 1:
            ak = f"({ak.lower()})"
        ap = d.add_paragraph()
        ar = ap.add_run(f"Correct Answer: {ak}")
        ar.bold = True
        ar.font.color.rgb = RGBColor(0x0F, 0x76, 0x6E)

    if q.explanation:
        src = " (LLM)" if q.answer_source == "llm" else ""
        ep = d.add_paragraph()
        er = ep.add_run(f"Explanation{src}: ")
        er.bold = True
        ep.add_run(_clean_latex(q.explanation))

    d.add_paragraph()
