"""Batch LLM conversion of bypass questions to SCQ / MCQ / INTEGER."""

from __future__ import annotations

import json
import math
import os

from bypass_question.llm import DEFAULT_MODEL, chat_json, count_tokens
from bypass_question.models import (
    ConversionResult,
    ConvertedQuestion,
    ParsedBypassFile,
    ParsedQuestion,
    TokenStats,
)
from bypass_question.parser import make_qid

BATCH_SIZE = int(os.getenv("BYPASS_BATCH_SIZE", "8"))

BATCH_SYSTEM = """You are an NCERT science question converter for Indian school students.

You receive a batch of subjective bypass questions. For EACH question:

1. Decide if it can be fairly converted to SCQ, MCQ, or INTEGER without changing the core meaning.
2. If YES → pick the best type, convert, and add to "questions".
3. If NO (e.g. "write 10 lines", "draw a diagram", long essay, cannot be made objective) → add only the question_id to "eliminated". Do NOT force-convert. Do NOT rewrite or change those questions.

Return JSON only:
{
  "questions": [
    {
      "question_id": "Q3a",
      "questionType": "scq|mcq|integer",
      "question_content": "stem with (A)(B)(C)(D) for scq/mcq",
      "answer_key": "A|B|C|D or numeric string for integer",
      "solution_content": "clear explanation",
      "level": "EASY|MEDIUM|HARD",
      "needs_review": false,
      "confidence": 0.85
    }
  ],
  "eliminated": ["Q7"]
}

Rules:
- scq/mcq: exactly 4 options labelled (A) (B) (C) (D), one correct answer.
- integer: no options; answer_key is a single integer as string.
- needs_review: true if conversion is uncertain.
- eliminated: question_ids only — omit anything that cannot be fairly converted.
- Keep scientific accuracy for NCERT syllabus."""


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _build_batch_user(
    batch: list[ParsedQuestion],
    parsed: ParsedBypassFile,
    *,
    force_type: str | None = None,
) -> str:
    payload = {
        "source": parsed.source,
        "subject": parsed.subject,
        "class_level": parsed.class_level,
        "questions": [
            {
                "question_id": q.question_id,
                "stem": q.stem,
                "line_start": q.line_start,
                "line_end": q.line_end,
            }
            for q in batch
        ],
    }
    if force_type:
        payload["force_type"] = force_type.lower()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _lookup_lines(batch: list[ParsedQuestion]) -> dict[str, ParsedQuestion]:
    return {q.question_id: q for q in batch}


def _item_to_converted(
    item: dict,
    parsed: ParsedBypassFile,
    lookup: dict[str, ParsedQuestion],
) -> ConvertedQuestion | None:
    qid = str(item.get("question_id", "")).strip()
    if not qid or qid not in lookup:
        return None

    orig = lookup[qid]
    qtype = str(item.get("questionType", "scq")).lower()
    answer_key = str(item.get("answer_key", "")).strip()
    if qtype == "integer":
        answer_key = "".join(ch for ch in answer_key if ch.isdigit() or ch == "-") or answer_key

    return ConvertedQuestion(
        qid=make_qid(parsed.source, parsed.subject, qid),
        source=parsed.source,
        subject=parsed.subject,
        question_id=qid,
        questionType=qtype,
        answer_key=answer_key,
        level=str(item.get("level", "EASY")).upper(),
        class_level=parsed.class_level,
        question_content=str(item.get("question_content", "")).strip(),
        solution_content=str(item.get("solution_content", "")).strip(),
        line_start=orig.line_start,
        line_end=orig.line_end,
        needs_review=bool(item.get("needs_review", False)),
        confidence=round(float(item.get("confidence", 0.5)), 3),
    )


