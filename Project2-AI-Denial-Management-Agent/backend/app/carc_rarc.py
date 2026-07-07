"""Data-driven CARC/RARC lookup and category mapping.

Adding support for a new denial code is a one-line dict entry here -
no per-payer or per-code branching logic lives anywhere else.
"""
from app.models import DenialCategory

CARC_DESCRIPTIONS = {
    "16": "Claim/service lacks information needed for adjudication",
    "50": "Service not deemed medically necessary",
    "197": "Precertification/authorization absent",
}

RARC_DESCRIPTIONS = {
    "N382": "Missing/incomplete/invalid patient identifier",
    "N115": "Decision based on Local Coverage Determination",
}

# category a CARC code maps to when no more-specific RARC overrides it
CARC_CATEGORY = {
    "16": "data_error",
    "50": "medical_necessity",
    "197": "auth_gap",
}

# RARC codes take precedence over the CARC's default category when present
RARC_CATEGORY_OVERRIDE = {
    "N382": "data_error",
    "N115": "medical_necessity",
}


def describe_carc(code: str) -> str:
    return CARC_DESCRIPTIONS.get(code, f"Unrecognized CARC code {code}")


def describe_rarc(code: str) -> str:
    return RARC_DESCRIPTIONS.get(code, f"Unrecognized RARC code {code}")


def classify(carc_codes: list[str], rarc_codes: list[str]) -> DenialCategory:
    for rarc in rarc_codes:
        if rarc in RARC_CATEGORY_OVERRIDE:
            return RARC_CATEGORY_OVERRIDE[rarc]
    for carc in carc_codes:
        if carc in CARC_CATEGORY:
            return CARC_CATEGORY[carc]
    return "other"
