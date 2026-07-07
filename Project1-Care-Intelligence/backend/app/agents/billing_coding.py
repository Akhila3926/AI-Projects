from __future__ import annotations
"""
Billing & Coding Agent — assigns ICD-10/CPT codes from an encounter note,
scrubs the resulting claim, fixes issues, and submits the claim to the DB.
"""
import json
import re
import uuid
from datetime import datetime

from app.data.store import store
from app.llm import ask_claude

CODING_SYSTEM_PROMPT = """You are a certified medical coder. Given a clinical
encounter note, assign the correct ICD-10 diagnosis codes and CPT procedure
codes. Respond ONLY with valid JSON in this exact shape, no prose:
{"icd10": ["<code>", ...], "cpt": ["<code>", ...], "amount": <estimated total charge as a number>}
"""

SCRUB_CHECKLIST = [
    "diagnosis codes are present and non-empty",
    "procedure codes are present and non-empty",
    "diagnosis codes are clinically consistent with procedure codes",
    "no missing modifiers for procedures that typically require them",
    "billed amount is reasonable for the procedures listed",
]

SCRUB_SYSTEM_PROMPT = f"""You are a claims scrubber. Check a coded claim
against this checklist:
{chr(10).join(f"- {c}" for c in SCRUB_CHECKLIST)}
Respond ONLY with valid JSON, no prose:
{{"issues": ["<issue description>", ...], "fixed_codes": {{"icd10": [...], "cpt": [...]}} or null}}
If there are no issues, return {{"issues": [], "fixed_codes": null}}.
If you find issues you can confidently fix, provide corrected codes in fixed_codes.
"""

# In-memory audit trail for billing actions
_audit_log: list[dict] = []


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group(0)) if match else {}


def _audit(action: str, claim_id: str, encounter_id: str, patient_name: str,
           amount: float, issues: list, caught_and_fixed: bool) -> None:
    _audit_log.insert(0, {
        "timestamp":      datetime.utcnow().isoformat(),
        "action":         action,
        "claim_id":       claim_id,
        "encounter_id":   encounter_id,
        "patient":        patient_name,
        "amount":         amount,
        "issues_found":   issues,
        "caught_and_fixed": caught_and_fixed,
    })
    if len(_audit_log) > 200:
        _audit_log.pop()


def get_audit_log() -> list[dict]:
    return list(_audit_log)


def code_and_scrub_encounter(encounter_id: str) -> dict:
    encounter = store.get_encounter(encounter_id)
    if not encounter:
        return {"action": "error", "message": f"Encounter {encounter_id} not found"}

    patient      = store.get_patient(encounter["patient_id"])
    patient_name = patient["name"] if patient else encounter["patient_id"]

    # 1. Assign codes via LLM
    coding_response = ask_claude(
        CODING_SYSTEM_PROMPT,
        f"Notes: {encounter.get('notes', '')}\n"
        f"Diagnoses noted: {', '.join(encounter.get('diagnoses') or [])}\n"
        f"Procedures noted: {', '.join(encounter.get('procedures') or [])}",
    )
    codes  = _extract_json(coding_response)
    icd10  = codes.get("icd10", [])
    cpt    = codes.get("cpt", [])
    amount = float(codes.get("amount", 0))

    # 2. Scrub
    scrub_response = ask_claude(
        SCRUB_SYSTEM_PROMPT,
        f"Diagnosis codes: {icd10}\nProcedure codes: {cpt}\nBilled amount: {amount}",
    )
    scrub_result   = _extract_json(scrub_response)
    issues         = scrub_result.get("issues", [])
    fixed_codes    = scrub_result.get("fixed_codes")

    caught_and_fixed = bool(issues and fixed_codes)
    if caught_and_fixed:
        icd10 = fixed_codes.get("icd10", icd10)
        cpt   = fixed_codes.get("cpt", cpt)

    # 3. Create claim and update DB status to Submitted
    claim_id = f"C{uuid.uuid4().hex[:6].upper()}"
    claim = {
        "id":           claim_id,
        "encounter_id": encounter_id,
        "patient_id":   encounter["patient_id"],
        "payer_id":     patient["payer_id"] if patient else "",
        "status":       "submitted",
        "codes":        {"icd10": icd10, "cpt": cpt},
        "amount":       amount,
        "scrub_issues": issues,
        "denial_reason": None,
    }

    # Persist: update the encounter row's claim status in DB
    store.update_claim_by_encounter(encounter_id, status="submitted",
                                    icd10=", ".join(icd10), cpt=", ".join(cpt), amount=amount)

    # 4. Audit trail
    _audit("coded_and_submitted", claim_id, encounter_id, patient_name, amount, issues, caught_and_fixed)

    feed_message = (
        f"Claim {claim_id} for {patient_name}: caught & fixed {len(issues)} issue(s), submitted clean"
        if caught_and_fixed else
        f"Claim {claim_id} for {patient_name} — ICD-10/CPT assigned, scrubbed, submitted · ${amount:,.0f}"
    )

    return {
        "action":          "coded_and_submitted",
        "claim":           claim,
        "caught_and_fixed": caught_and_fixed,
        "issues_found":    issues,
        "icd10":           icd10,
        "cpt":             cpt,
        "amount":          amount,
        "patient":         patient_name,
        "feed_message":    feed_message,
    }
