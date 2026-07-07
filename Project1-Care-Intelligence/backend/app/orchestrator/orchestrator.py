from __future__ import annotations

"""
Orchestrator — the "workforce" brain. Routes triggers to agents, chains
their outputs, logs every step to the activity feed, tracks outcome
counters, and holds an approvals queue for human-in-the-loop steps.
"""
import json
import re
import threading
import uuid
from datetime import datetime, timezone, timedelta

from app.agents import patient_access, billing_coding, denial_management
from app.data.store import store
from app.llm import ask_claude

_lock = threading.Lock()

_feed: list[dict] = []
_approvals: list[dict] = []
_outcomes = {
    "appointments_recovered": 0,
    "revenue_recovered": 0.0,
    "denials_overturned": 0,
    "hours_saved": 0.0,
}


def _init_demo() -> None:
    """Seed realistic historical activity so the demo opens with a live-looking feed."""
    now = datetime.now(timezone.utc)
    entries = [
        (95,  "Claim submitted for Marcus Lee — BCBS · $410 · ICD-10 M25.561, CPT 73721", "done"),
        (88,  "No-show recovered: Priya Patel — rebooked with Dr. Chen for next week", "done"),
        (75,  "Claim submitted for Sarah Jenkins — Aetna · $145 · ICD-10 J45.909", "done"),
        (60,  "Denial detected: James Carter UHC $540 — CO-97 bundling conflict caught and flagged", "caught_problem"),
        (48,  "Scrub issue fixed: modifier added to CPT 97110 for Emily Tran before BCBS submission", "caught_problem"),
        (35,  "Appeal drafted for Olivia Bennett UHC $95 — CO-50 medical necessity, queued for review", "needs_approval"),
        (22,  "No-show recovered: Angela Brooks — rebooked with Dr. Alvarez", "done"),
        (10,  "Denial overturned: Angela Brooks BCBS $185 appealed — $185 recovered", "done"),
        (4,   "Claim submitted for Henry Adams — Cigna · $350 · ICD-10 S83.0", "done"),
    ]
    with _lock:
        for mins, msg, kind in reversed(entries):
            _feed.append({
                "timestamp": (now - timedelta(minutes=mins)).isoformat(),
                "message": msg,
                "kind": kind,
            })
        recovered_appts = store.list_appointments(status="recovered")
        denied_claims   = store.list_claims(status="denied")
        appealed_claims = store.list_claims(status="appealed")
        submitted_claims = store.list_claims(status="submitted")
        _outcomes["appointments_recovered"] = len(recovered_appts)
        _outcomes["revenue_recovered"] = round(
            sum((c.get("charges", 0) - c.get("balance", 0)) for c in submitted_claims), 2
        )
        _outcomes["denials_overturned"] = len(appealed_claims)
        _outcomes["hours_saved"] = round(
            (len(recovered_appts) + len(appealed_claims) + len(denied_claims)) * 0.5, 1
        )

_init_demo()


def _log(message: str, kind: str = "done") -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "kind": kind,  # done | needs_approval | caught_problem
    }
    with _lock:
        _feed.insert(0, entry)
    return entry


def get_feed() -> list[dict]:
    return _feed


def get_outcomes() -> dict:
    return _outcomes


def get_approvals() -> list[dict]:
    return _approvals


# ---- Patient Access triggers ----

def run_patient_access_schedule(patient_id: str, provider: str, date_iso: str) -> dict:
    result = patient_access.schedule_appointment(patient_id, provider, date_iso)
    _log(result.get("feed_message", "Scheduled appointment"))
    with _lock:
        _outcomes["hours_saved"] += 0.1
    return result


def run_patient_access_request(request_text: str) -> dict:
    result = patient_access.handle_request(request_text)
    kind = "needs_approval" if result["action"] == "unclear" else "done"
    _log(result.get("feed_message", "Handled patient request"), kind=kind)
    if result["action"] == "unclear":
        with _lock:
            _approvals.append({
                "id": f"approval_{uuid.uuid4().hex[:8]}",
                "type": "unclear_request",
                "request_text": request_text,
                "parsed_intent": result.get("parsed_intent"),
            })
    elif result["action"] == "scheduled":
        with _lock:
            _outcomes["hours_saved"] += 0.1
    return result


def dismiss_approval(approval_id: str) -> dict:
    with _lock:
        before = len(_approvals)
        _approvals[:] = [a for a in _approvals if a["id"] != approval_id]
        removed = len(_approvals) < before
    if not removed:
        return {"action": "error", "message": f"Approval {approval_id} not found"}
    _log(f"Dismissed approval {approval_id}")
    return {"action": "dismissed", "approval_id": approval_id}


def run_patient_access_cancel(appointment_id: str) -> dict:
    result = patient_access.cancel_appointment(appointment_id)
    _log(result.get("feed_message", "Cancelled appointment"))
    return result


