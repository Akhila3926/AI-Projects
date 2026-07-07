from pathlib import Path
from app.parsers import era_835, eob_pdf, portal_notice
from app.classifier import classify, annotate_descriptions
from app.corrector import explain, generate_correction

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_eob_data_error_pipeline():
    raw = _load("sample_eob.txt")
    claim, denial = eob_pdf.parse(raw)
    denial = annotate_descriptions(denial)
    category = classify(denial)

    assert claim.claim_id == "CLM-2026-04871"
    assert claim.patient_name == "John Doe"
    assert "16" in denial.carc_codes
    assert "N382" in denial.rarc_codes
    assert category == "data_error"

    correction = explain(claim, denial, category)
    assert correction.category == "data_error"
    assert correction.corrected_claim is None
    assert correction.corrected_fields == {}

    correction = generate_correction(claim, denial, correction)
    assert correction.corrected_claim is not None
    assert "patient_identifier" in correction.corrected_fields


def test_835_auth_gap_pipeline():
    raw = _load("sample_835.txt")
    claim, denial = era_835.parse(raw)
    denial = annotate_descriptions(denial)
    category = classify(denial)

    assert claim.claim_id == "CLM-2026-05512"
    assert claim.patient_name == "Mary Smith"
    assert "197" in denial.carc_codes
    assert category == "auth_gap"

    correction = explain(claim, denial, category)
    assert correction.category == "auth_gap"
    assert correction.corrected_claim is None

    correction = generate_correction(claim, denial, correction)
    assert correction.corrected_claim is not None
    assert "prior_authorization_number" in correction.corrected_fields


def test_portal_medical_necessity_pipeline():
    raw = _load("sample_portal.txt")
    claim, denial = portal_notice.parse(raw)
    denial = annotate_descriptions(denial)
    category = classify(denial)

    assert claim.claim_id == "E7729941"
    assert claim.patient_name == "Robert Chen"
    assert "50" in denial.carc_codes
    assert "N115" in denial.rarc_codes
    assert category == "medical_necessity"

    correction = explain(claim, denial, category)
    assert correction.category == "medical_necessity"
    assert correction.corrected_claim is None
    assert correction.appeal_notes is not None
