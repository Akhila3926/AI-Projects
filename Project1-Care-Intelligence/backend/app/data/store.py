from __future__ import annotations
"""
Data-layer interface backed by SQLite (care_intelligence.db).
The DB has a single flat 'patients' table — one row per patient/appointment/claim.
All read methods return dicts shaped the same way the agents already expect.
"""
from typing import Optional
from app.data.models import get_session, create_tables, Record


def _to_patient(r: Record) -> dict:
    return {
        "id":             r.Patient_ID,
        "name":           r.Full_Name,
        "dob":            r.DOB,
        "age":            r.Age,
        "gender":         r.Gender,
        "phone":          r.Phone_Number,
        "email":          r.Email,
        "city":           r.City,
        "state":          r.State,
        "insurance_id":   r.Policy_Number,
        "payer_id":       r.Insurance_Payer,
        "is_new_patient": (r.Appointment_Type or "").strip().lower() == "new patient",
    }


def _to_appointment(r: Record) -> dict:
    return {
        "id":         r.Patient_ID,   # 1:1 with patient row
        "patient_id": r.Patient_ID,
        "provider":   r.Provider,
        "date":       r.Appointment_Date,
        "status":     _appt_status(r.Appointment_Status),
        "type":       r.Appointment_Type,
        "department": r.Department,
    }


def _to_encounter(r: Record) -> dict:
    return {
        "id":             r.Encounter_ID,
        "patient_id":     r.Patient_ID,
        "appointment_id": r.Patient_ID,
        "provider":       r.Provider,
        "date":           r.Appointment_Date,
        "notes":          r.Clinical_Notes,
        "diagnoses":      [r.Diagnosis] if r.Diagnosis else [],
        "procedures":     [r.Procedure] if r.Procedure else [],
        "allergies":      r.Allergies,
    }


def _to_claim(r: Record) -> dict:
    return {
        "id":            r.Claim_ID,
        "patient_id":    r.Patient_ID,
        "encounter_id":  r.Encounter_ID,
        "payer_id":      r.Insurance_Payer,
        "status":        _claim_status(r.Claim_Status),
        "amount":        float(r.Claim_Amount_USD or 0),
        "charges":       float(r.Charges_USD or 0),
        "balance":       float(r.Balance_USD or 0),
        "denial_reason": r.Denial_Reason,
        "last_updated":  r.Last_Updated,
        "codes":         [],
    }


def _to_payer(name: str) -> dict:
    return {"id": name, "name": name, "rules": {}}


def _appt_status(raw: str) -> str:
    mapping = {
        "Completed":  "completed",
        "Booked":     "booked",
        "Cancelled":  "cancelled",
        "No-Show":    "no_show",
        "No-show":    "no_show",
        "No Show":    "no_show",
        "Recovered":  "recovered",
    }
    return mapping.get(raw, (raw or "").lower())


def _claim_status(raw: str) -> str:
    mapping = {
        "Draft":          "draft",
        "Submitted":      "submitted",
        "Denied":         "denied",
        "Appealed":       "appealed",
        "Appeal Pending": "appeal_pending",
        "Approved":       "approved",
        "Paid":           "paid",
    }
    return mapping.get(raw, (raw or "").lower())


