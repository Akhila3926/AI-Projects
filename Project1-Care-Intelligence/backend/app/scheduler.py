from __future__ import annotations
"""APScheduler: autonomous cycle running all 3 agents every interval."""
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.data.store import store
from app.data.models import get_session
from app.emailer import build_denial_report_html, send_report
from app.agents.denial_management import is_appealable, MAX_APPEAL_ATTEMPTS, _appeal_attempts

_scheduler: BackgroundScheduler | None = None


# ── 1. Patient Access ─────────────────────────────────────────────────────────

def autonomous_patient_access_job() -> dict:
    """Auto-recover no-show appointments."""
    from app.agents.patient_access import recover_no_shows
    from app.orchestrator import graph as g

    results = recover_no_shows()
    recovered = len(results)

    if recovered > 0:
        g._log(f"Patient Access: {recovered} no-show(s) recovered automatically", kind="done")
        g._outcomes["appointments"] = g._outcomes.get("appointments", 0) + recovered
    else:
        g._log("Patient Access: No no-shows found this cycle", kind="done")

    print(f"[Scheduler] Patient Access: {recovered} no-shows recovered")
    return {"recovered_no_shows": recovered}


# ── 2. Billing & Coding ───────────────────────────────────────────────────────

def autonomous_billing_job() -> dict:
    """Auto-code and submit pending encounters (max 3 per cycle)."""
    from app.agents.billing_coding import code_and_scrub_encounter
    from app.orchestrator import graph as g

    encounters = store.list_encounters()
    claims = store.list_claims()
    submitted_enc_ids = {
        c.get("encounter_id")
        for c in claims
        if c.get("status") not in ("pending", None, "")
    }
    pending = [e for e in encounters if e.get("id") not in submitted_enc_ids][:3]

    processed = 0
    revenue = 0.0

    for enc in pending:
        try:
            result = code_and_scrub_encounter(enc["id"])
            claim = result.get("claim") or {}
            amt = float(claim.get("amount") or 0)
            revenue += amt
            processed += 1
            name = claim.get("patient_name") or enc.get("id")
            g._log(f"Billing: Auto-coded & submitted claim for {name} (${amt:,.0f})", kind="done")
        except Exception as e:
            print(f"[Scheduler] Billing error on {enc.get('id')}: {e}")

    if processed > 0:
        g._outcomes["revenue"] = g._outcomes.get("revenue", 0) + revenue
        g._outcomes["claims"] = g._outcomes.get("claims", 0) + processed
    elif not pending:
        g._log("Billing: No pending encounters this cycle", kind="done")

    print(f"[Scheduler] Billing: {processed} encounters processed, ${revenue:,.0f} submitted")
    return {"processed": processed, "revenue": revenue}


# ── 3. Denial Management ──────────────────────────────────────────────────────

