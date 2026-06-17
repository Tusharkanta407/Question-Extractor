"""Shared data models for extracted questions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class QuestionOption:
    label: str
    text: str


@dataclass
class Question:
    id: str
    section: str
    number: str
    type: str
    stem: str
    sub_part: str | None = None
    options: list[QuestionOption] = field(default_factory=list)
    match_column_a: list[QuestionOption] = field(default_factory=list)
    match_column_b: list[QuestionOption] = field(default_factory=list)
    flags: dict = field(default_factory=lambda: {
        "partial": False,
        "needs_review": False,
        "convertible": False,
    })
    raw_text: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["options"] = [asdict(o) for o in self.options]
        d["match_column_a"] = [asdict(o) for o in self.match_column_a]
        d["match_column_b"] = [asdict(o) for o in self.match_column_b]
        return d


@dataclass
class ExtractedDocument:
    title: str
    source_format: str
    source_file: str = ""
    questions: list[Question] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source_format": self.source_format,
            "source_file": self.source_file,
            "question_count": len(self.questions),
            "questions": [q.to_dict() for q in self.questions],
        }
