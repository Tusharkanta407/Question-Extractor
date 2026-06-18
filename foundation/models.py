"""Data models for Foundation question bank."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


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
        d["options"] = [asdict(o) for o in self.options]
        d["shared_options"] = [asdict(o) for o in self.shared_options]
        d["column_a"] = [asdict(o) for o in self.column_a]
        d["column_b"] = [asdict(o) for o in self.column_b]
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
