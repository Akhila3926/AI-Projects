"""Builds a plausible replacement (frequency code 7) 837 claim as EDI-like text.

Not a fully spec-certified 837 - a real clearinghouse would need the full
transaction envelope (ISA/GS/ST segments, etc). This produces the claim-level
segments needed to demonstrate the replacement-claim workflow.
"""
from app.models import Claim


def generate(original: Claim, corrected: Claim) -> str:
    lines = [
        "ST*837*0001*005010X222A1~",
        f"CLM*{corrected.claim_id}*{corrected.billed_amount or 0:.2f}***11:B:1*Y*A*Y*Y*7~",
        f"REF*F8*{original.claim_id}~",  # F8 = original reference number (replacement claim)
        f"NM1*QC*1*{corrected.patient_name.split()[-1].upper()}*{corrected.patient_name.split()[0].upper()}****MI*{corrected.patient_identifier or ''}~",
        f"DTP*472*D8*{corrected.date_of_service or ''}~",
        f"SV1*HC:{corrected.procedure_code or ''}*{corrected.billed_amount or 0:.2f}*UN*1***1~",
        "SE*6*0001~",
    ]
    return "\n".join(lines)
