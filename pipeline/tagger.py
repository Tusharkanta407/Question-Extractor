"""Stage: tag each surviving question with competitive-exam metadata.

Uses one batched LLM call per chunk (same pattern as
bypass_question/converter.py) to assign:
  - difficulty: EASY | MEDIUM | HARD
  - bloom_level: REMEMBER | UNDERSTAND | APPLY | ANALYZE | EVALUATE | CREATE
  - topic: short topic/concept label within the chapter
  - exam_tags: which competitive contexts the question fits
        (e.g. "NTSE", "OLYMPIAD", "JEE_FOUNDATION", "NEET_FOUNDATION", "BOARD")
  - estimated_time_seconds: expected solve time
  - concept_importance: HIGH | MEDIUM | LOW (how central the concept is to the syllabus)

Falls back to a deterministic rule-based tagger if no OPENAI_API_KEY is
set, so the pipeline stays runnable/testable without API access.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from pipeline.models import PipelineQuestion

_PKG_DIR = Path(__file__).resolve().parent
load_dotenv(_PKG_DIR / ".env")
load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TAG_BATCH_SIZE = int(os.getenv("TAG_BATCH_SIZE", "10"))

EXAM_TAG_CHOICES = ["NTSE", "OLYMPIAD", "JEE_FOUNDATION", "NEET_FOUNDATION", "BOARD"]
BLOOM_LEVELS = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"]

TAGGER_SYSTEM = """You are a competitive-exam question tagger for Indian school \
science/maths questions (NTSE, Olympiads, JEE/NEET Foundation, Board exams).

For EACH question, assign:
- difficulty: EASY | MEDIUM | HARD
- bloom_level: one of REMEMBER, UNDERSTAND, APPLY, ANALYZE, EVALUATE, CREATE
- topic: a short 2-5 word concept label (e.g. "Newton's Third Law")
- exam_tags: array, any of NTSE, OLYMPIAD, JEE_FOUNDATION, NEET_FOUNDATION, BOARD
  (a question can match multiple; BOARD if it's straightforward NCERT-level)
- estimated_time_seconds: realistic solve time for a student of that class level
- concept_importance: HIGH | MEDIUM | LOW

Return JSON only:
{
  "tags": [
    {
      "qid": "Q3a",
      "difficulty": "MEDIUM",
      "bloom_level": "APPLY",
      "topic": "Photosynthesis - factors affecting rate",
      "exam_tags": ["BOARD", "NTSE"],
      "estimated_time_seconds": 60,
      "concept_importance": "HIGH"
    }
  ]
}"""


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set.")
    return OpenAI(api_key=api_key)


def _parse_json_response(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _tag_batch_llm(
    batch: list[PipelineQuestion], *, model: str = DEFAULT_MODEL
) -> dict[str, dict]:
    client = _client()
    payload = {
        "questions": [
            {
                "qid": q.qid,
                "question_type": q.question_type,
                "question_content": q.question_content,
                "subject": q.subject,
                "class_level": q.class_level,
            }
            for q in batch
        ]
    }
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TAGGER_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    data = _parse_json_response(content)
    return {str(t.get("qid", "")): t for t in data.get("tags", [])}


# --- deterministic fallback (no API key needed) ---

_KEYWORD_TOPIC_HINTS = [
    (re.compile(r"photosynthesis", re.I), "Photosynthesis"),
    (re.compile(r"microorganism|bacteria|virus|fung", re.I), "Microorganisms"),
    (re.compile(r"combustion|flame|fuel", re.I), "Combustion and Flame"),
    (re.compile(r"coal|petroleum|fossil", re.I), "Coal and Petroleum"),
    (re.compile(r"force|newton|motion", re.I), "Force and Motion"),
    (re.compile(r"reaction|equation|chemical", re.I), "Chemical Reactions"),
    (re.compile(r"cell\b|tissue", re.I), "Cell Biology"),
]


def _rule_based_tag(q: PipelineQuestion) -> dict:
    text = q.question_content
    word_count = len(text.split())

    if word_count <= 12:
        difficulty, bloom = "EASY", "REMEMBER"
    elif word_count <= 30:
        difficulty, bloom = "MEDIUM", "UNDERSTAND"
    else:
        difficulty, bloom = "HARD", "APPLY"

    if re.search(r"\bwhy\b|\bexplain\b|\bhow does\b", text, re.I):
        bloom = "ANALYZE" if difficulty == "HARD" else "UNDERSTAND"
    if re.search(r"\bcalculate\b|\bhow many\b|\bfind\b", text, re.I):
        bloom = "APPLY"

    topic = "General"
    for pattern, label in _KEYWORD_TOPIC_HINTS:
        if pattern.search(text):
            topic = label
            break

    exam_tags = ["BOARD"]
    if difficulty != "EASY":
        exam_tags.append("NTSE")
    if q.question_type in {"SCQ", "MCQ"} and difficulty == "HARD":
        exam_tags.append("JEE_FOUNDATION")

    base_time = {"EASY": 30, "MEDIUM": 60, "HARD": 120}[difficulty]

    return {
        "difficulty": difficulty,
        "bloom_level": bloom,
        "topic": topic,
        "exam_tags": exam_tags,
        "estimated_time_seconds": base_time,
        "concept_importance": "MEDIUM",
        "tagged_by": "rule_based_fallback",
    }


def tag_questions(
    questions: list[PipelineQuestion],
    *,
    model: str = DEFAULT_MODEL,
    batch_size: int = TAG_BATCH_SIZE,
    force_rule_based: bool = False,
) -> list[PipelineQuestion]:
    """Mutates and returns `questions` with `.tags` populated."""
    use_llm = not force_rule_based and bool(os.getenv("OPENAI_API_KEY"))

    if not use_llm:
        for q in questions:
            q.tags = _rule_based_tag(q)
        return questions

    for batch in _chunks(questions, batch_size):
        try:
            tag_map = _tag_batch_llm(batch, model=model)
        except Exception as exc:
            for q in batch:
                q.tags = {**_rule_based_tag(q), "tag_error": str(exc)}
            continue

        for q in batch:
            tag = tag_map.get(q.qid)
            if tag:
                q.tags = {
                    "difficulty": tag.get("difficulty", "MEDIUM"),
                    "bloom_level": tag.get("bloom_level", "UNDERSTAND"),
                    "topic": tag.get("topic", ""),
                    "exam_tags": tag.get("exam_tags", []),
                    "estimated_time_seconds": tag.get("estimated_time_seconds", 60),
                    "concept_importance": tag.get("concept_importance", "MEDIUM"),
                    "tagged_by": "llm",
                }
            else:
                q.tags = _rule_based_tag(q)

    return questions
