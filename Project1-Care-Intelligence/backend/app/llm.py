"""Thin wrapper around the Groq API used by all agents."""
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
_MODEL = "llama-3.3-70b-versatile"


def ask_claude(system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
    response = _client.chat.completions.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content
