from app import llm_client
from app.models import Claim, Denial, DenialCategory

EXPLAIN_SYSTEM_PROMPT = """You are a medical billing assistant. Rewrite the given denial \
explanation to be clear, natural, plain English for a non-technical clinic biller, using the \
specific claim details provided. Keep it factually identical to the template - do not invent \
new facts, codes, or amounts. Keep it to 2-4 sentences. Respond with ONLY a JSON object: \
{"explanation": "<rewritten text>"}"""


def rewrite_explanation(
    claim: Claim, denial: Denial, category: DenialCategory, template_explanation: str
) -> str | None:
    """Ask Grok to rewrite the templated explanation more naturally.

    Returns None (keep the template) if Grok is unavailable, errors, or returns empty text.
    """
    user_prompt = (
        f"Category: {category}\n"
        f"Claim ID: {claim.claim_id}\n"
        f"Patient: {claim.patient_name}\n"
        f"CARC codes: {denial.carc_codes} ({denial.carc_descriptions})\n"
        f"RARC codes: {denial.rarc_codes} ({denial.rarc_descriptions})\n"
        f"Template explanation to rewrite:\n{template_explanation}"
    )
    data = llm_client.chat_json(EXPLAIN_SYSTEM_PROMPT, user_prompt)
    if not data:
        return None

    explanation = data.get("explanation")
    if not explanation or not isinstance(explanation, str):
        return None
    return explanation.strip()
