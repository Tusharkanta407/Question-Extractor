"""Stage: clean the remaining (non-duplicate) questions.

Pure text-normalization, no LLM calls:
- collapse whitespace / stray newlines
- strip leading question numbers re-introduced by upstream parsers
- normalize option label punctuation: "A)" / "(A)" / "A." -> "(A)"
- strip empty options
- trim solution/answer whitespace
"""

from __future__ import annotations

import re

from pipeline.models import PipelineQuestion

_WS_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_LEADING_NUM_RE = re.compile(r"^\s*(?:Q?\.?\s*\d+[a-z]?[\.\)]\s*)", re.IGNORECASE)
_OPTION_LABEL_RE = re.compile(r"^\(([A-Da-d])\)\s*|^([A-Da-d])[\.\)]\s+")


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(_WS_RE.sub(" ", line).strip() for line in text.split("\n"))
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _strip_leading_number(text: str) -> str:
    return _LEADING_NUM_RE.sub("", text, count=1).strip()


def clean_question(q: PipelineQuestion) -> PipelineQuestion:
    q.question_content = _strip_leading_number(_normalize_whitespace(q.question_content))
    q.solution_content = _normalize_whitespace(q.solution_content)
    q.answer_key = q.answer_key.strip()

    cleaned_options = []
    for opt in q.options:
        label = str(opt.get("label", "")).strip()
        text = _normalize_whitespace(str(opt.get("text", "")))
        text = _OPTION_LABEL_RE.sub("", text, count=1).strip()
        if not text:
            continue
        # normalize label to a bare letter, e.g. "(A)" -> "A"
        label_match = re.match(r"\(?([A-Da-d])\)?", label)
        label = label_match.group(1).upper() if label_match else label
        cleaned_options.append({"label": label, "text": text})
    q.options = cleaned_options

    return q


def clean_questions(questions: list[PipelineQuestion]) -> list[PipelineQuestion]:
    return [clean_question(q) for q in questions]
