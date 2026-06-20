"""Data models for Foundation question bank."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import re
import random

_NONNEG_NUMERIC_RE = re.compile(r"^\+?\d+(\.\d+)?$")


def _is_nonneg_numeric(value: str) -> bool:
    return bool(_NONNEG_NUMERIC_RE.match(value.strip()))


def _build_fib_options(correct: str, pool: list[str]) -> list[dict]:
    """
    Place correct answer randomly in (a/b/c/d).
    Fill remaining slots from pool (other FIB answers), avoiding duplicates.
    """
    # Distractors = other answers from pool, excluding correct
    distractors = [p for p in pool if p.lower() != correct.lower()]
    random.shuffle(distractors)
    distractors = distractors[:3]

    # Pad with placeholders if not enough distractors
    while len(distractors) < 3:
        distractors.append("___")

    # Place correct answer at a random position among 4
    labels = ["a", "b", "c", "d"]
    correct_pos = random.randint(0, 3)

    options = []
    distractor_idx = 0
    for i, label in enumerate(labels):
        if i == correct_pos:
            options.append({"label": label, "text": correct})
        else:
            options.append({"label": label, "text": distractors[distractor_idx]})
            distractor_idx += 1

    return options, labels[correct_pos]


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

    def to_dict(self, fib_pool: list[str] | None = None) -> dict:
        d = asdict(self)

        answer_key = (self.answer_key or "").strip()
        q_type = self.question_type
        opts = [asdict(o) for o in (self.options or self.shared_options)]
        needs_review = False
        convertible = False
        correct_label = None

        # ── Rule 1: INTEGER — only non-negative numeric answers allowed ──────
        if q_type == "INTEGER" and answer_key:
            if not _is_nonneg_numeric(answer_key):
                needs_review = True

        # ── Rule 2: FIB with word answer → convert to SCQ ───────────────────
        elif q_type == "FIB" and answer_key:
            if not _is_nonneg_numeric(answer_key):
                q_type = "SCQ"
                pool = fib_pool or []
                opts, correct_label = _build_fib_options(answer_key, pool)
                needs_review = any(o["text"] == "___" for o in opts)
                convertible = True

        d["question_type"] = q_type
        d["options"] = opts
        d["shared_options"] = [asdict(o) for o in self.shared_options]
        d["column_a"] = [asdict(o) for o in self.column_a]
        d["column_b"] = [asdict(o) for o in self.column_b]
        d["flags"] = {
            "needs_review": needs_review,
            "convertible": convertible,
            "correct_option": correct_label,
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

        # Build pool of all word-based FIB answers in this document
        fib_pool = [
            q.answer_key.strip()
            for q in self.questions
            if q.question_type == "FIB"
            and (q.answer_key or "").strip()
            and not _is_nonneg_numeric(q.answer_key.strip())
        ]

        book = sum(1 for q in self.questions if q.answer_source == "book")
        llm  = sum(1 for q in self.questions if q.answer_source == "llm")
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
            "questions": [q.to_dict(fib_pool=fib_pool) for q in self.questions],
        }
