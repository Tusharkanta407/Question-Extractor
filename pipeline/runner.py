"""Orchestrates the full post-extraction pipeline:

  embeddings -> similarity-vs-uploaded -> drop duplicates -> clean
  -> MathML conversion -> competitive tagging -> JSON output

Entry point: run_pipeline(questions, uploaded_questions=...)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.cleaner import clean_questions
from pipeline.embeddings import embed_questions
from pipeline.mathml import convert_questions_mathml
from pipeline.models import PipelineQuestion, question_from_dict
from pipeline.similarity import DEFAULT_DUPLICATE_THRESHOLD, dedup_pipeline
from pipeline.tagger import tag_questions


@dataclass
class PipelineRunResult:
    kept: list[PipelineQuestion] = field(default_factory=list)
    dropped: list[PipelineQuestion] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stats": self.stats,
            "question_count": len(self.kept),
            "dropped_count": len(self.dropped),
            "questions": [q.to_dict() for q in self.kept],
            "dropped": [
                {
                    "qid": q.qid,
                    "question_content": q.question_content,
                    "dropped_reason": q.dropped_reason,
                    "similarity_match": q.similarity_match,
                }
                for q in self.dropped
            ],
        }


def run_pipeline(
    raw_questions: list[dict],
    *,
    uploaded_questions: list[dict] | None = None,
    similarity_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    embed_model: str | None = None,
    tag_model: str | None = None,
    skip_embeddings: bool = False,
    force_rule_based_tagging: bool = False,
) -> PipelineRunResult:
    """Run the full pipeline on a list of already-extracted/classified
    question dicts (e.g. from ConversionResult.to_dict()["questions"]).

    `uploaded_questions` is the reference bank to check duplicates against
    (e.g. an existing question bank already in your system) - also a list
    of dicts in the same shape.
    """
    questions = [question_from_dict(d) for d in raw_questions]
    uploaded = [question_from_dict(d) for d in (uploaded_questions or [])]

    stats = {"input_count": len(questions), "uploaded_reference_count": len(uploaded)}

    # 1. Embeddings (skip if explicitly disabled, e.g. for offline testing)
    if not skip_embeddings and questions:
        kwargs = {}
        if embed_model:
            kwargs["model"] = embed_model
        embed_questions(questions, **kwargs)
        if uploaded:
            embed_questions(uploaded, **kwargs)
    stats["embedded_count"] = sum(1 for q in questions if q.embedding is not None)

    # 2 & 3. Similarity vs uploaded + drop duplicates (also drops empties)
    kept, dropped = dedup_pipeline(questions, uploaded, threshold=similarity_threshold)
    stats["dropped_duplicate_count"] = sum(1 for q in dropped if q.dropped_reason == "duplicate")
    stats["dropped_empty_count"] = sum(1 for q in dropped if q.dropped_reason == "empty")

    # 4. Clean remaining questions
    kept = clean_questions(kept)

    # 5. MathML conversion
    kept = convert_questions_mathml(kept)
    stats["mathml_conversions"] = sum(q.meta.get("mathml_conversions", 0) for q in kept)

    # 6. Competitive tagging
    kwargs = {"force_rule_based": force_rule_based_tagging}
    if tag_model:
        kwargs["model"] = tag_model
    kept = tag_questions(kept, **kwargs)

    stats["output_count"] = len(kept)

    return PipelineRunResult(kept=kept, dropped=dropped, stats=stats)
