"""Data models for bypass question pipeline."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field


@dataclass
class ParsedBypassFile:
    source: str
    subject: str
    class_level: int
    source_file: str
    questions: list[ParsedQuestion] = field(default_factory=list)


@dataclass
class ParsedQuestion:
    question_id: str
    stem: str
    line_start: int
    line_end: int


@dataclass
class ScoredQuestion:
    question_id: str
    stem: str
    line_start: int
    line_end: int
    scores: dict[str, float]
    recommended_type: str
    confidence: float


@dataclass
class ConvertedQuestion:
    qid: str
    source: str
    subject: str
    question_id: str
    questionType: str
    answer_key: str
    level: str
    class_level: int
    question_content: str
    solution_content: str
    answer_source: str = "generated"
    taggedBy: str = "NITAI"
    line_start: int = 0
    line_end: int = 0
    needs_review: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TokenStats:
    analysis_input: int = 0
    analysis_output: int = 0
    conversion_input: int = 0
    conversion_output: int = 0

    @property
    def total(self) -> int:
        return (
            self.analysis_input
            + self.analysis_output
            + self.conversion_input
            + self.conversion_output
        )

    def to_dict(self) -> dict:
        return {
            "analysis_input": self.analysis_input,
            "analysis_output": self.analysis_output,
            "conversion_input": self.conversion_input,
            "conversion_output": self.conversion_output,
            "total": self.total,
        }


@dataclass
class ConversionResult:
    source: str
    subject: str
    class_level: int
    source_file: str
    questions: list[ConvertedQuestion] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    tokens: TokenStats = field(default_factory=TokenStats)
    model: str = ""
    batch_calls: int = 0
    input_question_count: int = 0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "subject": self.subject,
            "class_level": self.class_level,
            "source_file": self.source_file,
            "model": self.model,
            "batch_calls": self.batch_calls,
            "batch_size": int(os.getenv("BYPASS_BATCH_SIZE", "8")),
            "input_question_count": self.input_question_count,
            "question_count": len(self.questions),
            "converted_count": len(self.questions),
            "eliminated_count": len(self.skipped),
            "needs_review_count": sum(1 for q in self.questions if q.needs_review),
            "by_type": _count_by_type(self.questions),
            "tokens": self.tokens.to_dict(),
            "questions": [q.to_dict() for q in self.questions],
            "eliminated": self.skipped,
            "skipped": self.skipped,
        }


def _count_by_type(questions: list[ConvertedQuestion]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for q in questions:
        key = q.questionType.lower()
        counts[key] = counts.get(key, 0) + 1
    return counts
