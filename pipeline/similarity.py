"""Stage: compare embeddings against an uploaded/reference question bank,
drop duplicates, and drop near-duplicates within the batch itself.

Two comparisons happen here:
1. Against an external reference set ("uploaded questions" - e.g. an
   existing question bank you don't want to re-add duplicates into).
2. Within the newly extracted batch itself (two chapters can yield the
   same question).
"""

from __future__ import annotations

import math

from pipeline.models import PipelineQuestion

DEFAULT_DUPLICATE_THRESHOLD = 0.93  # cosine similarity >= this => duplicate


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _best_match(
    query: PipelineQuestion, candidates: list[PipelineQuestion]
) -> tuple[PipelineQuestion | None, float]:
    best_q = None
    best_score = -1.0
    for cand in candidates:
        if cand is query or cand.embedding is None:
            continue
        score = cosine_similarity(query.embedding, cand.embedding)
        if score > best_score:
            best_score = score
            best_q = cand
    return best_q, best_score


def find_similar_to_uploaded(
    questions: list[PipelineQuestion],
    uploaded_questions: list[PipelineQuestion],
    *,
    threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
) -> list[PipelineQuestion]:
    """Compare each new question against the uploaded/reference bank.

    Sets `.similarity_match` and `.dropped_reason = "duplicate"` on matches
    at/above threshold. Does not remove anything from the list (caller
    decides whether to filter using `drop_flagged`).
    """
    for q in questions:
        if q.embedding is None:
            continue
        match, score = _best_match(q, uploaded_questions)
        if match is not None and score >= threshold:
            q.similarity_match = {
                "matched_qid": match.qid,
                "matched_content": match.question_content,
                "score": round(score, 4),
                "against": "uploaded",
            }
            q.dropped_reason = "duplicate"
    return questions


def find_internal_duplicates(
    questions: list[PipelineQuestion],
    *,
    threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
) -> list[PipelineQuestion]:
    """Flag near-duplicates within the batch itself.

    Keeps the first occurrence, flags later ones as duplicates of the
    earlier one. Only questions not already dropped are considered.
    """
    kept: list[PipelineQuestion] = []
    for q in questions:
        if q.dropped_reason or q.embedding is None:
            continue
        match, score = _best_match(q, kept)
        if match is not None and score >= threshold:
            q.similarity_match = {
                "matched_qid": match.qid,
                "matched_content": match.question_content,
                "score": round(score, 4),
                "against": "batch",
            }
            q.dropped_reason = "duplicate"
        else:
            kept.append(q)
    return questions


def drop_flagged(questions: list[PipelineQuestion]) -> tuple[list[PipelineQuestion], list[PipelineQuestion]]:
    """Split into (kept, dropped) based on `.dropped_reason`."""
    kept = [q for q in questions if not q.dropped_reason]
    dropped = [q for q in questions if q.dropped_reason]
    return kept, dropped


def dedup_pipeline(
    questions: list[PipelineQuestion],
    uploaded_questions: list[PipelineQuestion] | None = None,
    *,
    threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
) -> tuple[list[PipelineQuestion], list[PipelineQuestion]]:
    """Full dedup: drop empties, compare to uploaded bank, then internal dupes.

    Returns (kept, dropped).
    """
    for q in questions:
        if not q.question_content.strip():
            q.dropped_reason = "empty"

    if uploaded_questions:
        find_similar_to_uploaded(questions, uploaded_questions, threshold=threshold)

    find_internal_duplicates(questions, threshold=threshold)

    return drop_flagged(questions)