def run_no_show_recovery() -> dict:
    recovered = patient_access.recover_no_shows()
    for r in recovered:
        _log(r["feed_message"])
    with _lock:
        _outcomes["appointments_recovered"] += len(recovered)
        _outcomes["hours_saved"] += 0.25 * len(recovered)
    return {"recovered": recovered}


# ---- Billing & Coding trigger ----

def run_billing_coding(encounter_id: str) -> dict:
    result = billing_coding.code_and_scrub_encounter(encounter_id)
    if result["action"] == "error":
        _log(result["message"], kind="needs_approval")
        return result

    kind = "caught_problem" if result["caught_and_fixed"] else "done"
    _log(result["feed_message"], kind=kind)
    with _lock:
        _outcomes["hours_saved"] += 0.3

    return result


def run_all_denial_appeals() -> dict:
    """Diagnose and draft appeals for all currently denied claims."""
    denied_claims = store.list_claims(status="denied")
    results = []
    for claim in denied_claims:
        result = run_denial_diagnosis(claim["id"])
        results.append(result)
    return {"processed": len(results), "results": results}


def run_billing_all_pending() -> dict:
    """Process all encounters that don't yet have a claim."""
    encounters = store.list_encounters()
    existing_enc_ids = {c["encounter_id"] for c in store.list_claims()}
    pending = [e for e in encounters if e["id"] not in existing_enc_ids]
    results = []
    for enc in pending:
        result = run_billing_coding(enc["id"])
        results.append(result)
    return {"processed": len(results), "results": results}


# ---- Denial Management triggers ----

def run_denial_diagnosis(claim_id: str) -> dict:
    result = denial_management.diagnose_and_draft_appeal(claim_id)
    if result["action"] == "error":
        _log(result["message"], kind="needs_approval")
        return result

    _log(result["feed_message"], kind="needs_approval")
    approval = {
        "id": f"approval_{claim_id}",
        "type": "appeal_resubmission",
        "claim_id": claim_id,
        "appeal_letter": result["appeal_letter"],
        "diagnosis": result["diagnosis"],
    }
    with _lock:
        _approvals.append(approval)
    return result


def approve_denial_resubmission(claim_id: str) -> dict:
    result = denial_management.resubmit_appeal(claim_id)
    if result["action"] == "error":
        return result

    _log(result["feed_message"])
    claim = store.get_claim(claim_id)
    with _lock:
        _approvals[:] = [a for a in _approvals if a.get("claim_id") != claim_id]
        _outcomes["denials_overturned"] += 1
        _outcomes["revenue_recovered"] += claim["amount"] if claim else 0
        _outcomes["hours_saved"] += 0.5
    return result


# ---- The cascade ----

def run_cascade(patient_id: str, provider: str, date_iso: str) -> dict:
    """New visit -> Patient Access (book) -> Billing & Coding (code+scrub)
    -> Denial Management (fires only if the resulting claim is denied)."""
    steps = []

    booking = run_patient_access_schedule(patient_id, provider, date_iso)
    steps.append({"step": "patient_access", "result": booking})

    if booking["action"] != "scheduled":
        return {"steps": steps, "stopped_at": "patient_access"}

    appointment = booking["appointment"]
    encounter = store.create_encounter({
        "id": f"enc_{uuid.uuid4().hex[:8]}",
        "patient_id": patient_id,
        "appointment_id": appointment["id"],
        "provider": provider,
        "date": date_iso[:10],
        "visit_type": "office_visit",
        "chief_complaint": "Routine office visit",
        "notes": "Patient seen for a routine office visit. No acute complaints reported. "
                 "Standard evaluation performed, vitals reviewed, follow-up as needed.",
        "diagnoses": ["routine health exam"],
        "procedures": ["office visit - established patient, level 2"],
    })
    store.update_appointment(appointment["id"], status="completed")

    billing = run_billing_coding(encounter["id"])
    steps.append({"step": "billing_coding", "result": billing})

    claim = billing.get("claim")
    if claim and claim.get("status") == "denied":
        denial = run_denial_diagnosis(claim["id"])
        steps.append({"step": "denial_management", "result": denial})

    return {"steps": steps, "stopped_at": None}


# ---- Unified chat router ----

CHAT_ROUTER_SYSTEM_PROMPT = """You are the intelligent router for a clinic's AI agent workforce.
Given a staff member's free-text message and a snapshot of current work items, decide which agent or action handles it:

- "patient_access": scheduling, cancelling, or rebooking an appointment for a SPECIFIC named patient
- "billing_coding": coding & submitting a claim for a SPECIFIC patient's encounter
- "denial_management": diagnosing and drafting an appeal for a SPECIFIC patient's denied claim
- "bulk_billing": "process today's visits", "process all completed visits", "code all encounters", "process pending claims", "bill all"
- "no_show_recovery": "recover no shows", "follow up no-shows", "contact missed appointments", "rebook no-shows"
- "run_workflow": "run today's workflow", "run full workflow", "run everything", "cascade", "process everything today"
- "show_summary": "generate summary", "how are we doing", "today's summary", "show outcomes", "show results", "summarize"
- "show_approvals": "show approvals", "pending approvals", "what needs review", "what needs approval"
- "data_query": looking up, listing, or filtering data — patients by payer, denied/submitted/appealed claims, appointments by status, encounters, new patients, etc. Examples: "pull up Aetna patients", "show denied claims", "list no-show appointments", "get all patients", "how many claims are submitted"
- "unclear": none of the above fit confidently

For patient_access / billing_coding / denial_management, identify the patient by name from the snapshot and return exactly as given.
Respond ONLY with valid JSON (no prose):
{"agent": "...", "patient_name": "<exact name from snapshot or null>", "reasoning": "<one sentence>"}
"""


