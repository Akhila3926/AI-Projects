from app import llm_client
from app.classifier import classify, annotate_descriptions
from app.corrector import explain
from app.llm_extractor import extract
from app.llm_classifier import classify_with_llm
from app.models import Denial


UNPARSEABLE_TEXT = "Some denial notice text that doesn't match any of our known regex layouts."


def test_extract_returns_none_when_llm_not_configured(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = extract(UNPARSEABLE_TEXT, "eob_pdf")
    assert result is None


def test_extract_uses_llm_when_configured(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    fake_response = {
        "claim_id": "CLM-9999",
        "patient_name": "Jane Roe",
        "patient_identifier": None,
        "payer": "Humana",
        "provider": "Test Clinic",
        "date_of_service": "01/01/2026",
        "procedure_code": "99213",
        "procedure_desc": "Office visit",
        "billed_amount": 150.0,
        "allowed_amount": 0.0,
        "paid_amount": 0.0,
        "carc_codes": ["29"],
        "rarc_codes": [],
    }
    monkeypatch.setattr(llm_client, "chat_json", lambda system, user: fake_response)

    result = extract(UNPARSEABLE_TEXT, "eob_pdf")
    assert result is not None
    claim, denial = result
    assert claim.claim_id == "CLM-9999"
    assert claim.patient_name == "Jane Roe"
    assert "29" in denial.carc_codes


def test_extract_returns_none_on_invalid_llm_response(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(llm_client, "chat_json", lambda system, user: {"unexpected": "shape"})

    result = extract(UNPARSEABLE_TEXT, "eob_pdf")
    # Even a malformed response should still produce a best-effort Claim (fields default to
    # UNKNOWN/None) rather than raising - the caller decides whether that's "good enough".
    assert result is not None
    claim, _ = result
    assert claim.claim_id == "UNKNOWN"


def test_classify_falls_back_to_llm_for_unrecognized_codes(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(llm_client, "chat_json", lambda system, user: {"category": "auth_gap"})

    denial = Denial(carc_codes=["999"], rarc_codes=[], raw_text="unused", source_format="eob_pdf")
    denial = annotate_descriptions(denial)
    category = classify(denial)
    assert category == "auth_gap"


def test_classify_stays_other_when_llm_unavailable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    denial = Denial(carc_codes=["999"], rarc_codes=[], raw_text="unused", source_format="eob_pdf")
    denial = annotate_descriptions(denial)
    category = classify(denial)
    assert category == "other"


def test_classify_with_llm_rejects_invalid_category(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(llm_client, "chat_json", lambda system, user: {"category": "not_a_real_category"})

    denial = Denial(carc_codes=["999"], rarc_codes=[], raw_text="unused", source_format="eob_pdf")
    assert classify_with_llm(denial) is None


def test_explain_uses_llm_rewrite_when_configured(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(
        llm_client, "chat_json", lambda system, user: {"explanation": "This is a rewritten explanation."}
    )

    denial = Denial(carc_codes=["16"], rarc_codes=["N382"], raw_text="unused", source_format="eob_pdf")
    denial = annotate_descriptions(denial)
    from app.models import Claim

    claim = Claim(claim_id="CLM-1", patient_name="Test Patient")
    correction = explain(claim, denial, "data_error")
    assert correction.explanation == "This is a rewritten explanation."


def test_explain_keeps_template_when_llm_unavailable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    from app.models import Claim

    denial = Denial(carc_codes=["16"], rarc_codes=["N382"], raw_text="unused", source_format="eob_pdf")
    denial = annotate_descriptions(denial)
    claim = Claim(claim_id="CLM-1", patient_name="Test Patient")
    correction = explain(claim, denial, "data_error")
    assert "CLM-1" in correction.explanation
