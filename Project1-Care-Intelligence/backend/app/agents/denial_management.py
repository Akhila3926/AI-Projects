from __future__ import annotations
"""
Denial Management Agent — diagnoses a denial, drafts a payer-appropriate
appeal letter, and (after approval) resubmits the claim.

Smart appeal logic:
- Skips claims already appealed more than MAX_APPEAL_ATTEMPTS times
- Classifies denial reason to tailor the appeal argument
- Generates a real appeal letter with clinical justification
"""
from app.data.store import store
from app.llm import ask_claude

MAX_APPEAL_ATTEMPTS = 2  # don't re-appeal a claim more than twice

# Which denial reasons are worth appealing (all others get flagged for manual review)
APPEALABLE_REASONS = {
    "missing documentation": "We will provide the missing documentation with this appeal.",
    "missing info":          "We will supply the requested information with this resubmission.",
    "invalid code":          "The code has been reviewed and corrected per current payer guidelines.",
    "coverage issue":        "We are appealing on the basis of medical necessity and coverage eligibility.",
    "medical necessity":     "Clinical documentation supporting medical necessity is attached.",
    "authorization":         "Prior authorization was obtained / retroactive authorization is being requested.",
    "prior auth":            "Prior authorization documentation is attached.",
    "pre-auth":              "Pre-authorization was on file at the time of service.",
    "timely filing":         "Evidence of timely filing is attached (original submission records).",
    "coordination":          "Coordination of benefits has been verified and updated.",
    "eligibility":           "Eligibility was confirmed at the time of service — proof is attached.",
    "duplicate claim":       "This is not a duplicate — services were rendered on separate dates/encounters.",
    "experimental":          "Clinical evidence supporting the established nature of this treatment is attached.",
    "not covered":           "We are appealing with supporting clinical documentation for medical necessity.",
}

DIAGNOSIS_SYSTEM_PROMPT = """You are a denial management specialist. Given a
denied claim and its denial reason, explain in one or two sentences why it
was likely denied and what specific evidence or argument would overturn it."""

APPEAL_SYSTEM_PROMPT = """You are a denial management specialist writing a
formal payer appeal letter. Be professional, cite the denial reason, reference
the clinical justification, and request reconsideration. Keep it under 200 words.
Use this structure: opening (identify the claim), reason for appeal, supporting
evidence statement, closing request."""

# In-memory appeal attempt tracker (resets on server restart — acceptable for demo)
_appeal_attempts: dict[str, int] = {}


def _get_appeal_argument(denial_reason: str) -> str:
    """Return the best appeal argument for a given denial reason."""
    dl = (denial_reason or "").lower()
    for key, argument in APPEALABLE_REASONS.items():
        if key in dl:
            return argument
    return "We are appealing this denial and request a thorough review of the clinical documentation."


def is_appealable(denial_reason: str) -> bool:
    dl = (denial_reason or "").lower()
    return any(key in dl for key in APPEALABLE_REASONS)


def diagnose_and_draft_appeal(claim_id: str) -> dict:
    claim = store.get_claim(claim_id)
    if not claim or claim["status"] not in ("denied", "appeal_pending_approval"):
        return {"action": "error", "message": f"Claim {claim_id} not found or not denied"}

    # Retry limit check
    attempts = _appeal_attempts.get(claim_id, 0)
    if attempts >= MAX_APPEAL_ATTEMPTS:
        return {
            "action": "error",
            "message": f"Claim {claim_id} has already been appealed {attempts} time(s). Escalate to manual review.",
        }

    patient   = store.get_patient(claim["patient_id"])
    payer     = store.get_payer(claim["payer_id"])
    denial    = claim.get("denial_reason") or "Unspecified"
    denial_text = denial if isinstance(denial, str) else f"{denial.get('code','')} - {denial.get('desc','')}"
    payer_name  = payer["name"] if payer else claim.get("payer_id", "Unknown")
    pname       = patient["name"] if patient else claim["patient_id"]

    # Get targeted appeal argument
    appeal_argument = _get_appeal_argument(denial_text)
    appealable      = is_appealable(denial_text)

    diagnosis = ask_claude(
        DIAGNOSIS_SYSTEM_PROMPT,
        f"Patient: {pname}\nPayer: {payer_name}\nDenial reason: {denial_text}\n"
        f"Claim amount: ${claim.get('amount', 0):,.0f}\n"
        f"Suggested appeal argument: {appeal_argument}",
    )

    appeal_letter = ask_claude(
        APPEAL_SYSTEM_PROMPT,
        f"Patient: {pname}\nPayer: {payer_name}\nClaim ID: {claim_id}\n"
        f"Denial reason: {denial_text}\nBilled amount: ${claim.get('amount', 0):,.0f}\n"
        f"Appeal argument: {appeal_argument}\nDiagnosis: {diagnosis}",
    )

    # Track attempt
    _appeal_attempts[claim_id] = attempts + 1

    store.update_claim(claim_id, status="appeal_pending_approval")

    return {
        "action":           "appeal_drafted",
        "claim_id":         claim_id,
        "patient":          pname,
        "payer":            payer_name,
        "amount":           claim.get("amount", 0),
        "denial_reason":    denial_text,
        "appealable":       appealable,
        "appeal_attempt":   attempts + 1,
        "max_attempts":     MAX_APPEAL_ATTEMPTS,
        "diagnosis":        diagnosis,
        "appeal_argument":  appeal_argument,
        "appeal_letter":    appeal_letter,
        "feed_message":     f"Appeal #{attempts+1} drafted for claim {claim_id} ({pname}, ${claim.get('amount',0):,.0f}) — awaiting approval",
        "requires_approval": True,
    }


def resubmit_appeal(claim_id: str) -> dict:
    """Called after a human approves the drafted appeal."""
    claim = store.get_claim(claim_id)
    if not claim or claim["status"] != "appeal_pending_approval":
        return {"action": "error", "message": f"Claim {claim_id} not awaiting appeal approval"}

    store.update_claim(claim_id, status="appealed", denial_reason=None)

    payer = store.get_payer(claim["payer_id"])
    payer_name = payer["name"] if payer else claim.get("payer_id", "Unknown")

    return {
        "action":       "appeal_resubmitted",
        "claim_id":     claim_id,
        "feed_message": f"Appeal for claim {claim_id} resubmitted to {payer_name}",
    }


def _bump_payer_learning(payer_id: str) -> None:
    pass
