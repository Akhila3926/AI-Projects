from __future__ import annotations
"""
LangGraph-based multi-agent orchestrator.
Replaces the hand-rolled router in orchestrator.py with a proper StateGraph.

Graph shape:
  router → patient_access | billing | denial | bulk_billing |
           no_show_recovery | data_query | show_summary |
           show_approvals | run_workflow | unclear
        → response
"""
import json
import re
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import TypedDict, Optional, List, Any

from langgraph.graph import StateGraph, END

from app.agents import patient_access, billing_coding, denial_management
from app.data.store import store
from app.llm import ask_claude

# ── Shared in-memory state (feed, outcomes, approvals) ──────────────────────
_lock = threading.Lock()
_feed: List[dict] = []
_approvals: List[dict] = []
_outcomes = {
    "appointments_recovered": 0,
    "revenue_recovered": 0.0,
    "denials_overturned": 0,
    "hours_saved": 0.0,
}


def _log(message: str, kind: str = "done") -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "kind": kind,
    }
    with _lock:
        _feed.insert(0, entry)
        if len(_feed) > 100:
            _feed.pop()
    return entry


def _init_outcomes():
    recovered_appts  = store.list_appointments(status="recovered")
    appealed_claims  = store.list_claims(status="appealed")
    denied_claims    = store.list_claims(status="denied")
    submitted_claims = store.list_claims(status="submitted")
    with _lock:
        _outcomes["appointments_recovered"] = len(recovered_appts)
        _outcomes["revenue_recovered"] = round(
            sum((c.get("charges", 0) - c.get("balance", 0)) for c in submitted_claims), 2
        )
        _outcomes["denials_overturned"] = len(appealed_claims)
        _outcomes["hours_saved"] = round(
            (len(recovered_appts) + len(appealed_claims) + len(denied_claims)) * 0.5, 1
        )

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
        now = datetime.now(timezone.utc)
        for mins, msg, kind in reversed(entries):
            _feed.append({
                "timestamp": (now - timedelta(minutes=mins)).isoformat(),
                "message": msg,
                "kind": kind,
            })


_init_outcomes()


# ── LangGraph State ──────────────────────────────────────────────────────────
class AgentState(TypedDict):
    text: str                          # original user message
    context: str                       # optional prior context
    history: List[dict]                # conversation history [{role, content}]
    intent: str                        # classified intent
    patient_name: Optional[str]        # extracted patient name
    patient_id: Optional[str]          # resolved patient id
    reply: str                         # final reply to user
    suggestions: List[str]             # action suggestions
    result: Any                        # raw agent result
    agent: Optional[str]               # which agent handled it


# ── Router ───────────────────────────────────────────────────────────────────
CHAT_ROUTER_PROMPT = """You are a healthcare AI workforce router. Classify the user message into exactly one intent.

Intents:
- patient_access     : schedule/cancel appointment, patient-specific requests
- billing_coding     : code a specific encounter, process a visit
- denial_management  : diagnose/appeal a specific denied claim
- bulk_billing       : process ALL pending encounters at once
- no_show_recovery   : recover all no-show appointments
- run_workflow       : run full end-to-end workflow
- show_summary       : show outcomes / how are we doing
- show_approvals     : what needs approval
- data_query         : lookup / count / list / analytics on data
- unclear            : cannot determine

Respond ONLY with JSON: {"agent": "<intent>", "patient_name": "<name or null>", "reasoning": "<one sentence>"}"""

_PAYER_NAMES   = ["aetna", "bcbs", "blue cross", "uhc", "united health", "cigna", "humana", "unitedhealthcare"]
_DATA_TYPES    = ["patient", "patients", "claim", "claims", "appointment", "appointments",
                  "encounter", "encounters", "visit", "visits", "billing", "revenue",
                  "denial", "denials", "payer", "payers", "balance", "outstanding", "billed", "paid"]
_DATA_VERBS    = ["show me", "list", "get me", "find", "total", "how many", "count",
                  "what is", "what are", "tell me", "which", "who", "top", "highest",
                  "lowest", "most", "average", "all", "how much", "breakdown", "summary"]
