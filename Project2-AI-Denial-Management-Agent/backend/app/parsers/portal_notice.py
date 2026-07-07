import re
from app.models import Claim, Denial


def parse(raw_text: str) -> tuple[Claim, Denial]:
    from_match = re.search(r"From:\s*.+@([\w.-]+)", raw_text)
    claim_match = re.search(r"Claim ID:\s*(\S+)\s*\|\s*Patient:\s*(.+?)\s*\|\s*DOB", raw_text)
    provider_match = re.search(r"Provider:\s*(.+)", raw_text)
    service_match = re.search(r"Service:\s*(\S+)\s*\((.+?)\)\s*\|\s*DOS:\s*(\S+)", raw_text)
    billed_match = re.search(r"Billed:\s*\$([\d,.]+)", raw_text)
    carc_codes = re.findall(r"\bCO-(\d+)\b", raw_text)
    rarc_codes = re.findall(r"\b(N\d+)\b", raw_text)

    payer = None
    if from_match:
        domain = from_match.group(1)
        payer = domain.split(".")[0].capitalize()

    claim = Claim(
        claim_id=claim_match.group(1) if claim_match else "UNKNOWN",
        patient_name=claim_match.group(2).strip() if claim_match else "UNKNOWN",
        patient_identifier=None,
        payer=payer,
        provider=provider_match.group(1).strip() if provider_match else None,
        date_of_service=service_match.group(3) if service_match else None,
        procedure_code=service_match.group(1) if service_match else None,
        procedure_desc=service_match.group(2) if service_match else None,
        billed_amount=float(billed_match.group(1).replace(",", "")) if billed_match else None,
        allowed_amount=None,
        paid_amount=0.0,
    )

    denial = Denial(
        carc_codes=carc_codes,
        rarc_codes=rarc_codes,
        raw_text=raw_text,
        source_format="portal",
    )
    return claim, denial
