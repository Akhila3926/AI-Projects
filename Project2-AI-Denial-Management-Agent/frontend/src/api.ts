const BASE_URL = "http://localhost:8000";

export type SourceFormat = "835" | "eob_pdf" | "portal";
export type DenialCategory = "data_error" | "auth_gap" | "medical_necessity" | "other";
export type ReviewStatus = "pending" | "approved" | "rejected" | "routed_to_appeal" | "submitted";

export interface Claim {
  claim_id: string;
  patient_name: string;
  patient_identifier?: string | null;
  payer?: string | null;
  provider?: string | null;
  date_of_service?: string | null;
  procedure_code?: string | null;
  procedure_desc?: string | null;
  billed_amount?: number | null;
  allowed_amount?: number | null;
  paid_amount?: number | null;
}

export interface Denial {
  carc_codes: string[];
  rarc_codes: string[];
  carc_descriptions: string[];
  rarc_descriptions: string[];
  raw_text: string;
  source_format: SourceFormat;
}

export interface Correction {
  category: DenialCategory;
  explanation: string;
  corrected_fields: Record<string, string>;
  corrected_claim?: Claim | null;
  appeal_notes?: string | null;
}

export interface ClearinghouseSubmission {
  confirmation_number: string;
  submitted_at: string;
  clearinghouse_name: string;
  status: string;
}

export interface ReviewItem {
  id: string;
  claim: Claim;
  denial: Denial;
  correction: Correction;
  status: ReviewStatus;
  clearinghouse_submission?: ClearinghouseSubmission | null;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export function ingest(format: SourceFormat, raw_text: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, raw_text }),
  }).then((r) => handle<ReviewItem>(r));
}

export function ingestPdf(format: SourceFormat, raw_pdf_base64: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, raw_pdf_base64 }),
  }).then((r) => handle<ReviewItem>(r));
}

export function getQueue(): Promise<ReviewItem[]> {
  return fetch(`${BASE_URL}/review-queue`).then((r) => handle<ReviewItem[]>(r));
}

export function getReviewItem(id: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/review/${id}`).then((r) => handle<ReviewItem>(r));
}

export function generateCorrection(id: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/review/${id}/generate-correction`, { method: "POST" }).then((r) => handle<ReviewItem>(r));
}

export function approve(id: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/review/${id}/approve`, { method: "POST" }).then((r) => handle<ReviewItem>(r));
}

export function reject(id: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/review/${id}/reject`, { method: "POST" }).then((r) => handle<ReviewItem>(r));
}

export function submitToClearinghouse(id: string): Promise<ReviewItem> {
  return fetch(`${BASE_URL}/review/${id}/submit-clearinghouse`, { method: "POST" }).then((r) => handle<ReviewItem>(r));
}

export function output837Url(id: string): string {
  return `${BASE_URL}/outputs/${id}/837`;
}

export function outputPdfUrl(id: string): string {
  return `${BASE_URL}/outputs/${id}/pdf`;
}