class Store:

    # ---- patients ----
    def get_patient(self, patient_id: str) -> Optional[dict]:
        with get_session() as s:
            r = s.get(Record, patient_id)
            return _to_patient(r) if r else None

    def list_patients(self) -> list[dict]:
        with get_session() as s:
            return [_to_patient(r) for r in s.query(Record).all()]

    # ---- appointments ----
    def list_appointments(self, status: Optional[str] = None) -> list[dict]:
        with get_session() as s:
            q = s.query(Record)
            if status:
                to_raw = {
                    "completed": "Completed", "booked": "Booked",
                    "cancelled": "Cancelled", "no_show": "No-show",
                    "recovered": "Recovered", "no_show_recovered": "Recovered",
                }
                raw_status = to_raw.get(status, status)
                q = q.filter(Record.Appointment_Status == raw_status)
            return [_to_appointment(r) for r in q.all()]

    def get_appointment(self, appointment_id: str) -> Optional[dict]:
        with get_session() as s:
            r = s.get(Record, appointment_id)
            return _to_appointment(r) if r else None

    def update_appointment(self, appointment_id: str, **fields) -> dict:
        with get_session() as s:
            r = s.get(Record, appointment_id)
            if "status" in fields:
                reverse = {
                    "completed": "Completed", "booked": "Booked",
                    "cancelled": "Cancelled", "no_show": "No-show",
                    "recovered": "Recovered", "no_show_recovered": "Recovered",
                }
                r.Appointment_Status = reverse.get(fields["status"], fields["status"])
            s.commit()
            return _to_appointment(r)

    def create_appointment(self, appointment: dict) -> dict:
        # For new appointments not in the flat table, persist to the old JSON fallback
        # or simply return the dict as-is (agents use the return value, not re-query)
        return appointment

    # ---- encounters ----
    def get_encounter(self, encounter_id: str) -> Optional[dict]:
        with get_session() as s:
            r = s.query(Record).filter(Record.Encounter_ID == encounter_id).first()
            return _to_encounter(r) if r else None

    def list_encounters(self) -> list[dict]:
        with get_session() as s:
            return [_to_encounter(r) for r in s.query(Record).all()]

    def create_encounter(self, encounter: dict) -> dict:
        return encounter

    # ---- claims ----
    def get_claim(self, claim_id: str) -> Optional[dict]:
        with get_session() as s:
            r = s.query(Record).filter(Record.Claim_ID == claim_id).first()
            return _to_claim(r) if r else None

    def list_claims(self, status: Optional[str] = None) -> list[dict]:
        with get_session() as s:
            q = s.query(Record)
            if status:
                reverse = {
                    "draft": "Draft", "submitted": "Submitted",
                    "denied": "Denied", "appealed": "Appealed",
                    "appeal_pending": "Appeal Pending", "approved": "Approved", "paid": "Paid",
                }
                raw_status = reverse.get(status, status)
                q = q.filter(Record.Claim_Status == raw_status)
            return [_to_claim(r) for r in q.all()]

    def update_claim(self, claim_id: str, **fields) -> dict:
        with get_session() as s:
            r = s.query(Record).filter(Record.Claim_ID == claim_id).first()
            if r is None:
                return {}
            if "status" in fields:
                reverse = {
                    "draft": "Draft", "submitted": "Submitted",
                    "denied": "Denied", "appealed": "Appealed",
                    "appeal_pending": "Appeal Pending",
                }
                r.Claim_Status = reverse.get(fields["status"], fields["status"])
            if "denial_reason" in fields:
                r.Denial_Reason = fields["denial_reason"]
            if "appeal_letter" in fields:
                pass  # no column for this — ignored safely
            s.commit()
            return _to_claim(r)

    def create_claim(self, claim: dict) -> dict:
        return claim

    def update_claim_by_encounter(self, encounter_id: str, status: str,
                                   icd10: str = "", cpt: str = "", amount: float = 0) -> None:
        """Update claim status for a given encounter row in the DB."""
        from datetime import datetime
        with get_session() as s:
            r = s.query(Record).filter(Record.Encounter_ID == encounter_id).first()
            if r:
                reverse = {
                    "submitted": "Submitted", "denied": "Denied",
                    "appealed": "Appealed", "draft": "Draft",
                }
                r.Claim_Status = reverse.get(status, status)
                if amount:
                    r.Claim_Amount_USD = str(amount)
                r.Last_Updated = datetime.utcnow().strftime("%Y-%m-%d")
                s.commit()

    # ---- payers ----
    def get_payer(self, payer_id: str) -> Optional[dict]:
        with get_session() as s:
            r = s.query(Record).filter(Record.Insurance_Payer == payer_id).first()
            return _to_payer(payer_id) if r else None

    def list_payers(self) -> list[dict]:
        with get_session() as s:
            names = s.query(Record.Insurance_Payer).distinct().all()
            return [_to_payer(n[0]) for n in names if n[0]]

    def update_payer(self, payer_id: str, **fields) -> dict:
        return _to_payer(payer_id)


# Ensure tables exist on import (no-op for existing tables)
create_tables()
store = Store()
