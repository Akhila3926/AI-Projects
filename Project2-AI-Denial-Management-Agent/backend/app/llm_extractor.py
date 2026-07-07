from app import llm_client
from app.models import Claim, Denial

EXTRACTION_SYSTEM_PROMPT = """You are a medical billing claim data extractor. Given raw denial \
text (an 835 ERA, an EOB, or a payer portal/email notice), extract the claim and denial fields as \
strict JSON. Respond with ONLY a JSON object, no prose, matching this shape exactly:

{
  "claim_id": string,
  "patient_name": string,
  "patient_identifier": string or null,
  "payer": string or null,
  "provider": string or null,
  "date_of_service": string or null,
  "procedure_code": string or null,
  "procedure_desc": string or null,
  "billed_amount": number or null,
  "allowed_amount": number or null,
  "paid_amount": number or null,
  "carc_codes": array of strings (numeric CARC codes without the "CO-" prefix, e.g. "16"),
  "rarc_codes": array of strings (e.g. "N382")
}

If a field cannot be determined, use null (or an empty array for the code lists). Never invent \
a claim_id or patient_name - if genuinely absent, use "UNKNOWN"."""


def extract(raw_text: str, source_format: str) -> tuple[Claim, Denial] | None:
    """Ask Grok to extract claim/denial fields from text the regex parsers couldn't handle.

    Returns None if Grok is unavailable or its output doesn't validate against
    the Claim/Denial models - callers should keep the existing regex result in that case.
    """
    user_prompt = f"Source format: {source_format}\n\nRaw denial text:\n{raw_text}"
    data = llm_client.chat_json(EXTRACTION_SYSTEM_PROMPT, user_prompt)
    if not data:
        return None

    try:
        claim = Claim(
            claim_id=data.get("claim_id") or "UNKNOWN",
            patient_name=data.get("patient_name") or "UNKNOWN",
            patient_identifier=data.get("patient_identifier"),
            payer=data.get("payer"),
            provider=data.get("provider"),
            date_of_service=data.get("date_of_service"),
            procedure_code=data.get("procedure_code"),
            procedure_desc=data.get("procedure_desc"),
            billed_amount=data.get("billed_amount"),
            allowed_amount=data.get("allowed_amount"),
            paid_amount=data.get("paid_amount"),
        )
        denial = Denial(
            carc_codes=[str(c) for c in (data.get("carc_codes") or [])],
            rarc_codes=[str(c) for c in (data.get("rarc_codes") or [])],
            raw_text=raw_text,
            source_format=source_format,
        )
    except Exception:
        return None

    return claim, denial