_ANALYTICS_KW  = ["denial rate", "recovery rate", "by payer", "breakdown", "distribution",
                  "stats", "statistics", "metrics", "performance", "analysis", "report",
                  "outstanding balance", "total revenue", "revenue by", "claims by"]


def _fast_classify(text: str) -> Optional[str]:
    t = text.lower().strip()

    # Greetings and small talk → go straight to conversational LLM
    if t in ("hi", "hello", "hey", "hey there", "good morning", "good afternoon",
             "good evening", "how are you", "what can you do", "help", "what's up", "sup"):
        return "unclear"

    if any(w in t for w in ["how are we", "show outcome", "show result"]):
        return "show_summary"
    if any(w in t for w in ["approval", "pending review", "needs approval", "what needs"]):
        return "show_approvals"
    if any(w in t for w in ["no show", "no-show", "noshow", "missed appointment", "recover no"]):
        return "no_show_recovery"
    if any(w in t for w in ["process all", "all visits", "all encounter", "bill all", "code all"]):
        return "bulk_billing"
    if any(w in t for w in ["full workflow", "run workflow", "run everything", "cascade"]):
        return "run_workflow"
    if any(w in t for w in ["summary", "overview"]) and not any(w in t for w in _DATA_TYPES):
        return "show_summary"

    has_payer     = any(p in t for p in _PAYER_NAMES)
    has_type      = any(d in t for d in _DATA_TYPES)
    has_verb      = any(v in t for v in _DATA_VERBS)
    has_analytics = any(a in t for a in _ANALYTICS_KW)
    claim_status  = any(w in t for w in ["denied", "submitted", "appealed", "draft"])
    single_status = t in ("submitted", "denied", "appealed", "draft", "no show", "no-show")

    if has_analytics or has_payer or single_status:
        return "data_query"
    if (has_verb and has_type) or (claim_status and has_type):
        return "data_query"
    if has_type and any(w in t for w in ["all", "every", "each"]):
        return "data_query"
    return None


def router_node(state: AgentState) -> AgentState:
    """Classify user intent — fast path first, LLM fallback."""
    text = state["text"]
    fast = _fast_classify(text)

    if fast:
        return {**state, "intent": fast, "patient_name": None}

    # LLM fallback — minimal snapshot to avoid token burns
    denied_claims = store.list_claims(status="denied")
    patients      = store.list_patients()
    snapshot = {
        "total_patients": len(patients),
        "sample_patients": [p["name"] for p in patients[:8]],
        "denied_claims_count": len(denied_claims),
    }
    raw = ask_claude(
        CHAT_ROUTER_PROMPT,
        f"Message: \"{text}\"\nSnapshot: {json.dumps(snapshot)}",
    )
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    parsed = json.loads(match.group(0)) if match else {"agent": "unclear"}
    return {**state, "intent": parsed.get("agent", "unclear"), "patient_name": parsed.get("patient_name")}


