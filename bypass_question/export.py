"""Export converted bypass questions to JSON and plain text."""

from __future__ import annotations

import json

from bypass_question.models import ConversionResult, ConvertedQuestion


def questions_to_json(questions: list[ConvertedQuestion], *, indent: int = 2) -> str:
    payload = [q.to_dict() for q in questions]
    return json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"


def result_to_json(result: ConversionResult, *, indent: int = 2) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=indent) + "\n"


def question_to_plain_text(q: ConvertedQuestion) -> str:
    lines = [
        f"[{q.question_id}] ({q.questionType.upper()}) {q.qid}",
        f"Level: {q.level} | Confidence: {q.confidence}",
        "",
        "Question:",
        q.question_content,
        "",
        f"Answer: {q.answer_key}",
        "",
        "Solution:",
        q.solution_content,
    ]
    if q.needs_review:
        lines.append("")
        lines.append("*** needs_review ***")
    return "\n".join(lines)


def questions_to_plain_text(questions: list[ConvertedQuestion]) -> str:
    blocks = [question_to_plain_text(q) for q in questions]
    return ("\n\n" + ("=" * 60) + "\n\n").join(blocks) + "\n"


def output_filename(stem: str, ext: str) -> str:
    base = stem.replace("_rephrase", "")
    return f"{base}_converted.{ext.lstrip('.')}"
