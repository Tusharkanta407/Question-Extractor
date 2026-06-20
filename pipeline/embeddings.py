"""Stage: create embeddings for question stems.

Uses OpenAI's embeddings API (text-embedding-3-small by default) so it
shares the same API key already used by bypass_question/llm.py and
foundation/llm.py. Embeddings are batched to minimize API calls.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from pipeline.models import PipelineQuestion

_PKG_DIR = Path(__file__).resolve().parent
load_dotenv(_PKG_DIR / ".env")
load_dotenv()

DEFAULT_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "100"))


def _client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to pipeline/.env or the environment."
        )
    return OpenAI(api_key=api_key)


def _embed_text(q: PipelineQuestion) -> str:
    """Text actually sent to the embedding model: stem + options, so MCQ
    options participate in similarity (two questions with the same stem
    but different options should not be flagged as duplicates)."""
    parts = [q.question_content.strip()]
    for opt in q.options:
        label = opt.get("label", "")
        text = opt.get("text", "")
        if text:
            parts.append(f"{label}) {text}")
    return "\n".join(p for p in parts if p)


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def embed_questions(
    questions: list[PipelineQuestion],
    *,
    model: str = DEFAULT_EMBED_MODEL,
    batch_size: int = EMBED_BATCH_SIZE,
) -> list[PipelineQuestion]:
    """Mutates and returns `questions` with `.embedding` populated.

    Skips questions with empty content (left as None so later stages can
    treat them as "no embedding available").
    """
    client = _client()

    targets = [q for q in questions if q.question_content.strip()]
    for batch in _chunks(targets, batch_size):
        texts = [_embed_text(q) for q in batch]
        response = client.embeddings.create(model=model, input=texts)
        for q, item in zip(batch, response.data):
            q.embedding = item.embedding

    return questions
