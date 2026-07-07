from __future__ import annotations

"""
Patient Access Agent — scheduling, cancellations, no-show recovery.
Writes results to the data layer; returns a structured action + feed message.
"""
import json
import re
import uuid
from datetime import datetime, timedelta

from app.data.store import store
from app.llm import ask_claude

SYSTEM_PROMPT = """You are the Patient Access agent for a clinic's front desk.
You handle scheduling, cancellations, and no-show recovery. Given a request
and relevant patient/appointment context, decide the right action and write
a short, friendly message to the patient confirming it. Be concise."""

INTAKE_SYSTEM_PROMPT = """You are the Patient Access agent's intake parser.
Given a free-text request from or about a patient, and a list of known
patients with their upcoming appointments, decide what action is being
requested. Respond ONLY with valid JSON, no prose, in this exact shape:
{"intent": "schedule" | "cancel" | "unclear",
 "patient_id": "<id or null>",
 "appointment_id": "<id or null, required for cancel>",
 "provider": "<provider name or null, required for schedule>",
 "date_iso": "<ISO date or null, required for schedule>",
 "reasoning": "<one sentence on why you picked this>"}
If you can't confidently match a known patient or the request is ambiguous,
set intent to "unclear" and explain why in reasoning."""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group(0)) if match else {}


def handle_request(request_text: str) -> dict:
    """Parse a free-text request and route it to schedule/cancel, or flag as unclear."""
    patients = store.list_patients()
    appointments = store.list_appointments()
    context = {
        "patients": [{"id": p["id"], "name": p["name"]} for p in patients],
        "upcoming_appointments": [
            a for a in appointments if a["status"] == "booked"
        ],
    }

    parsed_raw = ask_claude(
        INTAKE_SYSTEM_PROMPT,
        f"Request: \"{request_text}\"\n\nContext: {json.dumps(context)}",
    )
    parsed = _extract_json(parsed_raw)
    intent = parsed.get("intent", "unclear")

    if intent == "schedule" and parsed.get("patient_id") and parsed.get("provider") and parsed.get("date_iso"):
        result = schedule_appointment(parsed["patient_id"], parsed["provider"], parsed["date_iso"])
        result["parsed_intent"] = parsed
        return result

    if intent == "cancel" and parsed.get("appointment_id"):
        result = cancel_appointment(parsed["appointment_id"])
        result["parsed_intent"] = parsed
        return result

    return {
        "action": "unclear",
        "feed_message": f"Couldn't confidently act on request: \"{request_text}\"",
        "parsed_intent": parsed,
        "requires_approval": True,
    }


def schedule_appointment(patient_id: str, provider: str, date_iso: str) -> dict:
    patient = store.get_patient(patient_id)
    if not patient:
        return {"action": "error", "message": f"Patient {patient_id} not found"}

    appt = {
        "id": f"appt_{uuid.uuid4().hex[:8]}",
        "patient_id": patient_id,
        "provider": provider,
        "date": date_iso,
        "status": "booked",
    }
    store.create_appointment(appt)

    confirmation = ask_claude(
        SYSTEM_PROMPT,
        f"Patient {patient['name']} just booked an appointment with {provider} "
        f"on {date_iso}. Write a one-sentence confirmation message to read back to them.",
    )

    return {
        "action": "scheduled",
        "appointment": appt,
        "feed_message": f"Booked {patient['name']} with {provider} on {date_iso}",
        "confirmation": confirmation,
    }


def cancel_appointment(appointment_id: str, offer_rebook: bool = True) -> dict:
    appt = store.get_appointment(appointment_id)
    if not appt:
        return {"action": "error", "message": f"Appointment {appointment_id} not found"}

    store.update_appointment(appointment_id, status="cancelled")
    patient = store.get_patient(appt["patient_id"])

    result = {
        "action": "cancelled",
        "appointment_id": appointment_id,
        "feed_message": f"Cancelled {patient['name']}'s appointment, slot reopened"
        + (" & rebooking offered" if offer_rebook else ""),
    }

    if offer_rebook:
        result["rebook_offer"] = ask_claude(
            SYSTEM_PROMPT,
            f"Patient {patient['name']} just cancelled their {appt['date']} appointment "
            f"with {appt['provider']}. Write a one-sentence rebooking offer.",
        )

    return result


def recover_no_shows() -> list[dict]:
    """Scan for no-shows, attempt rebooking with a personalized outreach message."""
    no_shows = store.list_appointments(status="no_show")
    recovered = []

    for appt in no_shows:
        patient = store.get_patient(appt["patient_id"])
        if not patient:
            continue

        new_date = (datetime.now() + timedelta(days=3)).replace(
            hour=10, minute=0, second=0, microsecond=0
        ).isoformat()

        new_appt = {
            "id": f"appt_{uuid.uuid4().hex[:8]}",
            "patient_id": patient["id"],
            "provider": appt["provider"],
            "date": new_date,
            "status": "booked",
        }
        store.create_appointment(new_appt)
        store.update_appointment(appt["id"], status="no_show_recovered")

        outreach = ask_claude(
            SYSTEM_PROMPT,
            f"Patient {patient['name']} missed their appointment on {appt['date']}. "
            f"We rebooked them for {new_date} with {appt['provider']}. "
            f"Write a one-sentence personalized rebooking confirmation message.",
        )

        recovered.append({
            "action": "no_show_recovered",
            "original_appointment_id": appt["id"],
            "new_appointment": new_appt,
            "feed_message": f"No-show recovered: {patient['name']} rebooked for {new_date[:10]}",
            "outreach_message": outreach,
        })

    return recovered