def _find_patient_id_by_name(name: str | None) -> str | None:
    if not name:
        return None
    name_lower = name.lower()
    for p in store.list_patients():
        if name_lower in p["name"].lower() or p["name"].lower() in name_lower:
            return p["id"]
    return None


def classify_message(text: str) -> dict:
    """Classify a free-text message → routing decision dict."""
    draft_encounters = [
        e for e in store.list_encounters()
        if all(c["encounter_id"] != e["id"] for c in store.list_claims())
    ]
    denied_claims = store.list_claims(status="denied")
    patients = store.list_patients()

    snapshot = {
        "total_patients": len(patients),
        "sample_patients": [p["name"] for p in patients[:10]],
        "encounters_awaiting_billing": len(draft_encounters),
        "denied_claims_count": len(denied_claims),
        "sample_denied_claims": [
            {"patient": (store.get_patient(c["patient_id"]) or {}).get("name", c["patient_id"]), "amount": c["amount"]}
            for c in denied_claims[:5]
        ],
    }

    raw = ask_claude(
        CHAT_ROUTER_SYSTEM_PROMPT,
        f"Message: \"{text}\"\n\nSnapshot: {json.dumps(snapshot)}",
    )
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(match.group(0)) if match else {"agent": "unclear", "reasoning": "Could not parse router output"}


def dispatch_classified(routed: dict, text: str) -> dict:
    """Execute the action determined by classify_message and return a reply dict."""
    agent = routed.get("agent", "unclear")
    patient_id = _find_patient_id_by_name(routed.get("patient_name"))

    if agent == "patient_access":
        result = patient_access.handle_request(text)
        kind = "needs_approval" if result["action"] == "unclear" else "done"
        _log(result.get("feed_message", "Handled patient request"), kind=kind)
        if result["action"] == "unclear":
            with _lock:
                _approvals.append({
                    "id": f"approval_{uuid.uuid4().hex[:8]}",
                    "type": "unclear_request",
                    "request_text": text,
                    "parsed_intent": result.get("parsed_intent"),
                })
        elif result["action"] == "scheduled":
            with _lock:
                _outcomes["hours_saved"] += 0.1
        reply = result.get("confirmation") or result.get("rebook_offer") or result.get("feed_message")
        return {"agent": "patient_access", "reply": reply, "result": result}

    if agent == "billing_coding" and patient_id:
        draft_encounters = [
            e for e in store.list_encounters()
            if all(c["encounter_id"] != e["id"] for c in store.list_claims())
        ]
        encounter = next((e for e in draft_encounters if e["patient_id"] == patient_id), None)
        if encounter:
            result = run_billing_coding(encounter["id"])
            return {"agent": "billing_coding", "reply": result.get("feed_message", "Claim processed."), "result": result}

    if agent == "denial_management" and patient_id:
        denied_claims = store.list_claims(status="denied")
        claim = next((c for c in denied_claims if c["patient_id"] == patient_id), None)
        if claim:
            result = run_denial_diagnosis(claim["id"])
            return {
                "agent": "denial_management",
                "reply": "I've drafted an appeal for that denied claim — it's waiting in the approvals queue for sign-off.",
                "result": result,
            }

    if agent == "bulk_billing":
        result = run_billing_all_pending()
        n = result["processed"]
        if n == 0:
            reply = "No pending encounters found — all visits have already been coded and submitted."
        else:
            reply = (
                f"Processed {n} encounter{'s' if n != 1 else ''}. "
                f"ICD-10 and CPT codes assigned, claims scrubbed against payer rules, and clean claims submitted."
            )
        return {"agent": "billing_coding", "reply": reply, "result": result}

    if agent == "no_show_recovery":
        result = run_no_show_recovery()
        n = len(result.get("recovered", []))
        if n == 0:
            reply = "No no-show appointments found to recover at this time."
        else:
            reply = (
                f"Recovered {n} no-show appointment{'s' if n != 1 else ''}. "
                f"Patients have been contacted and rebooked."
            )
        return {"agent": "patient_access", "reply": reply, "result": result}

    if agent == "run_workflow":
        demo_patients = store.list_patients()
        if demo_patients:
            p = demo_patients[0]
            result = run_cascade(p["id"], "Dr. Alvarez", datetime.now(timezone.utc).isoformat())
            steps_done = len(result.get("steps", []))
            reply = (
                f"Full workflow complete for **{p['name']}**. "
                f"Appointment booked with Dr. Alvarez, encounter coded with ICD-10 and CPT codes, "
                f"claim scrubbed and submitted — {steps_done} agent{'s' if steps_done != 1 else ''} involved."
            )
            return {"agent": "run_workflow", "reply": reply, "result": result}

    if agent == "show_summary":
        o = get_outcomes()
        feed_snippet = _feed[:3]
        recent = "; ".join(f["message"] for f in feed_snippet) if feed_snippet else "No recent activity"
        reply = (
            f"Here's today's operational summary:\n\n"
            f"• **{o['appointments_recovered']} appointments recovered** from no-shows\n"
            f"• **${o['revenue_recovered']:,.0f} revenue recovered** through appeal resubmissions\n"
            f"• **{o['denials_overturned']} denials overturned** after appeal\n"
            f"• **{o['hours_saved']:.1f} staff hours saved** by autonomous agents\n\n"
            f"Recent activity: {recent}\n\n"
            f"All three agents are operational and monitoring for new work items."
        )
        return {"agent": "show_summary", "reply": reply, "result": o}

    if agent == "data_query":
        result = handle_data_query(text)
        return result

    if agent == "show_approvals":
        current = get_approvals()
        if not current:
            reply = "No items currently need approval. Everything is running smoothly."
        else:
            lines = []
            for a in current[:5]:
                if a["type"] == "appeal_resubmission":
                    lines.append(f"• Appeal resubmission for claim **{a['claim_id']}** — ready to send")
                else:
                    snippet = (a.get("request_text") or "")[:60]
                    lines.append(f"• Unclear request: \"{snippet}...\" — needs staff review")
            reply = f"**{len(current)} item{'s' if len(current) != 1 else ''} awaiting approval:**\n\n" + "\n".join(lines)
        return {"agent": "show_approvals", "reply": reply, "result": current}

    # Fallback: unclear
    _log(f"Chat message needs review: \"{text}\"", kind="needs_approval")
    with _lock:
        _approvals.append({
            "id": f"approval_{uuid.uuid4().hex[:8]}",
            "type": "unclear_request",
            "request_text": text,
            "parsed_intent": routed,
        })
    return {
        "agent": "unclear",
        "reply": (
            "I couldn't confidently match that to an open work item. "
            "I've flagged it for staff review in the approvals queue. "
            "Try asking me to process visits, recover no-shows, run the full workflow, or handle a specific patient."
        ),
        "result": routed,
    }


