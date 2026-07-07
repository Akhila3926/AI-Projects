from app.models import Claim, Denial, Correction, DenialCategory
from app import llm_client
from app.llm_explainer import rewrite_explanation

# Categories where a corrected claim can be generated (only on explicit user request)
GENERATABLE_CATEGORIES = {"data_error", "auth_gap"}


def explain(claim: Claim, denial: Denial, category: DenialCategory) -> Correction:
    """Produce the plain-English denial explanation only - no corrected claim yet.

    A corrected claim is only generated later, on explicit user confirmation,
    via generate_correction().
    """
    if category == "data_error":
        explanation = (
            f"Payer denied claim {claim.claim_id} because the patient identifier was missing or invalid "
            f"({', '.join(denial.rarc_descriptions) or 'no RARC detail provided'}). "
            "The claim can be resubmitted once the correct member ID is confirmed and populated."
        )
        correction = Correction(category="data_error", explanation=explanation)

    elif category == "auth_gap":
        explanation = (
            f"Payer denied claim {claim.claim_id} because no prior authorization was on file "
            f"({', '.join(denial.carc_descriptions) or 'CO-197'}). "
            "Obtain a retroactive or standard authorization number from the payer, attach it to the claim, "
            "and resubmit as a replacement claim."
        )
        correction = Correction(category="auth_gap", explanation=explanation)

    elif category == "medical_necessity":
        correction = _route_to_appeal(claim, denial)

    else:
        correction = Correction(
            category="other",
            explanation=(
                f"Denial codes {denial.carc_codes + denial.rarc_codes} were not recognized. "
                "Flagged for manual biller review — no automatic correction attempted."
            ),
        )

    if llm_client.is_configured():
        rewritten = rewrite_explanation(claim, denial, correction.category, correction.explanation)
        if rewritten:
            correction.explanation = rewritten

    return correction


def generate_correction(claim: Claim, denial: Denial, correction: Correction) -> Correction:
    """Fill in the corrected claim fields - only called after the user confirms."""
    if correction.category == "data_error":
        return _correct_data_error(claim, denial, correction)
    if correction.category == "auth_gap":
        return _correct_auth_gap(claim, denial, correction)
    raise ValueError(f"No corrected claim can be generated for category '{correction.category}'")


def _correct_data_error(claim: Claim, denial: Denial, correction: Correction) -> Correction:
    corrected_fields = {}
    corrected = claim.model_copy()
    if not claim.patient_identifier or "identifier" in " ".join(denial.rarc_descriptions).lower():
        placeholder_id = f"{claim.patient_name.split()[0][:1]}00000000".upper()
        corrected.patient_identifier = placeholder_id
        corrected_fields["patient_identifier"] = (
            f"{claim.patient_identifier or '(missing)'} -> {placeholder_id} (needs verification against member card)"
        )

    correction.corrected_fields = corrected_fields
    correction.corrected_claim = corrected
    return correction


def _correct_auth_gap(claim: Claim, denial: Denial, correction: Correction) -> Correction:
    corrected = claim.model_copy()
    placeholder_auth = f"AUTH-{claim.claim_id[-6:]}"
    correction.corrected_fields = {
        "prior_authorization_number": f"(missing) -> {placeholder_auth} (obtain from payer before resubmission)"
    }
    correction.corrected_claim = corrected
    return correction


def _route_to_appeal(claim: Claim, denial: Denial) -> Correction:
    explanation = (
        f"Payer denied claim {claim.claim_id} as not medically necessary "
        f"({', '.join(denial.carc_descriptions + denial.rarc_descriptions)}). "
        "This cannot be fixed with a corrected claim resubmission — it requires an appeal with supporting "
        "clinical documentation (radiographs, clinical notes, etc.)."
    )
    appeal_notes = (
        "Attach: clinical notes, imaging/radiographs, and a letter of medical necessity referencing the "
        "payer's Local Coverage Determination. Submit within the appeal deadline stated on the denial notice."
    )
    return Correction(
        category="medical_necessity",
        explanation=explanation,
        appeal_notes=appeal_notes,
    )
