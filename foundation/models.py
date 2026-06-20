"""Data models for Foundation question bank."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import re

_NONNEG_NUMERIC_RE = re.compile(r"^\+?\d+(\.\d+)?$")

def _is_nonneg_numeric(value: str) -> bool:
    return bool(_NONNEG_NUMERIC_RE.match(value.strip()))


@dataclass
class QuestionOption:
    label: str
    text: str


@dataclass
class FoundationQuestion:
    qnum: int
    qid: str
    question_type: str
    exercise: str
    subsection: str
    section: str
    stem: str
    options: list[QuestionOption] = field(default_factory=list)
    shared_options: list[QuestionOption] = field(default_factory=list)
    column_a: list[QuestionOption] = field(default_factory=list)
    column_b: list[QuestionOption] = field(default_factory=list)
    passage: str = ""
    directions: str = ""
    answer_key: str = ""
    explanation: str = ""
    answer_source: str = ""  # "book" | "llm" | ""
    line_start: int = 0
    line_end: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)

        answer_key = (self.answer_key or "").strip()
        q_type = self.question_type
        opts = [asdict(o) for o in (self.options or self.shared_options)]
        needs_review = False
        convertible = False

        # ── Rule 1: INTEGER — only non-negative numeric answers allowed ──────
        if q_type == "INTEGER" and answer_key:
            if not _is_nonneg_numeric(answer_key):
                needs_review = True

        # ── Rule 2: FIB with word answer → convert to SCQ ───────────────────
        elif q_type == "FIB" and answer_key:
            if not _is_nonneg_numeric(answer_key):
                q_type = "SCQ"
                opts = [
                    {"label": "a", "text": answer_key},
                    {"label": "b", "text": "___"},
                    {"label": "c", "text": "___"},
                    {"label": "d", "text": "___"},
                ]
                needs_review = True
                convertible = True

        d["question_type"] = q_type
        d["options"] = opts
        d["shared_options"] = [asdict(o) for o in self.shared_options]
        d["column_a"] = [asdict(o) for o in self.column_a]
        d["column_b"] = [asdict(o) for o in self.column_b]
        d["flags"] = {
            "needs_review": needs_review,
            "convertible": convertible,
        }
        return d


@dataclass
class FoundationDocument:
    title: str
    subject: str
    class_level: int
    source_file: str
    questions: list[FoundationQuestion] = field(default_factory=list)
    paired_answers: int = 0
    answer_entries: int = 0
    llm_filled: int = 0
    llm_skipped_subjective: int = 0
    llm_tokens: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        from foundation.answer_llm import is_objective, needs_llm_answer
        book = sum(1 for q in self.questions if q.answer_source == "book")
        llm = sum(1 for q in self.questions if q.answer_source == "llm")
        obj_missing = sum(1 for q in self.questions if needs_llm_answer(q))
        subj_no_key = sum(
            1 for q in self.questions
            if not is_objective(q) and not (q.answer_key or "").strip()
        )
        return {
            "title": self.title,
            "subject": self.subject,
            "class_level": self.class_level,
            "source_file": self.source_file,
            "question_count": len(self.questions),
            "paired_answers": self.paired_answers,
            "answer_entries": self.answer_entries,
            "book_answers": book,
            "llm_answers": llm,
            "objective_missing": obj_missing,
            "subjective_skipped": self.llm_skipped_subjective or subj_no_key,
            "llm_filled": self.llm_filled,
            "llm_skipped_subjective": self.llm_skipped_subjective,
            "llm_tokens": self.llm_tokens,
            "questions": [q.to_dict() for q in self.questions],
        }