def _claim_payment(claim: dict) -> dict:
    """Derive payment breakdown from claim status (no stored payment fields needed)."""
    amount = claim.get("amount") or 0
    status = claim.get("status", "")
    if status == "submitted":
        paid        = round(amount * 0.75, 2)
        adjustment  = round(amount * 0.10, 2)
        patient_res = round(amount - paid - adjustment, 2)
        balance     = patient_res
    elif status in ("appealed", "appeal_pending_approval"):
        paid        = 0.0
        adjustment  = 0.0
        patient_res = 0.0
        balance     = amount   # pending — full amount at risk
    elif status == "denied":
        paid        = 0.0
        adjustment  = 0.0
        patient_res = 0.0
        balance     = amount   # unpaid
    else:  # draft / unknown
        paid = adjustment = patient_res = balance = 0.0
    return {"paid": paid, "adjustment": adjustment,
            "patient_responsibility": patient_res, "balance": balance}


def _fmt(n: float) -> str:
    return f"${n:,.0f}"


def handle_data_query(text: str, context: str = "") -> dict:
    """Answer data-lookup questions about patients, claims, appointments, encounters."""
    t = text.lower()
    full_text = (context + " " + text).lower() if context else t

    all_patients     = store.list_patients()
    all_claims       = store.list_claims()
    all_appointments = store.list_appointments()
    all_encounters   = store.list_encounters()
    all_payers       = store.list_payers()

    payer_map   = {p["id"]: p for p in all_payers}
    patient_map = {p["id"]: p for p in all_patients}

    # ── Analytics / aggregation questions (answered before row-level queries) ──
    _is_analytics = any(w in t for w in [
        "denial rate", "recovery rate", "by payer", "per payer", "breakdown", "distribution",
        "performance", "stats", "statistics", "metrics", "analysis", "report",
        "which payer", "best payer", "worst payer", "top payer", "payer performance",
        "top patient", "highest balance", "most denied", "revenue by", "claims by",
        "outstanding balance", "total revenue", "total billed", "total paid",
        "how much revenue", "how much billed", "how much paid", "how much outstanding",
        "average claim", "avg claim", "average balance",
    ])

    if _is_analytics:
        # Build per-payer stats
        payer_stats = {}
        for pname in set(p["id"] for p in all_payers):
            pc = [c for c in all_claims if c.get("payer_id") == pname]
            denied  = [c for c in pc if c.get("status") == "denied"]
            submitted = [c for c in pc if c.get("status") in ("submitted", "approved", "paid")]
            billed  = sum(c.get("amount", 0) for c in pc)
            recovered = sum((c.get("charges", 0) - c.get("balance", 0)) for c in submitted)
            payer_stats[pname] = {
                "name": pname,
                "total": len(pc),
                "denied": len(denied),
                "denial_rate": round(len(denied) / len(pc) * 100, 1) if pc else 0,
                "billed": billed,
                "recovered": recovered,
            }

        sorted_by_denial = sorted(payer_stats.values(), key=lambda x: x["denial_rate"], reverse=True)
        sorted_by_billed = sorted(payer_stats.values(), key=lambda x: x["billed"], reverse=True)

        total_billed    = sum(c.get("amount", 0) for c in all_claims)
        total_denied    = sum(1 for c in all_claims if c.get("status") == "denied")
        total_submitted = [c for c in all_claims if c.get("status") in ("submitted", "approved", "paid")]
        total_recovered = sum((c.get("charges", 0) - c.get("balance", 0)) for c in total_submitted)
        denial_rate     = round(total_denied / len(all_claims) * 100, 1) if all_claims else 0
        avg_claim       = round(total_billed / len(all_claims), 0) if all_claims else 0

        # Which payer has highest denial rate?
        if any(w in t for w in ["which payer", "worst payer", "highest denial", "most denial", "denial rate"]):
            lines = ["**Denial Rate by Payer:**\n"]
            for p in sorted_by_denial:
                bar = "█" * int(p["denial_rate"] / 5)
                lines.append(f"• **{p['name']}** — {p['denial_rate']}% ({p['denied']}/{p['total']} claims) {bar}")
            lines.append(f"\n**Overall denial rate: {denial_rate}%** across {len(all_claims):,} claims")
            suggestions = [f"Show denied {sorted_by_denial[0]['name']} claims", "Draft appeals for all denied claims"]
            return {"agent": "data_query", "reply": "\n".join(lines), "suggestions": suggestions}

        # Revenue / billed / paid / outstanding
        if any(w in t for w in ["revenue", "billed", "paid", "outstanding", "balance", "how much"]):
            lines = ["**Revenue Summary by Payer:**\n"]
            for p in sorted_by_billed:
                recovery_pct = round(p["recovered"] / p["billed"] * 100, 1) if p["billed"] else 0
                lines.append(f"• **{p['name']}** — Billed {_fmt(p['billed'])} · Recovered {_fmt(p['recovered'])} ({recovery_pct}%)")
            outstanding = total_billed - total_recovered
            lines.append(f"\n**Total billed: {_fmt(total_billed)}** · Recovered: {_fmt(total_recovered)} · Outstanding: {_fmt(outstanding)}")
            return {"agent": "data_query", "reply": "\n".join(lines), "suggestions": ["Show denied claims", "Draft appeals for all denied claims"]}

        # Top patients by balance / most denied
        if any(w in t for w in ["top patient", "highest balance", "most denied patient"]):
            pat_stats = []
            for pid, pat in patient_map.items():
                pc = [c for c in all_claims if c.get("patient_id") == pid]
                denied_n = sum(1 for c in pc if c.get("status") == "denied")
                balance  = sum(c.get("balance", 0) for c in pc)
                billed   = sum(c.get("amount", 0) for c in pc)
                pat_stats.append({"name": pat["name"], "payer": pat.get("payer_id",""), "denied": denied_n, "balance": balance, "billed": billed})
            if "denied" in t or "most denied" in t:
                pat_stats.sort(key=lambda x: x["denied"], reverse=True)
                lines = ["**Top Patients by Denied Claims:**\n"]
                for p in pat_stats[:20]:
                    if p["denied"] == 0: break
                    lines.append(f"• **{p['name']}** ({p['payer']}) — {p['denied']} denied · {_fmt(p['billed'])} billed")
            else:
                pat_stats.sort(key=lambda x: x["balance"], reverse=True)
                lines = ["**Top Patients by Outstanding Balance:**\n"]
                for p in pat_stats[:20]:
                    if p["balance"] == 0: break
                    lines.append(f"• **{p['name']}** ({p['payer']}) — Balance {_fmt(p['balance'])} · Billed {_fmt(p['billed'])}")
            return {"agent": "data_query", "reply": "\n".join(lines), "suggestions": ["Show denied claims"]}

        # Average claim / general stats
        if any(w in t for w in ["average", "avg", "stats", "statistics", "metrics", "breakdown", "distribution", "performance", "report", "analysis"]):
            status_counts = {}
            for c in all_claims:
                s = c.get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            appt_counts = {}
            for a in all_appointments:
                s = a.get("status", "unknown")
                appt_counts[s] = appt_counts.get(s, 0) + 1

            lines = [
                "**Care Intelligence — Performance Overview**\n",
                f"**Patients:** {len(all_patients):,}",
                f"**Claims:** {len(all_claims):,} · Avg {_fmt(avg_claim)} · Total billed {_fmt(total_billed)}",
                f"**Denial rate:** {denial_rate}% ({total_denied:,} denied)",
                f"**Revenue recovered:** {_fmt(total_recovered)}\n",
                "**Claims by status:**",
            ]
            for s, n in sorted(status_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  • {s.replace('_',' ').title()}: {n:,}")
            lines.append("\n**Appointments by status:**")
            for s, n in sorted(appt_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  • {s.replace('_',' ').title()}: {n:,}")
            lines.append("\n**Denial rate by payer:**")
            for p in sorted_by_denial:
                lines.append(f"  • {p['name']}: {p['denial_rate']}% ({p['denied']} denied / {p['total']} total)")
            suggestions = ["Show denied claims", "Draft appeals for all denied claims", "Recover no-show appointments"]
            return {"agent": "data_query", "reply": "\n".join(lines), "suggestions": suggestions}

    # Build payer-name → payer-id lookup
    payer_name_to_id: dict = {}
    for p in all_payers:
        payer_name_to_id[p["name"].lower()] = p["id"]
        for word in p["name"].lower().split():
            if len(word) >= 4:
                payer_name_to_id[word] = p["id"]

    # Detect payer filter
    matched_payer_id = None
    for name, pid in payer_name_to_id.items():
        if name in t:
            matched_payer_id = pid
            break

    # Detect patient name filter
    matched_patient_ids: set = set()
    for p in all_patients:
        name_lower = p["name"].lower()
        parts = name_lower.split()
        if name_lower in full_text or any(part in full_text for part in parts if len(part) > 3):
            matched_patient_ids.add(p["id"])

    # Detect claim status filter
    _claim_status_kw = [
        ("denied",               "denied"),
        ("submitted",            "submitted"),
        ("appealed",             "appealed"),
        ("appeal pending",       "appeal_pending_approval"),
        ("pending approval",     "appeal_pending_approval"),
        ("draft",                "draft"),
    ]
    matched_claim_status = None
    for kw, status in _claim_status_kw:
        if kw in t:
            matched_claim_status = status
            break

    # Detect appointment status filter
    _appt_status_kw = [
        ("no show",    "no_show"),
        ("no-show",    "no_show"),
        ("noshow",     "no_show"),
        ("recovered",  "no_show_recovered"),
        ("booked",     "booked"),
        ("cancelled",  "cancelled"),
        ("canceled",   "cancelled"),
        ("completed",  "completed"),
    ]
    matched_appt_status = None
    for kw, status in _appt_status_kw:
        if kw in t:
            matched_appt_status = status
            break

    # Determine entity type
    asking_claims       = any(w in t for w in ["claim", "claims", "billing"])
    asking_patients     = any(w in t for w in ["patient", "patients"])
    asking_appointments = any(w in t for w in ["appointment", "appointments", "visit", "schedule"])
    asking_encounters   = any(w in t for w in ["encounter", "encounters"])
    count_only          = any(w in t for w in ["how many", "count", "number of", "total number", "how much", "total claims", "total patients", "total appointments", "total encounters"])

    # ── Claims ────────────────────────────────────────────────────────────
    if asking_claims or (matched_claim_status and not asking_patients and not asking_appointments) or (matched_patient_ids and not asking_patients and not asking_appointments):
        filtered = list(all_claims)
        if matched_payer_id:
            pat_ids = {p["id"] for p in all_patients if p.get("payer_id") == matched_payer_id}
            filtered = [c for c in filtered if c["patient_id"] in pat_ids]
        if matched_claim_status:
            filtered = [c for c in filtered if c.get("status") == matched_claim_status]
        if matched_patient_ids:
            filtered = [c for c in filtered if c["patient_id"] in matched_patient_ids]

        payer_label  = payer_map.get(matched_payer_id, {}).get("name", "") if matched_payer_id else ""
        status_label = (matched_claim_status or "").replace("_", " ").title() if matched_claim_status else ""
        qualifier    = " ".join(filter(None, [status_label, payer_label]))

        if count_only:
            total = sum(c.get("amount") or 0 for c in filtered)
            return {"agent": "data_query", "reply": f"There are **{len(filtered)} {qualifier + ' ' if qualifier else ''}claim{'s' if len(filtered) != 1 else ''}** totalling **${total:,.0f}**.", "suggestions": []}

        header = f"**{len(filtered)} {qualifier + ' ' if qualifier else ''}Claim{'s' if len(filtered) != 1 else ''}**\n\n"

        if not filtered:
            return {"agent": "data_query", "reply": header + "No claims match that filter.", "suggestions": []}

        total_billed  = sum(c.get("amount") or 0 for c in filtered)
        total_paid    = sum(c.get("paid_amount") if c.get("paid_amount") is not None else _claim_payment(c)["paid"] for c in filtered)
        total_balance = sum(max(0, (c.get("amount") or 0) - (c.get("paid_amount") or 0)) if c.get("paid_amount") is not None else _claim_payment(c)["balance"] for c in filtered)
        summary_line  = (
            f"Total billed: **${total_billed:,.0f}** · "
            f"Paid by payer: **${total_paid:,.0f}** · "
            f"Outstanding: **${total_balance:,.0f}**\n\n"
        )

        lines = []
        for c in filtered:
            pat    = patient_map.get(c["patient_id"], {})
            payer  = payer_map.get(pat.get("payer_id", ""), {})
            amount = c.get("amount") or 0
            paid   = c.get("paid_amount") if c.get("paid_amount") is not None else _claim_payment(c)["paid"]
            adj    = c.get("adjustment") if c.get("adjustment") is not None else _claim_payment(c)["adjustment"]
            balance = max(0, amount - paid - adj) if paid > 0 else (amount if c.get("status") in ("denied", "appealed", "appeal_pending_approval") else 0)

            status = c.get("status", "")
            status_icon = {"submitted": "✓", "denied": "✗", "appealed": "↩", "appeal_pending_approval": "⏳", "draft": "○"}.get(status, "·")
            status_str  = status.replace("_", " ")
            denial_str  = f" · **{c.get('denial_code')}**" if c.get("denial_code") else ""
            _codes_raw  = c.get("codes") or {}
            _icd10      = (_codes_raw.get("icd10", []) if isinstance(_codes_raw, dict) else [])
            _cpt        = (_codes_raw.get("cpt", [])   if isinstance(_codes_raw, dict) else [])
            codes       = " · ".join((c.get("icd10_codes") or _icd10)[:1] + (c.get("cpt_codes") or _cpt)[:1])

            # Compact single line: name — status · $billed · paid/balance info · codes
            fin = f"${amount:,.0f}"
            if paid > 0:
                fin += f" · paid ${paid:,.0f}"
                if balance > 0:
                    fin += f" · bal **${balance:,.0f}**"
            elif balance > 0:
                fin += f" · bal **${balance:,.0f}**"

            denial_col = f" · {c.get('denial_reason', '')}" if c.get("denial_reason") else ""
            lines.append(
                f"| {status_icon} {pat.get('name', c['patient_id'])} | {payer.get('name', pat.get('payer_id',''))} | {status_str}{denial_col} | {fin} |"
            )

        denied_count = sum(1 for c in filtered if c.get("status") == "denied")
        suggestions = []
        if denied_count > 0 and matched_claim_status != "denied":
            suggestions.append(f"Draft appeals for all {denied_count} denied claims")
        elif denied_count > 0:
            suggestions.append("Draft appeals for all denied claims")

        MAX_ROWS = 50
        shown  = lines[:MAX_ROWS]
        table_header = "| Patient | Payer | Status | Amount |\n|---|---|---|---|\n"
        more = f"\n\n_Showing {MAX_ROWS} of {len(filtered)} — ask for a specific payer or status to filter._" if len(lines) > MAX_ROWS else ""
        return {"agent": "data_query", "reply": header + summary_line + table_header + "\n".join(shown) + more, "suggestions": suggestions}

    # ── Appointments ──────────────────────────────────────────────────────
    if asking_appointments or matched_appt_status:
        filtered = list(all_appointments)
        if matched_payer_id:
            pat_ids = {p["id"] for p in all_patients if p.get("payer_id") == matched_payer_id}
            filtered = [a for a in filtered if a["patient_id"] in pat_ids]
        if matched_appt_status:
            filtered = [a for a in filtered if a.get("status") == matched_appt_status]
        if matched_patient_ids:
            filtered = [a for a in filtered if a["patient_id"] in matched_patient_ids]

        status_label = (matched_appt_status or "").replace("_", " ").title() if matched_appt_status else ""
        qualifier    = status_label
        header = f"**{len(filtered)} {qualifier + ' ' if qualifier else ''}Appointment{'s' if len(filtered) != 1 else ''}**\n\n"

        if count_only:
            return {"agent": "data_query", "reply": f"There are **{len(filtered)} {qualifier + ' ' if qualifier else ''}appointment{'s' if len(filtered) != 1 else ''}**.", "suggestions": []}

        if not filtered:
            return {"agent": "data_query", "reply": header + "No appointments match that filter.", "suggestions": []}

        lines = []
        for a in filtered:
            pat  = patient_map.get(a["patient_id"], {})
            date = (a.get("date") or "")[:16].replace("T", " at ")
            lines.append(f"• **{pat.get('name', a['patient_id'])}** — {a.get('provider', '—')} · {date} · {a.get('status', '').replace('_', ' ')}")

        no_shows = sum(1 for a in filtered if a.get("status") == "no_show")
        suggestions = ["Recover no-show appointments"] if no_shows > 0 and matched_appt_status != "no_show" else []
        MAX_ROWS = 50
        shown = lines[:MAX_ROWS]
        truncation = f"\n\n_Showing {MAX_ROWS} of {len(filtered)} — filter by status or patient name to narrow results._" if len(lines) > MAX_ROWS else ""
        return {"agent": "data_query", "reply": header + "\n".join(shown) + truncation, "suggestions": suggestions}

    # ── Encounters ────────────────────────────────────────────────────────
    if asking_encounters:
        claimedIds = {c["encounter_id"] for c in all_claims}
        filtered   = list(all_encounters)
        if matched_payer_id:
            pat_ids = {p["id"] for p in all_patients if p.get("payer_id") == matched_payer_id}
            filtered = [e for e in filtered if e["patient_id"] in pat_ids]
        if matched_patient_ids:
            filtered = [e for e in filtered if e["patient_id"] in matched_patient_ids]
        if "pending" in t or "uncoded" in t or "unprocessed" in t:
            filtered = [e for e in filtered if e["id"] not in claimedIds]

        header = f"**{len(filtered)} Encounter{'s' if len(filtered) != 1 else ''}**\n\n"
        if count_only:
            return {"agent": "data_query", "reply": f"There are **{len(filtered)} encounter{'s' if len(filtered) != 1 else ''}**.", "suggestions": []}
        if not filtered:
            return {"agent": "data_query", "reply": header + "No encounters match that filter.", "suggestions": []}

        lines = []
        for e in filtered:
            pat     = patient_map.get(e["patient_id"], {})
            coded   = " · ✓ Coded" if e["id"] in claimedIds else " · ⚠ Uncoded"
            lines.append(f"• **{pat.get('name', e['patient_id'])}** — {', '.join(e.get('diagnoses') or [e.get('notes','')[:40]])} · {e.get('date', '')} · {e.get('provider', '')}{coded}")

        uncoded = sum(1 for e in filtered if e["id"] not in claimedIds)
        suggestions = [f"Process all {uncoded} pending encounters"] if uncoded > 0 else []
        MAX_ROWS = 50
        shown = lines[:MAX_ROWS]
        truncation = f"\n\n_Showing {MAX_ROWS} of {len(filtered)} — filter by patient or provider to narrow results._" if len(lines) > MAX_ROWS else ""
        return {"agent": "data_query", "reply": header + "\n".join(shown) + truncation, "suggestions": suggestions}

    # ── Patients ──────────────────────────────────────────────────────────
    filtered = list(all_patients)
    if matched_payer_id:
        filtered = [p for p in all_patients if p.get("payer_id") == matched_payer_id]
    if matched_patient_ids and not asking_patients:
        filtered = [p for p in all_patients if p["id"] in matched_patient_ids]
    if "new patient" in t:
        filtered = [p for p in filtered if p.get("is_new_patient")]

    payer_label = payer_map.get(matched_payer_id, {}).get("name", "") if matched_payer_id else ""
    qualifier   = " ".join(filter(None, ["New" if "new patient" in t else "", payer_label]))
    header = f"**{len(filtered)} {qualifier + ' ' if qualifier else ''}Patient{'s' if len(filtered) != 1 else ''}**\n\n"

    if count_only:
        return {"agent": "data_query", "reply": f"There are **{len(filtered)} {qualifier + ' ' if qualifier else ''}patient{'s' if len(filtered) != 1 else ''}**.", "suggestions": []}

    if not filtered:
        return {"agent": "data_query", "reply": header + "No patients match that filter.", "suggestions": []}

    lines = []
    for p in filtered:
        payer      = payer_map.get(p.get("payer_id", ""), {})
        pat_claims = [c for c in all_claims if c["patient_id"] == p["id"]]
        denied_n   = sum(1 for c in pat_claims if c.get("status") == "denied")
        total_billed  = sum(c.get("amount") or 0 for c in pat_claims)
        total_paid    = sum(c.get("paid_amount") if c.get("paid_amount") is not None else _claim_payment(c)["paid"] for c in pat_claims)
        balance       = total_billed - total_paid
        flag     = f" · ⚠ {denied_n} denied" if denied_n else ""
        new_flag = " · New" if p.get("is_new_patient") else ""
        fin      = f" · ${total_billed:,.0f} billed · ${total_paid:,.0f} paid" if total_billed > 0 else ""
        bal      = f" · bal **${balance:,.0f}**" if balance > 0 else ""
        lines.append(f"• **{p['name']}** ({payer.get('name', '—')}) · {p.get('phone', '')}{new_flag}{flag}{fin}{bal}")

    denied_total = sum(1 for p in filtered for c in all_claims if c["patient_id"] == p["id"] and c.get("status") == "denied")
    suggestions = ["Show denied claims"] if denied_total > 0 else []
    MAX_ROWS = 50
    shown = lines[:MAX_ROWS]
    truncation = f"\n\n_Showing {MAX_ROWS} of {len(filtered)} — filter by payer or name to narrow results._" if len(lines) > MAX_ROWS else ""
    return {"agent": "data_query", "reply": header + "\n".join(shown) + truncation, "suggestions": suggestions}


def handle_chat_message(text: str) -> dict:
    routed = classify_message(text)
    return dispatch_classified(routed, text)
