"""OpenAI client for Foundation answer filling."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI

_PKG_DIR = Path(__file__).resolve().parent
load_dotenv(_PKG_DIR / ".env")
load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BATCH_SIZE = int(os.getenv("FOUNDATION_LLM_BATCH_SIZE", "12"))


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to foundation/.env")
    return OpenAI(api_key=api_key)


def _encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = DEFAULT_MODEL) -> int:
    if not text:
        return 0
    return len(_encoding(model).encode(text))


def _parse_json_response(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def chat_json(*, system: str, user: str, model: str = DEFAULT_MODEL) -> tuple[dict, dict]:
    client = _client()
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content or "{}"
    usage = response.usage
    if usage:
        return _parse_json_response(content), {
            "input": usage.prompt_tokens,
            "output": usage.completion_tokens,
        }
    return _parse_json_response(content), {
        "input": count_tokens(system + user, model),
        "output": count_tokens(content, model),
    }
