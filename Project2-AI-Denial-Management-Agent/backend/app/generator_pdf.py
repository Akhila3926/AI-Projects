import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.models import Claim, Correction


def generate(original: Claim, corrected: Claim, correction: Correction) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 72

    def line(text: str, size: int = 11, gap: int = 16):
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(72, y, text)
        y -= gap

    line("CORRECTED CLAIM — CONFIRMATION COPY", 14, 24)
    line(f"Claim ID: {corrected.claim_id}  (Replacement of original claim)")
    line(f"Patient: {corrected.patient_name}")
    line(f"Payer: {corrected.payer or 'N/A'}")
    line(f"Provider: {corrected.provider or 'N/A'}")
    line(f"Date of Service: {corrected.date_of_service or 'N/A'}")
    line(f"Procedure: {corrected.procedure_code or 'N/A'} - {corrected.procedure_desc or ''}")
    line(f"Billed Amount: ${corrected.billed_amount or 0:.2f}")
    y -= 8
    line("Denial Explanation:", 12, 18)
    for chunk in _wrap(correction.explanation, 95):
        line(chunk, 10, 13)
    y -= 8
    line("Corrected Fields:", 12, 18)
    for field, change in correction.corrected_fields.items():
        line(f"- {field}: {change}", 10, 13)

    c.showPage()
    c.save()
    return buffer.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines
