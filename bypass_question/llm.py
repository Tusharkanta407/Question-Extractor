"""OpenAI client with tiktoken-based token counting."""

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


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to bypass_question/.env"
        )
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


def chat_json(
    *,
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
) -> tuple[dict, dict]:
    """Return (parsed_json, token_usage_dict)."""
    client = _client()
    input_tokens = count_tokens(system, model) + count_tokens(user, model)

    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    content = response.choices[0].message.content or "{}"
    usage = response.usage
    output_tokens = usage.completion_tokens if usage else count_tokens(content, model)
    if usage:
        input_tokens = usage.prompt_tokens

    return _parse_json_response(content), {
        "input": input_tokens,
        "output": output_tokens,
    }
