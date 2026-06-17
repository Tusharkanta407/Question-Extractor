"""Export ExtractedDocument to txt, docx, json, and mmd."""

from __future__ import annotations

import json
import re
from io import BytesIO

from export_formats import _clean_latex_inline, to_docx_bytes, to_plain_text
from models import ExtractedDocument, Question
from question_classifier import classify_question

SECTION_RE = re.compile(r"^\\section\*\{([^}]+)\}$")


def mmd_to_document(mmd_text: str, source_format: str, title: str = "", source_file: str = "") -> ExtractedDocument:
    """Convert legacy mmd extractor output into structured document."""
    questions: list[Question] = []
    current_section = ""
    idx = 0

    for block in [b.strip() for b in mmd_text.split("\n\n") if b.strip()]:
        lines = block.splitlines()
        first = lines[0].strip()
        m_sec = SECTION_RE.match(first)
        if m_sec and len(lines) == 1:
            current_section = m_sec.group(1)
            continue
        if m_sec:
            current_section = m_sec.group(1)
            body = "\n".join(lines[1:]).strip()
        else:
            body = block

        if not body:
            continue

        options = []
        stem_lines = []
        for line in body.splitlines():
            stripped = line.strip()
            om = re.match(r"^\(([a-d])\)\s+(.*)$", stripped, re.IGNORECASE)
            if om:
                options.append({"label": om.group(1).lower(), "text": om.group(2)})
            else:
                stem_lines.append(stripped)

        stem = "\n".join(stem_lines).strip()
        if stem.startswith("Answer:"):
            qtype = "ANSWER"
        else:
            qtype = classify_question(current_section, stem, has_options=bool(options))

        from models import QuestionOption

        questions.append(Question(
            id=f"{source_format}-{idx}",
            section=current_section or "General",
            number=str(idx + 1),
            type=qtype,
            stem=stem,
            options=[QuestionOption(o["label"], o["text"]) for o in options],
            raw_text=body,
            flags={"partial": False, "needs_review": False, "convertible": False},
        ))
        idx += 1

    return ExtractedDocument(
        title=title,
        source_format=source_format,
        source_file=source_file,
        questions=questions,
    )


def document_to_plain_text(doc: ExtractedDocument) -> str:
    if doc.source_format == "ncert" and doc.questions:
        parts: list[str] = []
        if doc.title:
            parts.extend([doc.title, "=" * min(60, max(len(doc.title), 20)), ""])
        current = ""
        for q in doc.questions:
            if q.section != current:
                current = q.section
                parts.extend(["", current.upper(), "-" * len(current)])
            label = f"{q.number}." if q.number else ""
            sp = f"({q.sub_part}) " if q.sub_part else ""
            parts.append(f"{label}{sp}[{q.type}] {_clean_latex_inline(q.stem)}")
            for o in q.options:
                parts.append(f"  ({o.label}) {_clean_latex_inline(o.text)}")
            for o in q.match_column_a:
                parts.append(f"  ({o.label}) {_clean_latex_inline(o.text)}")
            for o in q.match_column_b:
                parts.append(f"  ({o.label}) {_clean_latex_inline(o.text)}")
        return "\n".join(parts).strip() + "\n"

    return to_plain_text(document_to_mmd_simple(doc))


def document_to_mmd_simple(doc: ExtractedDocument) -> str:
    from ncert_qa_extractor import document_to_mmd
    return document_to_mmd(doc)


def document_to_docx_bytes(doc: ExtractedDocument) -> bytes:
    return to_docx_bytes(document_to_mmd_simple(doc), title=doc.title)


def document_to_json(doc: ExtractedDocument, *, indent: int = 2) -> str:
    return json.dumps(doc.to_dict(), ensure_ascii=False, indent=indent) + "\n"


def document_to_json_bytes(doc: ExtractedDocument) -> bytes:
    return document_to_json(doc).encode("utf-8")


def output_filename(stem: str, ext: str) -> str:
    return f"{stem}_qa.{ext.lstrip('.')}"
