"""One-time script: load seed_data.json into SQLite."""
from __future__ import annotations
import json
from pathlib import Path
from app.data.models import (
    create_tables, get_session,
    Patient, Appointment, Encounter, Claim, Payer,
)

SEED = Path(__file__).parent / "data_store" / "seed_data.json"
KNOWN = {
    "patients":     {"id", "name", "dob", "insurance_id", "payer_id", "phone", "email"},
    "appointments": {"id", "patient_id", "provider", "date", "status"},
    "encounters":   {"id", "patient_id", "appointment_id", "provider", "date", "notes", "diagnoses", "procedures"},
    "claims":       {"id", "patient_id", "encounter_id", "payer_id", "status", "amount", "codes", "denial_reason", "appeal_letter"},
    "payers":       {"id", "name", "rules"},
}

def extra(row: dict, table: str) -> dict:
    return {k: v for k, v in row.items() if k not in KNOWN[table]}

def main():
    create_tables()
    data = json.loads(SEED.read_text(encoding="utf-8"))
    with get_session() as s:
        for r in data.get("patients", []):
            s.merge(Patient(id=r["id"], name=r.get("name"), dob=r.get("dob"),
                            insurance_id=r.get("insurance_id"), payer_id=r.get("payer_id"),
                            phone=r.get("phone"), email=r.get("email"), extra=extra(r, "patients")))
        for r in data.get("appointments", []):
            s.merge(Appointment(id=r["id"], patient_id=r.get("patient_id"), provider=r.get("provider"),
                                date=r.get("date"), status=r.get("status"), extra=extra(r, "appointments")))
        for r in data.get("encounters", []):
            s.merge(Encounter(id=r["id"], patient_id=r.get("patient_id"), appointment_id=r.get("appointment_id"),
                              provider=r.get("provider"), date=r.get("date"), notes=r.get("notes"),
                              diagnoses=r.get("diagnoses"), procedures=r.get("procedures"), extra=extra(r, "encounters")))
        for r in data.get("claims", []):
            s.merge(Claim(id=r["id"], patient_id=r.get("patient_id"), encounter_id=r.get("encounter_id"),
                          payer_id=r.get("payer_id"), status=r.get("status"), amount=r.get("amount"),
                          codes=r.get("codes"), denial_reason=r.get("denial_reason"),
                          appeal_letter=r.get("appeal_letter"), extra=extra(r, "claims")))
        for r in data.get("payers", []):
            s.merge(Payer(id=r["id"], name=r.get("name"), rules=r.get("rules"), extra=extra(r, "payers")))
        s.commit()
    print("Migration complete.")

if __name__ == "__main__":
    main()
