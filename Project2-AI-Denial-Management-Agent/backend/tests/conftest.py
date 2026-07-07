import pytest


@pytest.fixture(autouse=True)
def no_real_llm_calls(monkeypatch):
    """Keep tests offline/deterministic by default: strip any real Groq key from
    the environment so llm_client.is_configured() is False unless a test
    explicitly opts in (e.g. by monkeypatching app.llm_client.chat_json itself).
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