def convert_batch(
    batch: list[ParsedQuestion],
    parsed: ParsedBypassFile,
    *,
    model: str = DEFAULT_MODEL,
    force_type: str | None = None,
) -> tuple[list[ConvertedQuestion], list[dict], dict]:
    """One LLM call for a batch. Returns (converted, eliminated, token_usage)."""
    if not batch:
        return [], [], {"input": 0, "output": 0}

    lookup = _lookup_lines(batch)
    system = BATCH_SYSTEM.replace("{class_level}", str(parsed.class_level)).replace(
        "{subject}", parsed.subject
    )
    user = _build_batch_user(batch, parsed, force_type=force_type)

    data, usage = chat_json(system=system, user=user, model=model)

    converted: list[ConvertedQuestion] = []
    for item in data.get("questions", []):
        cq = _item_to_converted(item, parsed, lookup)
        if cq and cq.question_content and cq.answer_key:
            converted.append(cq)

    eliminated: list[dict] = []
    for eid in data.get("eliminated", []):
        eid = str(eid).strip()
        if eid in lookup:
            eliminated.append({"question_id": eid, "stem": lookup[eid].stem})

    # Any batch question neither converted nor eliminated → treat as eliminated
    done_ids = {q.question_id for q in converted} | {e["question_id"] for e in eliminated}
    for q in batch:
        if q.question_id not in done_ids:
            eliminated.append({"question_id": q.question_id, "stem": q.stem})

    return converted, eliminated, usage


def convert_single(
    question: ParsedQuestion,
    parsed: ParsedBypassFile,
    *,
    model: str = DEFAULT_MODEL,
    question_type: str | None = None,
) -> tuple[ConvertedQuestion | None, dict]:
    """Single-question convert (for regenerate button)."""
    converted, eliminated, usage = convert_batch(
        [question],
        parsed,
        model=model,
        force_type=question_type,
    )
    if converted:
        return converted[0], usage
    return None, usage


def run_pipeline(
    parsed: ParsedBypassFile,
    *,
    model: str = DEFAULT_MODEL,
    batch_size: int = BATCH_SIZE,
) -> ConversionResult:
    tokens = TokenStats()
    converted: list[ConvertedQuestion] = []
    eliminated: list[dict] = []
    batch_calls = 0

    valid = [q for q in parsed.questions if q.stem.strip()]
    for empty in parsed.questions:
        if not empty.stem.strip():
            eliminated.append({"question_id": empty.question_id, "stem": ""})

    for batch in _chunks(valid, batch_size):
        try:
            items, elim, usage = convert_batch(batch, parsed, model=model)
            converted.extend(items)
            eliminated.extend(elim)
            tokens.conversion_input += usage["input"]
            tokens.conversion_output += usage["output"]
            batch_calls += 1
        except Exception as exc:
            for q in batch:
                eliminated.append(
                    {"question_id": q.question_id, "stem": q.stem, "error": str(exc)}
                )

    result = ConversionResult(
        source=parsed.source,
        subject=parsed.subject,
        class_level=parsed.class_level,
        source_file=parsed.source_file,
        questions=converted,
        skipped=eliminated,
        tokens=tokens,
        model=model,
    )
    result.batch_calls = batch_calls
    result.input_question_count = len(parsed.questions)
    return result


def estimate_tokens_for_file(
    parsed: ParsedBypassFile,
    model: str = DEFAULT_MODEL,
    batch_size: int = BATCH_SIZE,
) -> dict:
    """Pre-run token estimate using tiktoken (no API call)."""
    valid = [q for q in parsed.questions if q.stem.strip()]
    num_batches = max(1, math.ceil(len(valid) / batch_size)) if valid else 0
    system_tokens = count_tokens(BATCH_SYSTEM, model)

    batch_tokens = 0
    for batch in _chunks(valid, batch_size):
        user = _build_batch_user(batch, parsed)
        batch_tokens += count_tokens(user, model)

    # Old way: 2 calls per question (analysis + convert) with repeated system prompt
    old_estimate = len(valid) * (count_tokens(BATCH_SYSTEM, model) + 200) * 2
    new_estimate = num_batches * system_tokens + batch_tokens

    return {
        "questions": len(parsed.questions),
        "batch_size": batch_size,
        "batch_calls": num_batches,
        "estimated_input_tokens": new_estimate,
        "estimated_old_tokens": old_estimate,
        "token_saving_pct": round(
            (1 - new_estimate / old_estimate) * 100, 1
        ) if old_estimate else 0,
        "model": model,
    }
