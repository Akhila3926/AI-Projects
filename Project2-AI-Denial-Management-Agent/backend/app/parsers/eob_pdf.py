import re
from app.models import Claim, Denial


def parse(raw_text: str) -> tuple[Claim, Denial]:
    payer_match = re.search(r"^(.+?)\s*\|\s*Remittance Date", raw_text, re.MULTILINE)
    provider_match = re.search(r"Provider:\s*(.+?)\s*\|\s*NPI", raw_text)
    patient_match = re.search(r"Patient:\s*(.+?)\s*\|\s*Member ID:\s*(\S+)", raw_text)
    claim_match = re.search(r"Claim #:\s*(\S+)\s*\|\s*Date of Service:\s*(\S+)", raw_text)
    cpt_match = re.search(r"CPT\s+(\d+)\s*\((.+?)\)", raw_text)
    amounts_match = re.search(
        r"Billed:\s*\$([\d,.]+)\s*\|\s*Allowed:\s*\$([\d,.]+)\s*\|\s*Paid:\s*\$([\d,.]+)", raw_text
    )
    carc_codes = re.findall(r"\bCO-(\d+)\b", raw_text)
    rarc_codes = re.findall(r"\b(N\d+)\b", raw_text)

    claim = Claim(
        claim_id=claim_match.group(1) if claim_match else "UNKNOWN",
        patient_name=patient_match.group(1).strip() if patient_match else "UNKNOWN",
        patient_identifier=patient_match.group(2) if patient_match else None,
        payer=payer_match.group(1).strip() if payer_match else None,
        provider=provider_match.group(1).strip() if provider_match else None,
        date_of_service=claim_match.group(2) if claim_match else None,
        procedure_code=cpt_match.group(1) if cpt_match else None,
        procedure_desc=cpt_match.group(2) if cpt_match else None,
        billed_amount=float(amounts_match.group(1).replace(",", "")) if amounts_match else None,
        allowed_amount=float(amounts_match.group(2).replace(",", "")) if amounts_match else None,
        paid_amount=float(amounts_match.group(3).replace(",", "")) if amounts_match else None,
    )

    denial = Denial(
        carc_codes=carc_codes,
        rarc_codes=rarc_codes,
        raw_text=raw_text,
        source_format="eob_pdf",
    )
    return claim, denial
