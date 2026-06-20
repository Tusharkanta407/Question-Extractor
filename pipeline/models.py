"""Shared data models for the post-extraction pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class PipelineQuestion:
    """Normalized question record used across the pipeline stages.

    Built from whatever upstream extractor/converter produced the question
    (ConvertedQuestion, FoundationQuestion, Question, or a raw dict). Carries
    every field forward and adds slots that later stages fill in.
    """

    qid: str
    question_type: str  # SCQ | MCQ | INTEGER | ...
    question_content: str
    answer_key: str = ""
    solution_content: str = ""
    options: list[dict] = field(default_factory=list)
    source: str = ""
    subject: str = ""
    class_level: int | str = ""
    level: str = ""
    line_start: int = 0
    line_end: int = 0
    meta: dict = field(default_factory=dict)

    # --- filled in by pipeline stages ---
    embedding: list[float] | None = field(default=None, repr=False)
    similarity_match: dict | None = None       # set if dropped as duplicate
    dropped_reason: str | None = None           # "duplicate" | "empty" | ...
    question_content_mathml: str = ""           # cleaned + MathML version
    solution_content_mathml: str = ""
    tags: dict = field(default_factory=dict)    # competitive tagger output

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("embedding", None)  # never serialize raw vectors into output JSON
        return d


def question_from_dict(d: dict) -> PipelineQuestion:
    """Build a PipelineQuestion from any upstream record shape.

    Accepts ConvertedQuestion.to_dict() (bypass_question), FoundationQuestion
    .to_dict() (foundation), Question.to_dict() (root extractor), or an
    already-normalized dict.
    """
    qid = d.get("qid") or d.get("question_id") or d.get("id") or ""
    qtype = (d.get("questionType") or d.get("question_type") or d.get("type") or "").upper()
    content = d.get("question_content") or d.get("stem") or ""
    answer = d.get("answer_key") or ""
    solution = d.get("solution_content") or d.get("explanation") or ""
    options = d.get("options") or []

    return PipelineQuestion(
        qid=str(qid),
        question_type=qtype,
        question_content=content,
        answer_key=str(answer),
        solution_content=solution,
        options=options,
        source=d.get("source", ""),
        subject=d.get("subject", ""),
        class_level=d.get("class_level", ""),
        level=d.get("level", ""),
        line_start=d.get("line_start", 0),
        line_end=d.get("line_end", 0),
        meta={k: v for k, v in d.items() if k not in {
            "qid", "question_id", "id", "questionType", "question_type", "type",
            "question_content", "stem", "answer_key", "solution_content",
            "explanation", "options", "source", "subject", "class_level",
            "level", "line_start", "line_end",
        }},
    )
