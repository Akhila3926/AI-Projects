import io
import base64

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from fastapi.testclient import TestClient

from app.pdf_extractor import extract_text
from app.main import app


def _make_pdf_bytes(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.showPage()
    c.save()
    return buffer.getvalue()


def test_extract_text_round_trip():
    pdf_bytes = _make_pdf_bytes(["Claim #: CLM-TEST-001", "CO-16 denial reason"])
    text = extract_text(pdf_bytes)
    assert "CLM-TEST-001" in text
    assert "CO-16" in text


def test_ingest_endpoint_accepts_real_pdf_upload():
    pdf_bytes = _make_pdf_bytes(
        [
            "Provider: Test Clinic | NPI: 1234567890",
            "Patient: Jane Roe | Member ID: X12345",
            "Claim #: CLM-PDF-777 | Date of Service: 01/01/2026",
            "CPT 99213 (Office visit)",
            "Billed: $100.00 | Allowed: $0.00 | Paid: $0.00",
            "DENIAL REASON:",
            "CO-16 — Claim/service lacks information needed for adjudication",
            "N382 — Missing/incomplete/invalid patient identifier",
        ]
    )
    b64 = base64.b64encode(pdf_bytes).decode()

    client = TestClient(app)
    response = client.post("/ingest", json={"format": "eob_pdf", "raw_pdf_base64": b64})
    assert response.status_code == 200
    data = response.json()
    assert data["claim"]["claim_id"] == "CLM-PDF-777"
    assert "16" in data["denial"]["carc_codes"]


def test_ingest_endpoint_rejects_pdf_with_no_extractable_text():
    # An empty PDF page has no text layer at all - simulates a scanned/image-only PDF.
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.showPage()
    c.save()
    b64 = base64.b64encode(buffer.getvalue()).decode()

    client = TestClient(app)
    response = client.post("/ingest", json={"format": "eob_pdf", "raw_pdf_base64": b64})
    assert response.status_code == 422
