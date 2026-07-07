from __future__ import annotations
"""Prior Authorization Agent — checks if procedures need auth, submits requests, tracks status."""

import random
from datetime import datetime

from app.data.store import store

# Appointment types that require prior authorization
REQUIRES_AUTH_TYPES = {"diagnostic test", "therapy session"}

# Departments that require prior authorization
REQUIRES_AUTH_DEPTS = {"radiology", "physical therapy", "cardiology", "orthopedics"}

# Payers that are stricter (lower approval rate)
STRICT_PAYERS = {"united", "aetna", "cigna", "humana", "anthem"}

# In-memory store: appointment_id -> auth record
_auth_requests: dict[str, dict] = {}


def needs_prior_auth(appt_type: str, department: str) -> bool:
    """Return True if this appointment type or department requires prior auth."""
    return (
        appt_type.lower() in REQUIRES_AUTH_TYPES or
        department.lower() in REQUIRES_AUTH_DEPTS
    )


def _simulate_payer_decision(payer: str) -> str:
    """Simulate payer approving or denying the auth request."""
    payer_lower = payer.lower()
    is_strict = any(p in payer_lower for p in STRICT_PAYERS)
    approve_chance = 0.55 if is_strict else 0.78
    return "approved" if random.random() < approve_chance else "denied"


def submit_auth_request(appointment_id: str, patient_name: str,
                         procedure: str, payer: str) -> dict:
    """Submit a prior auth request and get simulated payer decision."""
    if appointment_id in _auth_requests:
        return _auth_requests[appointment_id]

    decision = _simulate_payer_decision(payer)
    record = {
        "appointment_id": appointment_id,
        "patient_name":   patient_name,
        "procedure":      procedure,
        "payer":          payer,
        "status":         decision,
        "submitted_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reason":         _denial_reason(procedure) if decision == "denied" else None,
    }
    _auth_requests[appointment_id] = record
    return record


def _denial_reason(procedure: str) -> str:
    reasons = [
        "Not medically necessary per payer guidelines",
        "Alternative treatment required first",
        "Missing clinical documentation",
        "Outside covered benefit",
    ]
    return random.choice(reasons)


def get_auth_status(appointment_id: str) -> dict | None:
    return _auth_requests.get(appointment_id)


def list_auth_requests() -> list[dict]:
    return list(_auth_requests.values())


def run_autonomous_prior_auth() -> dict:
    """
    Scan all booked appointments, check if they need prior auth,
    submit requests for any that haven't been checked yet.
    """
    appointments = store.list_appointments(status="booked")
    patients = {p["id"]: p for p in store.list_patients()}

    submitted = 0
    approved  = 0
    denied    = 0
    skipped   = 0

    for appt in appointments:
        appt_id = appt.get("id", "")

        # Already processed
        if appt_id in _auth_requests:
            skipped += 1
            continue

        patient      = patients.get(appt.get("patient_id", ""), {})
        patient_name = patient.get("name", "Unknown")
        payer        = patient.get("payer", "Unknown")
        appt_type    = appt.get("type", "General Visit")
        department   = appt.get("department", "")

        if not needs_prior_auth(appt_type, department):
            skipped += 1
            continue

        procedure = f"{appt_type} — {department}" if department else appt_type
        result = submit_auth_request(appt_id, patient_name, procedure, payer)
        submitted += 1

        if result["status"] == "approved":
            approved += 1
        else:
            denied += 1

    return {
        "submitted": submitted,
        "approved":  approved,
        "denied":    denied,
        "skipped":   skipped,
    }
