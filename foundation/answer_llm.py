"""LLM batch answer filler — objective questions only, no subjective."""

from __future__ import annotations

import json

from foundation.llm import BATCH_SIZE, DEFAULT_MODEL, chat_json, count_tokens
from foundation.models import FoundationDocument, FoundationQuestion

OBJECTIVE_TYPES = frozenset({
    "MCQ", "MCQ_MULTI", "ASSERTION_REASON", "FIB", "TRUE_FALSE", "INTEGER", "MATCH",
})
SUBJECTIVE_TYPES = frozenset({
    "VSA", "SA", "LA", "DESCRIPTIVE", "TEXTBOOK", "PASSAGE", "CASE_STUDY",
})

ANSWER_SYSTEM = """You are an expert NCERT/Foundation school teacher.
Answer ONLY the objective questions provided. Be accurate for the given class level.

Return JSON only:
{
  "answers": [
    {"qid": "Q1", "answer_key": "d", "explanation": "brief reason"}
  ]
}

Rules:
- MCQ / MCQ_MULTI / ASSERTION_REASON: answer_key is one letter a/b/c/d.
- TRUE_FALSE: answer_key is True or False.
- FIB: answer_key is the blank fill word/phrase.
- INTEGER: answer_key is numeric string.
- MATCH: answer_key is mapping like A->q, B->r.
- Do not rewrite questions. Only answer_key + short explanation."""


def is_objective(q: FoundationQuestion) -> bool:
    return q.question_type in OBJECTIVE_TYPES


def is_subjective(q: FoundationQuestion) -> bool:
    return q.question_type in SUBJECTIVE_TYPES


def needs_llm_answer(q: FoundationQuestion) -> bool:
    if not is_objective(q):
        return False
    if (q.answer_key or "").strip():
        return False
    return True


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _question_payload(q: FoundationQuestion) -> dict:
    opts = q.options or q.shared_options
    return {
        "qid": q.qid,
        "type": q.question_type,
        "stem": q.stem,
        "options": [f"({o.label}) {o.text}" for o in opts] if opts else [],
        "column_a": [f"({o.label}) {o.text}" for o in q.column_a],
        "column_b": [f"({o.label}) {o.text}" for o in q.column_b],
    }


def _build_user_batch(batch: list[FoundationQuestion], doc: FoundationDocument) -> str:
    return json.dumps(
        {
            "subject": doc.subject,
            "class_level": doc.class_level,
            "questions": [_question_payload(q) for q in batch],
        },
        ensure_ascii=False,
    )


def fill_missing_answers(
    doc: FoundationDocument,
    *,
    model: str = DEFAULT_MODEL,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int, dict]:
    """Returns (filled_count, skipped_subjective, token_stats)."""
    missing = [q for q in doc.questions if needs_llm_answer(q)]
    skipped_subjective = sum(
        1 for q in doc.questions
        if is_subjective(q) and not (q.answer_key or "").strip()
    )

    if not missing:
        return 0, skipped_subjective, {
            "input": 0, "output": 0, "total": 0,
            "batch_calls": 0, "model": model, "queued": 0,
        }

    tokens = {"input": 0, "output": 0, "batch_calls": 0, "model": model, "queued": len(missing)}
    filled = 0
    lookup = {q.qid: q for q in missing}

    for batch in _chunks(missing, batch_size):
        user = _build_user_batch(batch, doc)
        try:
            data, usage = chat_json(system=ANSWER_SYSTEM, user=user, model=model)
        except Exception:
            continue

        tokens["input"] += usage["input"]
        tokens["output"] += usage["output"]
        tokens["batch_calls"] += 1

        for item in data.get("answers", []):
            qid = str(item.get("qid", "")).strip()
            q = lookup.get(qid)
            if not q:
                continue
            key = str(item.get("answer_key", "")).strip()
            expl = str(item.get("explanation", "")).strip()
            if not key and not expl:
                continue
            q.answer_key = key
            q.explanation = expl
            q.answer_source = "llm"
            filled += 1

    tokens["total"] = tokens["input"] + tokens["output"]
    return filled, skipped_subjective, tokens


def estimate_llm_tokens(doc: FoundationDocument, model: str = DEFAULT_MODEL) -> dict:
    missing = [q for q in doc.questions if needs_llm_answer(q)]
    skipped = sum(1 for q in doc.questions if is_subjective(q) and not (q.answer_key or "").strip())
    if not missing:
        return {
            "missing_objective": 0,
            "skipped_subjective": skipped,
            "batch_calls": 0,
            "estimated_input_tokens": 0,
            "model": model,
        }

    batch_calls = (len(missing) + BATCH_SIZE - 1) // BATCH_SIZE
    est = count_tokens(ANSWER_SYSTEM, model) * batch_calls
    for batch in _chunks(missing, BATCH_SIZE):
        est += count_tokens(_build_user_batch(batch, doc), model)
    return {
        "missing_objective": len(missing),
        "skipped_subjective": skipped,
        "batch_calls": batch_calls,
        "batch_size": BATCH_SIZE,
        "estimated_input_tokens": est,
        "model": model,
    }
