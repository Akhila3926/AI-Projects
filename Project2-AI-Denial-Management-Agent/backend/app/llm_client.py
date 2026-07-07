"""Thin wrapper around Groq's OpenAI-compatible API, used only as a fallback when the
deterministic regex parsers / CARC-RARC lookup table can't handle a denial.

Every call here is designed to fail safe: on any error (missing key,
network issue, invalid JSON) callers get None back and fall through to
the existing rule-based behavior rather than crashing the request.
"""
import json
import os

from dotenv import load_dotenv

load_dotenv()

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

_client = None


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=GROQ_BASE_URL)
    return _client


def chat_json(system_prompt: str, user_prompt: str) -> dict | None:
    """Call the LLM and parse its response as JSON. Returns None on any failure."""
    if not is_configured():
        return None

    model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception:
        return None