def autonomous_denial_job() -> dict:
    """Auto-appeal denied claims and send email report."""
    from app.orchestrator import graph as g

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    denied_claims = store.list_claims(status="denied")
    scanned = len(denied_claims)

    recovered_claims = []
    pending_claims   = []
    revenue_recovered = 0.0

    session = get_session()
    try:
        for claim in denied_claims:
            cid    = claim.get("id", "")
            amount = float(claim.get("amount") or 0)
            denial = claim.get("denial_reason") or "Unknown"
            pid    = claim.get("patient_id", "")
            payer  = claim.get("payer_id", "Unknown")

            patient = store.get_patient(pid) or {}
            pname   = patient.get("name", pid)

            attempts   = _appeal_attempts.get(cid, 0)
            appealable = is_appealable(denial) and attempts < MAX_APPEAL_ATTEMPTS

            if appealable:
                from app.data.models import Record
                rec = session.query(Record).filter(Record.Claim_ID == cid).first()
                if rec:
                    rec.Claim_Status = "Appealed"
                _appeal_attempts[cid] = attempts + 1
                revenue_recovered += amount
                recovered_claims.append({
                    "id": cid, "patient": pname, "payer": payer,
                    "amount": amount, "denial_reason": denial,
                })
                g._log(f"Denial: Auto-appealed {pname} (${amount:,.0f}) - {denial}", kind="done")

                # Handoff to Billing if denied due to a coding error
                if any(r in denial.lower() for r in ("invalid code", "wrong code", "incorrect code")):
                    enc_id = claim.get("encounter_id", "")
                    if enc_id:
                        try:
                            from app.agents.billing_coding import code_and_scrub_encounter
                            result = code_and_scrub_encounter(enc_id)
                            g._log(f"Billing (via Denial): Re-coded {pname}'s claim after code error", kind="done")
                            print(f"[Scheduler] Handoff: Billing re-coded {enc_id} for {pname}")
                        except Exception as he:
                            print(f"[Scheduler] Handoff error for {enc_id}: {he}")
            else:
                pending_claims.append({
                    "id": cid, "patient": pname, "payer": payer,
                    "amount": amount, "denial_reason": denial,
                })

        session.commit()
    except Exception as exc:
        session.rollback()
        print(f"[Scheduler] Denial DB error: {exc}")
    finally:
        session.close()

    recovered    = len(recovered_claims)
    still_denied = len(pending_claims)

    try:
        g._outcomes["denials"] = max(0, g._outcomes.get("denials", 0) - recovered)
        g._outcomes["revenue"] = g._outcomes.get("revenue", 0) + revenue_recovered
    except Exception:
        pass

    top3 = sorted(recovered_claims + pending_claims, key=lambda c: c["amount"], reverse=True)[:3]

    report = {
        "scanned": scanned, "recovered": recovered,
        "still_denied": still_denied, "revenue_recovered": revenue_recovered,
        "recovered_claims": recovered_claims, "pending_claims": pending_claims,
        "top3_claims": top3, "run_at": now_str,
    }

    if scanned > 0:
        subject   = f"[Care Intelligence] Denial Alerts - {now_str}"
        send_report(subject, build_denial_report_html(report))

    print(f"[Scheduler] Denial: scanned={scanned}, recovered={recovered}, still_denied={still_denied}")
    return report


# ── 0. Prior Authorization ────────────────────────────────────────────────────

def autonomous_prior_auth_job() -> dict:
    """Auto-check booked appointments for prior auth requirements."""
    from app.agents.prior_auth import run_autonomous_prior_auth
    from app.orchestrator import graph as g

    result = run_autonomous_prior_auth()
    submitted = result["submitted"]
    approved  = result["approved"]
    denied    = result["denied"]

    if submitted > 0:
        g._log(
            f"Prior Auth: {submitted} request(s) submitted — {approved} approved, {denied} denied",
            kind="done" if denied == 0 else "caught_problem",
        )
        if denied > 0:
            g._log(
                f"Prior Auth: {denied} auth(s) denied — Denial agent will follow up",
                kind="caught_problem",
            )
    else:
        g._log("Prior Auth: No new auth requests this cycle", kind="done")

    print(f"[Scheduler] Prior Auth: submitted={submitted}, approved={approved}, denied={denied}")
    return result


# ── Master cycle ──────────────────────────────────────────────────────────────

def autonomous_cycle() -> dict:
    """Run all 4 agents in sequence: Prior Auth → Patient Access → Billing → Denial."""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[Scheduler] == Autonomous cycle @ {now} ==")

    from app.orchestrator import graph as g
    g._log(f"Autonomous cycle started @ {now}", kind="done")

    results = {}

    try:
        results["prior_auth"] = autonomous_prior_auth_job()
    except Exception as e:
        print(f"[Scheduler] Prior Auth error: {e}")
        results["prior_auth"] = {"error": str(e)}

    try:
        results["patient_access"] = autonomous_patient_access_job()
    except Exception as e:
        print(f"[Scheduler] Patient Access error: {e}")
        results["patient_access"] = {"error": str(e)}

    try:
        results["billing"] = autonomous_billing_job()
    except Exception as e:
        print(f"[Scheduler] Billing error: {e}")
        results["billing"] = {"error": str(e)}

    try:
        results["denial"] = autonomous_denial_job()
    except Exception as e:
        print(f"[Scheduler] Denial error: {e}")
        results["denial"] = {"error": str(e)}

    g._log("Autonomous cycle complete", kind="done")
    print(f"[Scheduler] == Cycle complete ==\n")
    return results


# ── Scheduler lifecycle ───────────────────────────────────────────────────────

def start_scheduler() -> None:
    global _scheduler
    interval = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        autonomous_cycle,
        trigger="interval",
        minutes=interval,
        id="autonomous_cycle",
        replace_existing=True,
        next_run_time=None,
    )
    _scheduler.start()
    print(f"[Scheduler] Started - all 3 agents cycle every {interval} minute(s).")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped.")


def trigger_now() -> dict:
    return autonomous_cycle()
