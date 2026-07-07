import { useEffect, useState } from "react";
import {
  approve,
  generateCorrection,
  getReviewItem,
  output837Url,
  outputPdfUrl,
  reject,
  submitToClearinghouse,
  type ReviewItem,
} from "../api";
import { ClaimDiff } from "../components/ClaimDiff";
import { DenialExplanation } from "../components/DenialExplanation";

const GENERATABLE_CATEGORIES = new Set(["data_error", "auth_gap"]);

export function ReviewPage({ id, onBack }: { id: string; onBack: () => void }) {
  const [item, setItem] = useState<ReviewItem | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => {
    getReviewItem(id).then(setItem).catch(console.error);
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!item) return <div className="review-page">Loading…</div>;

  const handleGenerateCorrection = async () => {
    setBusy(true);
    try {
      await generateCorrection(id);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    setBusy(true);
    try {
      await approve(id);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await reject(id);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async () => {
    setBusy(true);
    try {
      await submitToClearinghouse(id);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const isGeneratable = GENERATABLE_CATEGORIES.has(item.correction.category);
  const hasCorrectedClaim = Boolean(item.correction.corrected_claim);
  const awaitingGenerateConfirmation = item.status === "pending" && isGeneratable && !hasCorrectedClaim;
  const canSubmit = item.status === "approved" && hasCorrectedClaim;
  const canViewOutputs = (item.status === "approved" || item.status === "submitted") && hasCorrectedClaim;

  return (
    <div>
      <button className="back-link" onClick={onBack}>
        ← Back to queue
      </button>
      <div className="review-header">
        <h1>
          Claim {item.claim.claim_id} — {item.claim.patient_name}
        </h1>
        <p className="status-line">
          Status: <span className={`status-pill status-${item.status}`}>{item.status}</span>
        </p>
      </div>

      <DenialExplanation denial={item.denial} correction={item.correction} />

      {awaitingGenerateConfirmation && (
        <div className="card generate-prompt">
          <p>
            The denial reason has been identified. Would you like to generate a corrected claim for this denial so
            it can be reviewed and approved for resubmission?
          </p>
          <div className="actions">
            <button className="approve-btn" disabled={busy} onClick={handleGenerateCorrection}>
              Generate Corrected Claim
            </button>
            <button className="reject-btn" disabled={busy} onClick={handleReject}>
              Reject
            </button>
          </div>
        </div>
      )}

      {hasCorrectedClaim && (
        <>
          <h2>Original vs. Corrected Claim</h2>
          <ClaimDiff original={item.claim} corrected={item.correction.corrected_claim} correction={item.correction} />
        </>
      )}

      {item.status === "pending" && hasCorrectedClaim && (
        <div className="actions">
          <button className="approve-btn" disabled={busy} onClick={handleApprove}>
            Approve
          </button>
          <button className="reject-btn" disabled={busy} onClick={handleReject}>
            Reject
          </button>
        </div>
      )}

      {item.status === "pending" && !isGeneratable && (
        <div className="actions">
          <button className="approve-btn" disabled={busy} onClick={handleApprove}>
            Approve
          </button>
          <button className="reject-btn" disabled={busy} onClick={handleReject}>
            Reject
          </button>
        </div>
      )}

      {item.status === "routed_to_appeal" && (
        <p className="info-banner">
          This denial has been routed to the appeal workflow (reason above). No corrected claim resubmission will be
          generated — it requires an appeal with supporting documentation.
        </p>
      )}

      {canViewOutputs && (
        <div className="card outputs">
          <h2>Resubmission Outputs</h2>
          <a href={output837Url(id)} target="_blank" rel="noreferrer">
            Download corrected 837 (replacement claim)
          </a>
          <a href={outputPdfUrl(id)} target="_blank" rel="noreferrer">
            Download corrected claim PDF
          </a>
        </div>
      )}

      {canSubmit && (
        <div className="actions">
          <button className="submit-btn" disabled={busy} onClick={handleSubmit}>
            Submit to Clearinghouse
          </button>
        </div>
      )}

      {item.status === "submitted" && item.clearinghouse_submission && (
        <div className="card clearinghouse-confirmation">
          <h2>Clearinghouse Submission Confirmed</h2>
          <p>
            <strong>Confirmation #:</strong> {item.clearinghouse_submission.confirmation_number}
          </p>
          <p>
            <strong>Clearinghouse:</strong> {item.clearinghouse_submission.clearinghouse_name}
          </p>
          <p>
            <strong>Status:</strong> {item.clearinghouse_submission.status}
          </p>
          <p>
            <strong>Submitted at:</strong> {new Date(item.clearinghouse_submission.submitted_at).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
