import base64
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models import SourceFormat, ReviewItem
from app.parsers import era_835, eob_pdf, portal_notice
from app.classifier import classify, annotate_descriptions
from app.corrector import explain
from app import store, llm_client
from app.llm_extractor import extract as extract_with_llm
from app.pdf_extractor import extract_text as extract_pdf_text

router = APIRouter()

PARSERS = {
    "835": era_835.parse,
    "eob_pdf": eob_pdf.parse,
    "portal": portal_notice.parse,
}


class IngestRequest(BaseModel):
    format: SourceFormat
    raw_text: str = ""
    raw_pdf_base64: str | None = None


@router.post("/ingest")
def ingest(request: IngestRequest) -> ReviewItem:
    parser = PARSERS.get(request.format)
    if not parser:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")

    raw_text = request.raw_text
    if request.raw_pdf_base64:
        try:
            pdf_bytes = base64.b64decode(request.raw_pdf_base64)
            raw_text = extract_pdf_text(pdf_bytes)
        except Exception:
            raise HTTPException(status_code=422, detail="Could not read this PDF file.")
        if not raw_text:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No text could be extracted from this PDF - it may be a scanned image "
                    "without a text layer, which isn't supported yet."
                ),
            )

    claim, denial = parser(raw_text)

    extraction_incomplete = claim.claim_id == "UNKNOWN" or (not denial.carc_codes and not denial.rarc_codes)
    if extraction_incomplete and llm_client.is_configured():
        llm_result = extract_with_llm(raw_text, request.format)
        if llm_result:
            claim, denial = llm_result

    denial = annotate_descriptions(denial)
    category = classify(denial)
    correction = explain(claim, denial, category)

    item = ReviewItem(
        id=str(uuid.uuid4()),
        claim=claim,
        denial=denial,
        correction=correction,
    )
    store.save(item)
    return item
