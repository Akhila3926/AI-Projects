from typing import Optional, Literal
from pydantic import BaseModel

DenialCategory = Literal["data_error", "auth_gap", "medical_necessity", "other"]
ReviewStatus = Literal["pending", "approved", "rejected", "routed_to_appeal", "submitted"]
SourceFormat = Literal["835", "eob_pdf", "portal"]


class Claim(BaseModel):
    claim_id: str
    patient_name: str
    patient_identifier: Optional[str] = None
    payer: Optional[str] = None
    provider: Optional[str] = None
    date_of_service: Optional[str] = None
    procedure_code: Optional[str] = None
    procedure_desc: Optional[str] = None
    billed_amount: Optional[float] = None
    allowed_amount: Optional[float] = None
    paid_amount: Optional[float] = None


class Denial(BaseModel):
    carc_codes: list[str] = []
    rarc_codes: list[str] = []
    carc_descriptions: list[str] = []
    rarc_descriptions: list[str] = []
    raw_text: str
    source_format: SourceFormat


class Correction(BaseModel):
    category: DenialCategory
    explanation: str
    corrected_fields: dict[str, str] = {}
    corrected_claim: Optional[Claim] = None
    appeal_notes: Optional[str] = None


class ClearinghouseSubmission(BaseModel):
    confirmation_number: str
    submitted_at: str
    clearinghouse_name: str
    status: str


class ReviewItem(BaseModel):
    id: str
    claim: Claim
    denial: Denial
    correction: Correction
    status: ReviewStatus = "pending"
    clearinghouse_submission: Optional[ClearinghouseSubmission] = None
