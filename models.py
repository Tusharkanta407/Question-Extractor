"""Shared data models for extracted questions."""
from __future__ import annotations
import re
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
    answer: str | None = None
    flags: dict = field(default_factory=lambda: {
        "partial": False,
        "needs_review": False,
        "convertible": False,
    })
    raw_text: str = ""

    def is_valid_integer_answer(self) -> bool:
        """Return True if answer is a non-negative integer or decimal number."""
        if self.answer is None:
            return False
        val = self.answer.strip().lstrip("+")
        try:
            n = float(val)
            return n >= 0
        except ValueError:
            return False

    def set_integer_answer(self, value: str) -> None:
        """Set answer with validation. Raises ValueError for invalid integer answers."""
        val = value.strip().lstrip("+")
        try:
            n = float(val)
            if n < 0:
                raise ValueError(f"Integer answer must be non-negative, got: {value!r}")
        except ValueError as e:
            if "non-negative" in str(e):
                raise
            raise ValueError(f"Integer answer must be a number, got: {value!r}") from e
        self.answer = val

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
