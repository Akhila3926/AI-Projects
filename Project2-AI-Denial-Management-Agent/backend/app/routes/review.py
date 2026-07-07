from fastapi import APIRouter, HTTPException
from app.models import ReviewItem
from app import store, clearinghouse
from app.corrector import generate_correction, GENERATABLE_CATEGORIES

router = APIRouter()


@router.get("/review-queue")
def review_queue() -> list[ReviewItem]:
    return store.list_all()


@router.get("/review/{item_id}")
def get_review(item_id: str) -> ReviewItem:
    item = store.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/review/{item_id}/generate-correction")
def generate_correction_route(item_id: str) -> ReviewItem:
    item = store.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.correction.category not in GENERATABLE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"No corrected claim can be generated for category '{item.correction.category}'",
        )
    item.correction = generate_correction(item.claim, item.denial, item.correction)
    store.save(item)
    return item


@router.post("/review/{item_id}/approve")
def approve(item_id: str) -> ReviewItem:
    item = store.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.correction.category in GENERATABLE_CATEGORIES and not item.correction.corrected_claim:
        raise HTTPException(
            status_code=400,
            detail="Generate the corrected claim before approving",
        )
    item.status = "routed_to_appeal" if item.correction.category == "medical_necessity" else "approved"
    store.save(item)
    return item


@router.post("/review/{item_id}/reject")
def reject(item_id: str) -> ReviewItem:
    item = store.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.status = "rejected"
    store.save(item)
    return item


@router.post("/review/{item_id}/submit-clearinghouse")
def submit_clearinghouse(item_id: str) -> ReviewItem:
    item = store.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Only approved, correctable claims can be submitted (status={item.status})",
        )
    item.clearinghouse_submission = clearinghouse.submit(item.claim.claim_id)
    item.status = "submitted"
    store.save(item)
    return item