def _find_patient_id(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    nl = name.lower()
    for p in store.list_patients():
        if nl in p["name"].lower() or p["name"].lower() in nl:
            return p["id"]
    return None


# ── Agent nodes ──────────────────────────────────────────────────────────────

def patient_access_node(state: AgentState) -> AgentState:
    result = patient_access.handle_request(state["text"])
    kind   = "needs_approval" if result["action"] == "unclear" else "done"
    _log(result.get("feed_message", "Handled patient request"), kind=kind)
    if result["action"] == "unclear":
        with _lock:
            _approvals.append({"id": f"approval_{uuid.uuid4().hex[:8]}", "type": "unclear_request",
                                "request_text": state["text"], "parsed_intent": result.get("parsed_intent")})
    elif result["action"] == "scheduled":
        with _lock:
            _outcomes["hours_saved"] += 0.1
    reply = result.get("confirmation") or result.get("rebook_offer") or result.get("feed_message", "Done.")
    return {**state, "reply": reply, "result": result, "agent": "patient_access", "suggestions": []}


def billing_node(state: AgentState) -> AgentState:
    pid = state.get("patient_id") or _find_patient_id(state.get("patient_name"))
    if pid:
        encounters = store.list_encounters()
        claimed_ids = {c["encounter_id"] for c in store.list_claims()}
        enc = next((e for e in encounters if e["patient_id"] == pid and e["id"] not in claimed_ids), None)
        if enc:
            result = billing_coding.code_and_scrub_encounter(enc["id"])
            kind = "caught_problem" if result.get("caught_and_fixed") else "done"
            _log(result.get("feed_message", "Claim processed"), kind=kind)
            with _lock:
                _outcomes["hours_saved"] += 0.3
            return {**state, "reply": result.get("feed_message", "Claim coded and submitted."),
                    "result": result, "agent": "billing_coding", "suggestions": []}
    return {**state, "reply": "I need a specific patient or encounter to code. Try 'process today's visits' to bill all pending encounters.",
            "result": {}, "agent": "billing_coding", "suggestions": ["Process today's visits"]}


def denial_node(state: AgentState) -> AgentState:
    pid    = state.get("patient_id") or _find_patient_id(state.get("patient_name"))
    denied = store.list_claims(status="denied")
    claim  = next((c for c in denied if c["patient_id"] == pid), None) if pid else (denied[0] if denied else None)
    if not claim:
        return {**state, "reply": "No denied claims found to appeal.", "result": {}, "agent": "denial_management", "suggestions": []}

    result = denial_management.diagnose_and_draft_appeal(claim["id"])

    if result.get("action") == "error":
        return {**state, "reply": result["message"], "result": result, "agent": "denial_management", "suggestions": []}

    _log(result.get("feed_message", "Appeal drafted"), kind="needs_approval")
    approval = {"id": f"approval_{claim['id']}", "type": "appeal_resubmission",
                "claim_id": claim["id"], "appeal_letter": result.get("appeal_letter"),
                "diagnosis": result.get("diagnosis")}
    with _lock:
        _approvals.append(approval)

    attempt     = result.get("appeal_attempt", 1)
    max_att     = result.get("max_attempts", 2)
    patient     = result.get("patient", claim["patient_id"])
    amount      = result.get("amount", claim.get("amount", 0))
    denial      = result.get("denial_reason", "Unknown")
    payer       = result.get("payer", claim.get("payer_id", "Unknown"))
    argument    = result.get("appeal_argument", "")
    diagnosis   = result.get("diagnosis", "")
    letter      = result.get("appeal_letter", "")

    reply = (
        f"**Appeal #{attempt}/{max_att} drafted** for **{patient}** (${amount:,.0f} · {payer})\n\n"
        f"**Denial reason:** {denial}\n\n"
        f"**Why it was denied:** {diagnosis}\n\n"
        f"**Appeal strategy:** {argument}\n\n"
        f"---\n\n"
        f"**Appeal Letter:**\n\n{letter}\n\n"
        f"---\n\n"
        f"This appeal is now in the approvals queue — use 'show approvals' to review and submit."
    )
    return {**state, "reply": reply, "result": result, "agent": "denial_management", "suggestions": ["Show approvals"]}


def bulk_billing_node(state: AgentState) -> AgentState:
    encounters  = store.list_encounters()
    claimed_ids = {c["encounter_id"] for c in store.list_claims()}
    pending     = [e for e in encounters if e["id"] not in claimed_ids]
    results     = []
    for enc in pending:
        r = billing_coding.code_and_scrub_encounter(enc["id"])
        kind = "caught_problem" if r.get("caught_and_fixed") else "done"
        _log(r.get("feed_message", "Claim processed"), kind=kind)
        with _lock:
            _outcomes["hours_saved"] += 0.3
        results.append(r)
    n = len(results)
    reply = (f"Processed {n} encounter{'s' if n != 1 else ''}. ICD-10 and CPT codes assigned, claims scrubbed and submitted."
             if n else "No pending encounters — all visits are already coded and submitted.")
    return {**state, "reply": reply, "result": {"processed": n, "results": results},
            "agent": "billing_coding", "suggestions": []}


def no_show_recovery_node(state: AgentState) -> AgentState:
    recovered = patient_access.recover_no_shows()
    for r in recovered:
        _log(r["feed_message"])
    with _lock:
        _outcomes["appointments_recovered"] += len(recovered)
        _outcomes["hours_saved"] += 0.25 * len(recovered)
    n = len(recovered)
    reply = (f"Recovered {n} no-show appointment{'s' if n != 1 else ''}. Patients contacted and rebooked."
             if n else "No no-show appointments found to recover right now.")
    return {**state, "reply": reply, "result": {"recovered": recovered},
            "agent": "patient_access", "suggestions": []}


def run_workflow_node(state: AgentState) -> AgentState:
    patients = store.list_patients()
    if not patients:
        return {**state, "reply": "No patients found.", "result": {}, "agent": "run_workflow", "suggestions": []}
    p    = patients[0]
    date = datetime.now(timezone.utc).isoformat()

    # Step 1 — schedule
    appt_result = patient_access.schedule_appointment(p["id"], "Dr. Alvarez", date)
    _log(appt_result.get("feed_message", "Appointment booked"))

    # Step 2 — bill pending encounters
    encounters  = store.list_encounters()
    claimed_ids = {c["encounter_id"] for c in store.list_claims()}
    pending     = [e for e in encounters if e["patient_id"] == p["id"] and e["id"] not in claimed_ids]
    bill_result = {}
    if pending:
        bill_result = billing_coding.code_and_scrub_encounter(pending[0]["id"])
        _log(bill_result.get("feed_message", "Claim coded"))

    # Step 3 — check denials
    denied = store.list_claims(status="denied")
    pat_denied = [c for c in denied if c["patient_id"] == p["id"]]
    denial_result = {}
    if pat_denied:
        denial_result = denial_management.diagnose_and_draft_appeal(pat_denied[0]["id"])
        _log(denial_result.get("feed_message", "Appeal drafted"), kind="needs_approval")

    with _lock:
        _outcomes["hours_saved"] += 0.7

    reply = (f"Full workflow complete for **{p['name']}**. "
             f"Appointment booked with Dr. Alvarez, "
             f"{'encounter coded and claim submitted, ' if bill_result else ''}"
             f"{'denial appeal drafted' if denial_result else 'no denied claims found'}.")
    return {**state, "reply": reply,
            "result": {"appointment": appt_result, "billing": bill_result, "denial": denial_result},
            "agent": "run_workflow", "suggestions": []}


def show_summary_node(state: AgentState) -> AgentState:
    o = dict(_outcomes)
    recent = "; ".join(f["message"] for f in _feed[:3]) if _feed else "No recent activity"
    reply  = (
        f"Here's today's operational summary:\n\n"
        f"• **{o['appointments_recovered']} appointments recovered** from no-shows\n"
        f"• **${o['revenue_recovered']:,.0f} revenue recovered** through appeal resubmissions\n"
        f"• **{o['denials_overturned']} denials overturned** after appeal\n"
        f"• **{o['hours_saved']:.1f} staff hours saved** by autonomous agents\n\n"
        f"Recent activity: {recent}\n\nAll three agents are operational."
    )
    return {**state, "reply": reply, "result": o, "agent": "show_summary",
            "suggestions": ["Show denied claims", "Recover no-show appointments"]}


def show_approvals_node(state: AgentState) -> AgentState:
    current = list(_approvals)
    if not current:
        reply = "No items currently need approval. Everything is running smoothly."
    else:
        lines = []
        for a in current[:5]:
            if a["type"] == "appeal_resubmission":
                lines.append(f"• Appeal resubmission for claim **{a['claim_id']}** — ready to send")
            else:
                snippet = (a.get("request_text") or "")[:60]
                lines.append(f"• Unclear request: \"{snippet}\" — needs staff review")
        reply = f"**{len(current)} item{'s' if len(current) != 1 else ''} awaiting approval:**\n\n" + "\n".join(lines)
    return {**state, "reply": reply, "result": current, "agent": "show_approvals", "suggestions": []}


def data_query_node(state: AgentState) -> AgentState:
    from app.orchestrator.orchestrator import handle_data_query
    result = handle_data_query(state["text"], state.get("context", ""))
    return {**state, "reply": result.get("reply", ""), "result": result,
            "agent": "data_query", "suggestions": result.get("suggestions", [])}


_GENERAL_CHAT_PROMPT = """You are Care Intelligence, a helpful AI assistant for a healthcare revenue cycle management (RCM) platform.
You help clinic staff with questions about billing, claims, denials, appointments, patients, and general healthcare topics.
You can also have normal conversation — greet users, answer general questions, explain concepts.
Be warm, concise, and helpful. If you don't know something specific to this clinic's data, say so and offer what you do know."""


def unclear_node(state: AgentState) -> AgentState:
    text    = state["text"]
    history = state.get("history") or []

    # Keep prompt small — Groq free tier has 12k TPM limit
    history_lines = ""
    if history:
        last = history[-2:]
        history_lines = "\n".join(f"{h['role'].title()}: {h['content'][:80]}" for h in last)

    o = dict(_outcomes)
    context_snippet = (
        f"Clinic: {o.get('appointments_recovered',0)} appts recovered, "
        f"{o.get('denials_overturned',0)} denials overturned, "
        f"${o.get('revenue_recovered',0):,.0f} revenue recovered."
    )

    prompt = (
        (f"Recent:\n{history_lines}\n" if history_lines else "")
        + f"{context_snippet}\nUser: {text[:300]}"
    )

    try:
        reply = ask_claude(_GENERAL_CHAT_PROMPT, prompt)
    except Exception:
        reply = "I'm here to help! You can ask me about claims, denials, appointments, patients, or anything about this clinic's revenue cycle."

    return {**state, "reply": reply, "result": {}, "agent": "unclear", "suggestions": []}


# ── Build the graph ──────────────────────────────────────────────────────────

def _route(state: AgentState) -> str:
    return state.get("intent", "unclear")


def build_graph() -> Any:
    g = StateGraph(AgentState)

    g.add_node("router",            router_node)
    g.add_node("patient_access",    patient_access_node)
    g.add_node("billing_coding",    billing_node)
    g.add_node("denial_management", denial_node)
    g.add_node("bulk_billing",      bulk_billing_node)
    g.add_node("no_show_recovery",  no_show_recovery_node)
    g.add_node("run_workflow",      run_workflow_node)
    g.add_node("show_summary",      show_summary_node)
    g.add_node("show_approvals",    show_approvals_node)
    g.add_node("data_query",        data_query_node)
    g.add_node("unclear",           unclear_node)

    g.set_entry_point("router")

    g.add_conditional_edges("router", _route, {
        "patient_access":    "patient_access",
        "billing_coding":    "billing_coding",
        "denial_management": "denial_management",
        "bulk_billing":      "bulk_billing",
        "no_show_recovery":  "no_show_recovery",
        "run_workflow":      "run_workflow",
        "show_summary":      "show_summary",
        "show_approvals":    "show_approvals",
        "data_query":        "data_query",
        "unclear":           "unclear",
    })

    for node in ["patient_access", "billing_coding", "denial_management",
                 "bulk_billing", "no_show_recovery", "run_workflow",
                 "show_summary", "show_approvals", "data_query", "unclear"]:
        g.add_edge(node, END)

    return g.compile()


# Singleton compiled graph
_graph = build_graph()


# ── Public API (called by main.py) ───────────────────────────────────────────

_CONVERSATIONAL_PROMPT = """You are Care Intelligence, a warm and helpful AI assistant for a healthcare revenue cycle management platform.
You have just retrieved data or completed an action. Your job is to present the result in a natural, conversational way.

Rules:
- Speak like a knowledgeable colleague, not a database
- Start with a direct answer, then add context or insight
- Use "I found", "I see", "Looks like", "Here's what I found" naturally
- If there's something actionable (e.g. denied claims), proactively suggest what to do next
- Keep it concise — don't repeat everything from the data, highlight what matters
- Reference prior conversation context if relevant
- Never say "As an AI" or be robotic
"""


def _add_intro(text: str, raw_reply: str, history: List[dict]) -> str:
    """Add a short 1-sentence conversational intro before the data."""
    history_snippet = ""
    if history:
        last = history[-2:] if len(history) >= 2 else history
        history_snippet = "\n".join(f"{h['role'].title()}: {h['content'][:100]}" for h in last)

    prompt = (
        f"User asked: \"{text}\"\n"
        + (f"Recent conversation:\n{history_snippet}\n\n" if history_snippet else "")
        + f"Data:\n{raw_reply[:400]}\n\n"
        + "Write ONE short, warm sentence (max 15 words) introducing this data. "
        + "No lists, no details — just a friendly lead-in. Example: 'Here's what I found:' or "
        + "'Sure, here are the denied claims:' or 'We have 191 denied claims totalling $523k —'"
    )
    try:
        intro = ask_claude(_CONVERSATIONAL_PROMPT, prompt).strip()
        # Ensure intro ends cleanly before the data
        if not intro.endswith((":", "—", "-")):
            intro = intro.rstrip(".") + ":"
        return f"{intro}\n\n{raw_reply}"
    except Exception:
        return raw_reply


def run_graph(text: str, context: str = "", history: List[dict] = None) -> dict:
    """Run the LangGraph and return {reply, agent, suggestions}."""
    history = history or []
    initial: AgentState = {
        "text": text, "context": context, "history": history,
        "intent": "", "patient_name": None, "patient_id": None,
        "reply": "", "suggestions": [], "result": None, "agent": None,
    }
    final   = _graph.invoke(initial)
    reply   = final["reply"]
    agent   = final["agent"] or "unclear"

    # Add conversational intro before data lists
    if agent == "data_query" and len(reply) > 100:
        reply = _add_intro(text, reply, history)

    return {"reply": reply, "agent": agent, "suggestions": final.get("suggestions", [])}


def get_feed()     -> list: return list(_feed)
def get_outcomes() -> dict: return dict(_outcomes)
def get_approvals()-> list: return list(_approvals)


def dismiss_approval(approval_id: str) -> dict:
    with _lock:
        before = len(_approvals)
        _approvals[:] = [a for a in _approvals if a["id"] != approval_id]
    if len(_approvals) < before:
        _log(f"Dismissed approval {approval_id}")
        return {"action": "dismissed", "approval_id": approval_id}
    return {"action": "error", "message": f"Approval {approval_id} not found"}


def approve_denial_resubmission(claim_id: str) -> dict:
    result = denial_management.resubmit_appeal(claim_id)
    if result["action"] == "error":
        return result
    _log(result["feed_message"])
    claim = store.get_claim(claim_id)
    with _lock:
        _approvals[:] = [a for a in _approvals if a.get("claim_id") != claim_id]
        _outcomes["denials_overturned"] += 1
        _outcomes["revenue_recovered"]  += claim["amount"] if claim else 0
        _outcomes["hours_saved"]        += 0.5
    return result


def run_no_show_recovery() -> dict:
    recovered = patient_access.recover_no_shows()
    for r in recovered:
        _log(r["feed_message"])
    with _lock:
        _outcomes["appointments_recovered"] += len(recovered)
        _outcomes["hours_saved"]            += 0.25 * len(recovered)
    return {"recovered": recovered}


def run_patient_access_schedule(patient_id: str, provider: str, date_iso: str) -> dict:
    result = patient_access.schedule_appointment(patient_id, provider, date_iso)
    _log(result.get("feed_message", "Appointment booked"))
    return result


def run_patient_access_cancel(appointment_id: str) -> dict:
    result = patient_access.cancel_appointment(appointment_id)
    _log(result.get("feed_message", "Appointment cancelled"))
    return result


def run_patient_access_request(text: str) -> dict:
    result = patient_access.handle_request(text)
    _log(result.get("feed_message", "Handled patient request"),
         kind="needs_approval" if result["action"] == "unclear" else "done")
    return result


def run_billing_coding(encounter_id: str) -> dict:
    result = billing_coding.code_and_scrub_encounter(encounter_id)
    if result["action"] == "error":
        _log(result["message"], kind="needs_approval")
        return result
    _log(result["feed_message"], kind="caught_problem" if result.get("caught_and_fixed") else "done")
    with _lock:
        _outcomes["hours_saved"] += 0.3
    return result


def run_denial_diagnosis(claim_id: str) -> dict:
    result = denial_management.diagnose_and_draft_appeal(claim_id)
    if result["action"] == "error":
        _log(result["message"], kind="needs_approval")
        return result
    _log(result["feed_message"], kind="needs_approval")
    with _lock:
        _approvals.append({"id": f"approval_{claim_id}", "type": "appeal_resubmission",
                           "claim_id": claim_id, "appeal_letter": result.get("appeal_letter"),
                           "diagnosis": result.get("diagnosis")})
    return result
