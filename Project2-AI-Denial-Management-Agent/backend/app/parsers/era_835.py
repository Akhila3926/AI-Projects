from app.models import Claim, Denial

PROC_DESCRIPTIONS = {
    "97110": "Therapeutic exercise",
    "98941": "Chiropractic manipulation, 3-4 regions",
    "D2740": "Crown, porcelain/ceramic",
}


def parse(raw_text: str) -> tuple[Claim, Denial]:
    claim_id = None
    billed_amount = None
    paid_amount = None
    date_of_service = None
    patient_name = "UNKNOWN"
    patient_identifier = None
    procedure_code = None
    carc_codes: list[str] = []

    for line in raw_text.strip().splitlines():
        segments = line.strip().rstrip("~").split("*")
        tag = segments[0]

        if tag == "CLP":
            claim_id = segments[1]
            billed_amount = float(segments[3])
            paid_amount = float(segments[4])
        elif tag == "NM1" and len(segments) > 3:
            last_name, first_name = segments[3], segments[4]
            patient_name = f"{first_name} {last_name}".strip().title()
            if "MI" in segments:
                patient_identifier = segments[segments.index("MI") + 1]
        elif tag == "SVC":
            proc = segments[1]
            procedure_code = proc.split(":")[-1] if ":" in proc else proc
        elif tag == "CAS" and segments[1] == "CO":
            carc_codes.append(segments[2])
        elif tag == "DTM" and segments[1] == "472":
            date_of_service = segments[2]

    claim = Claim(
        claim_id=claim_id or "UNKNOWN",
        patient_name=patient_name,
        patient_identifier=patient_identifier,
        payer=None,
        provider=None,
        date_of_service=date_of_service,
        procedure_code=procedure_code,
        procedure_desc=PROC_DESCRIPTIONS.get(procedure_code) if procedure_code else None,
        billed_amount=billed_amount,
        allowed_amount=0.0,
        paid_amount=paid_amount,
    )

    denial = Denial(
        carc_codes=carc_codes,
        rarc_codes=[],
        raw_text=raw_text,
        source_format="835",
    )
    return claim, denial
