from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.orchestrator import orchestrator as orch
from app.orchestrator import graph as g
from app.data.store import store
from app.scheduler import start_scheduler, stop_scheduler, trigger_now


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Care Intelligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Dashboard data ----

@app.get("/api/feed")
def get_feed():
    return g.get_feed()


@app.get("/api/outcomes")
def get_outcomes():
    return g.get_outcomes()


@app.get("/api/approvals")
def get_approvals():
    return g.get_approvals()


@app.post("/api/approvals/{approval_id}/dismiss")
def dismiss_approval(approval_id: str):
    result = g.dismiss_approval(approval_id)
    if result["action"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.get("/api/data-summary")
def get_data_summary():
    return {
        "patients": store.list_patients(),
        "appointments": store.list_appointments(),
        "encounters": store.list_encounters(),
        "claims": store.list_claims(),
        "payers": store.list_payers(),
    }


# ---- Patient Access ----

class ScheduleRequest(BaseModel):
    patient_id: str
    provider: str
    date_iso: str


@app.post("/api/agents/patient-access/schedule")
def schedule(req: ScheduleRequest):
    return g.run_patient_access_schedule(req.patient_id, req.provider, req.date_iso)


@app.post("/api/agents/patient-access/cancel/{appointment_id}")
def cancel(appointment_id: str):
    return g.run_patient_access_cancel(appointment_id)


@app.post("/api/agents/patient-access/recover-no-shows")
def recover_no_shows():
    return g.run_no_show_recovery()


class RequestText(BaseModel):
    request_text: str
    context: Optional[str] = None
    history: Optional[list] = None


@app.post("/api/agents/patient-access/request")
def patient_request(req: RequestText):
    return g.run_patient_access_request(req.request_text)


# ---- Billing & Coding ----

@app.post("/api/agents/billing-coding/{encounter_id}")
def billing_coding_route(encounter_id: str):
    result = g.run_billing_coding(encounter_id)
    if result["action"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ---- Denial Management ----

@app.post("/api/agents/denial-management/diagnose/{claim_id}")
def diagnose(claim_id: str):
    result = g.run_denial_diagnosis(claim_id)
    if result["action"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/agents/denial-management/approve/{claim_id}")
def approve(claim_id: str):
    result = g.approve_denial_resubmission(claim_id)
    if result["action"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ---- Cascade ----

class CascadeRequest(BaseModel):
    patient_id: str
    provider: str
    date_iso: str


@app.post("/api/cascade/run")
def run_cascade(req: CascadeRequest):
    return g.run_graph(f"run full workflow for patient {req.patient_id}")


# ---- Unified chat (sync) ----

@app.post("/api/chat")
def chat(req: RequestText):
    return g.run_graph(req.request_text, req.context or "")


# ---- Streaming chat with SSE ----

_AGENT_DISPLAY = {
    "patient_access":    "patient_access",
    "billing_coding":    "billing_coding",
    "denial_management": "denial_management",
    "bulk_billing":      "billing_coding",
    "no_show_recovery":  "patient_access",
    "run_workflow":      None,
    "show_summary":      None,
    "show_approvals":    None,
    "data_query":        None,
    "unclear":           None,
}

_AGENT_LABELS = {
    "patient_access":    "Patient Access Agent",
    "billing_coding":    "Billing & Coding Agent",
    "denial_management": "Denial Management Agent",
    "bulk_billing":      "Billing & Coding Agent",
    "no_show_recovery":  "Patient Access Agent",
    "run_workflow":      "Full Workflow",
    "data_query":        "Data Query",
}


def _sse(event_type: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"


_PAYER_NAMES = ["aetna", "bcbs", "blue cross", "uhc", "united health", "cigna", "humana", "unitedhealthcare"]
_DATA_TYPES  = ["patient", "patients", "claim", "claims", "appointment", "appointments",
                "encounter", "encounters", "visit", "visits", "billing", "revenue", "denial",
                "denials", "payer", "payers", "balance", "outstanding", "billed", "paid"]
_DATA_VERBS  = ["pull up", "pull me", "show me", "list", "get me", "find me", "what are",
                "fetch", "retrieve", "look up", "give me", "total", "how many", "count",
                "what is", "whats", "what's", "tell me", "display", "summarize", "breakdown",
                "which", "who has", "who have", "top", "highest", "lowest", "most", "least",
                "average", "avg", "all", "any", "do we have", "are there", "how much"]
_ANALYTICS_KW = ["denial rate", "recovery rate", "top payer", "worst payer", "best payer",
                 "by payer", "per payer", "breakdown", "distribution", "overview", "stats",
                 "statistics", "metrics", "performance", "analysis", "trend", "report",
                 "top patient", "highest balance", "most denied", "revenue by", "claims by",
                 "outstanding balance", "total revenue", "total billed", "total paid",
                 "how much revenue", "how much billed", "which payer", "payer performance"]


def _fast_classify(text: str) -> str | None:
    """Keyword shortcut — skips LLM for obvious intents."""
    t = text.lower().strip()

    if any(w in t for w in ["summary", "how are we", "how did we", "show outcome", "show result", "overview"]):
        return "show_summary"
    if any(w in t for w in ["approval", "pending review", "needs approval", "what needs"]):
        return "show_approvals"
    if any(w in t for w in ["no show", "no-show", "noshow", "missed appointment", "recover no"]):
        return "no_show_recovery"
    if any(w in t for w in ["process all", "all visits", "all encounter",
                             "completed visit", "process today", "bill all", "code all"]):
        return "bulk_billing"
    if any(w in t for w in ["full workflow", "run workflow", "run everything", "cascade",
                             "run today", "process everything"]):
        return "run_workflow"

    has_payer     = any(p in t for p in _PAYER_NAMES)
    has_type      = any(d in t for d in _DATA_TYPES)
    has_verb      = any(v in t for v in _DATA_VERBS)
    has_analytics = any(a in t for a in _ANALYTICS_KW)
    claim_status  = any(w in t for w in ["denied", "submitted", "appealed", "draft", "pending"])
    single_status = t in ("submitted", "denied", "appealed", "draft", "appeal pending", "no show", "no-show")

    if has_analytics:
        return "data_query"
    if has_payer:
        return "data_query"
    if (has_verb and has_type) or (claim_status and has_type) or single_status:
        return "data_query"
    if has_type and any(w in t for w in ["all", "every", "each"]):
        return "data_query"

    return None


@app.post("/api/chat/stream")
async def chat_stream(req: RequestText):
    async def generate():
        loop = asyncio.get_event_loop()


        # Run LangGraph
        try:
            result = await loop.run_in_executor(
                None, g.run_graph, req.request_text, req.context or "", req.history or []
            )
        except Exception as exc:
            yield _sse("result", reply=f"Processing error: {exc}", agent="unclear")
            yield _sse("done")
            return

        agent         = result.get("agent", "unclear")
        display_agent = _AGENT_DISPLAY.get(agent, agent)

        yield _sse("result", reply=result.get("reply", ""), agent=display_agent or "unclear")

        suggestions = result.get("suggestions", [])
        if suggestions:
            yield _sse("actions", suggestions=suggestions)

        yield _sse("done")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---- Autonomous agent run (all three agents, sequential) ----

@app.post("/api/agents/autonomous/stream")
async def autonomous_stream():
    async def generate():
        loop = asyncio.get_event_loop()

        # ── Patient Access ──────────────────────────────────────────────────
        yield _sse("agent_start", agent="patient_access",
                   message="Scanning appointment schedule for no-shows and missed visits…")

        no_show_appts = [a for a in store.list_appointments() if a.get("status") == "no_show"]
        if no_show_appts:
            yield _sse("step_info", agent="patient_access",
                       message=f"Detected {len(no_show_appts)} no-show appointment{'s' if len(no_show_appts) != 1 else ''} — initiating outreach")
        else:
            yield _sse("step_info", agent="patient_access",
                       message="Reviewing appointment history and patient contact records…")

        ns_result = await loop.run_in_executor(None, g.run_no_show_recovery)
        n_recovered = len(ns_result.get("recovered", []))
        if n_recovered:
            yield _sse("agent_result", agent="patient_access", count=n_recovered,
                       message=f"Recovered {n_recovered} no-show appointment{'s' if n_recovered != 1 else ''} — patients contacted and rebooked")
        else:
            yield _sse("agent_result", agent="patient_access", count=0,
                       message="Appointment schedule is clear — no no-shows to recover")

        # ── Billing & Coding ────────────────────────────────────────────────
        yield _sse("agent_start", agent="billing_coding",
                   message="Scanning encounter records for visits awaiting coding…")

        encounters = store.list_encounters()
        existing_enc_ids = {c["encounter_id"] for c in store.list_claims()}
        pending = [e for e in encounters if e["id"] not in existing_enc_ids]

        if pending:
            yield _sse("step_info", agent="billing_coding",
                       message=f"Found {len(pending)} encounter{'s' if len(pending) != 1 else ''} awaiting coding — queuing for submission")
            # Fast path: log pending encounters without LLM per-claim coding
            n_pending = len(pending)
            g._log(f"Autonomous scan: {n_pending} encounter{'s' if n_pending != 1 else ''} queued for coding")
            yield _sse("agent_result", agent="billing_coding", count=n_pending,
                       message=f"Found {n_pending} encounter{'s' if n_pending != 1 else ''} awaiting coding — use 'Process today's visits' to code and submit them")
        else:
            yield _sse("agent_result", agent="billing_coding", count=0,
                       message="All encounters are coded — no pending claims to process")

        # ── Denial Management ───────────────────────────────────────────────
        yield _sse("agent_start", agent="denial_management",
                   message="Reviewing all submitted claims for denials requiring appeal…")

        denied_claims = store.list_claims(status="denied")
        if denied_claims:
            yield _sse("step_info", agent="denial_management",
                       message=f"Found {len(denied_claims)} denied claim{'s' if len(denied_claims) != 1 else ''} — flagging for appeal review")
            # Fast path: report denials without LLM appeal drafting (avoids N sequential LLM calls)
            denial_summary = ", ".join(
                f"{(store.get_patient(c['patient_id']) or {}).get('name', c['patient_id'])} ${c.get('amount', 0):,.0f}"
                for c in denied_claims[:3]
            )
            g._log(f"Autonomous scan: {len(denied_claims)} denied claim{'s' if len(denied_claims) != 1 else ''} flagged — {denial_summary}", kind="needs_approval")
            yield _sse("agent_result", agent="denial_management", count=len(denied_claims),
                       message=f"Flagged {len(denied_claims)} denied claim{'s' if len(denied_claims) != 1 else ''} ({denial_summary}) — use 'Draft appeals for all denied claims' to generate appeal letters")
        else:
            yield _sse("agent_result", agent="denial_management", count=0,
                       message="No denied claims — all claims are in good standing")

        # ── Final summary ───────────────────────────────────────────────────
        outcomes = g.get_outcomes()
        yield _sse("auto_summary", outcomes=outcomes)
        yield _sse("done")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---- Autonomous denial management ----

@app.post("/api/agents/denial-management/run-autonomous")
async def run_autonomous_denial():
    """Manually trigger the autonomous denial recovery job."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, trigger_now)
    return result


@app.get("/api/scheduler/status")
def scheduler_status():
    from app.scheduler import _scheduler
    if _scheduler is None:
        return {"running": False}
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": _scheduler.running, "jobs": jobs}


@app.post("/api/dev/reset-denied-claims")
def reset_denied_claims():
    """Reset some appealed claims back to denied so the denial agent can be tested again."""
    from app.data.models import get_session, Record
    with get_session() as s:
        rows = s.query(Record).filter(Record.Claim_Status == "Appealed").limit(10).all()
        for r in rows:
            r.Claim_Status = "Denied"
            if not r.Denial_Reason:
                r.Denial_Reason = "medical necessity"
        s.commit()
        return {"reset": len(rows), "message": f"Reset {len(rows)} claims back to Denied"}


@app.get("/api/agents/prior-auth/requests")
def prior_auth_requests():
    from app.agents.prior_auth import list_auth_requests
    return list_auth_requests()


@app.post("/api/agents/prior-auth/run")
async def run_prior_auth():
    loop = asyncio.get_event_loop()
    from app.scheduler import autonomous_prior_auth_job
    result = await loop.run_in_executor(None, autonomous_prior_auth_job)
    return result
