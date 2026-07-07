from app import llm_client
from app.models import Denial, DenialCategory

VALID_CATEGORIES = {"data_error", "auth_gap", "medical_necessity", "other"}

CLASSIFICATION_SYSTEM_PROMPT = """You are a medical billing denial classifier. Given a set of \
CARC/RARC denial codes and descriptions, pick exactly ONE category from this fixed list:

- "data_error": missing/incorrect patient or claim data (identifiers, coding errors, modifier issues, eligibility mismatches)
- "auth_gap": missing or invalid prior authorization/precertification
- "medical_necessity": denied as not medically necessary, requires a clinical appeal
- "other": doesn't clearly fit any of the above

Respond with ONLY a JSON object: {"category": "<one of the four values above>"}"""


def classify_with_llm(denial: Denial) -> DenialCategory | None:
    """Fallback classification when the CARC/RARC lookup table doesn't recognize the codes.

    Returns None if Grok is unavailable or returns something outside the fixed category set.
    """
    codes_summary = (
        f"CARC codes: {denial.carc_codes} ({denial.carc_descriptions})\n"
        f"RARC codes: {denial.rarc_codes} ({denial.rarc_descriptions})\n"
        f"Raw denial text:\n{denial.raw_text}"
    )
    data = llm_client.chat_json(CLASSIFICATION_SYSTEM_PROMPT, codes_summary)
    if not data:
        return None

    category = data.get("category")
    if category not in VALID_CATEGORIES:
        return None
    return category
