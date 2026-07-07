from fastapi import APIRouter, HTTPException, Response
from app import store
from app.generator_837 import generate as generate_837
from app.generator_pdf import generate as generate_pdf

router = APIRouter()


def _get_approved_item(item_id: str):
    item = store.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status not in ("approved", "submitted"):
        raise HTTPException(
            status_code=400,
            detail=f"Claim outputs are only available for approved, correctable claims (status={item.status})",
        )
    if not item.correction.corrected_claim:
        raise HTTPException(status_code=400, detail="No corrected claim available for this denial category")
    return item


@router.get("/outputs/{item_id}/837")
def get_837(item_id: str):
    item = _get_approved_item(item_id)
    edi_text = generate_837(item.claim, item.correction.corrected_claim)
    return Response(content=edi_text, media_type="text/plain")


@router.get("/outputs/{item_id}/pdf")
def get_pdf(item_id: str):
    item = _get_approved_item(item_id)
    pdf_bytes = generate_pdf(item.claim, item.correction.corrected_claim, item.correction)
    return Response(content=pdf_bytes, media_type="application/pdf")
