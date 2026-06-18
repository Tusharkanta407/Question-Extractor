"""Adapt FoundationDocument for shared export interfaces."""

from __future__ import annotations

from foundation.formatter import format_question_bank
from foundation.models import FoundationDocument, FoundationQuestion
from models import ExtractedDocument, Question, QuestionOption


def foundation_to_extracted(doc: FoundationDocument) -> ExtractedDocument:
    questions: list[Question] = []
    for i, fq in enumerate(doc.questions):
        opts = [QuestionOption(o.label, o.text) for o in (fq.options or fq.shared_options)]
        stem = fq.stem
        if fq.passage:
            stem = f"[Passage] {fq.passage}\n\n{stem}"
        questions.append(
            Question(
                id=f"foundation-{fq.qid}",
                section=fq.section,
                number=str(fq.qnum),
                type=fq.question_type,
                stem=stem,
                options=opts,
                match_column_a=[QuestionOption(o.label, o.text) for o in fq.column_a],
                match_column_b=[QuestionOption(o.label, o.text) for o in fq.column_b],
                raw_text=stem,
                flags={
                    "partial": False,
                    "needs_review": not bool(fq.answer_key),
                    "convertible": False,
                },
            )
        )
    return ExtractedDocument(
        title=doc.title,
        source_format="foundation",
        source_file=doc.source_file,
        questions=questions,
    )


def foundation_plain_text(doc: FoundationDocument) -> str:
    return format_question_bank(doc)
