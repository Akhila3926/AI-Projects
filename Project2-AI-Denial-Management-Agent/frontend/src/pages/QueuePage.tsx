import { useEffect, useRef, useState } from "react";
import { getQueue, ingest, ingestPdf, type ReviewItem, type SourceFormat } from "../api";
import eobFixture from "../fixtures/sample_eob.txt?raw";
import eraFixture from "../fixtures/sample_835.txt?raw";
import portalFixture from "../fixtures/sample_portal.txt?raw";

const SAMPLES: { label: string; format: SourceFormat; text: string }[] = [
  { label: "Sample EOB", format: "eob_pdf", text: eobFixture },
  { label: "Sample 835 ERA", format: "835", text: eraFixture },
  { label: "Sample Portal Notice", format: "portal", text: portalFixture },
];

const UPLOAD_TARGETS: { label: string; format: SourceFormat; hint: string; accept: string }[] = [
  { label: "Upload EOB", format: "eob_pdf", hint: "PDF or text file", accept: ".pdf,.txt,text/plain,application/pdf" },
  { label: "Upload 835 ERA", format: "835", hint: "Electronic remittance file", accept: ".txt,.edi,text/plain" },
  { label: "Upload Portal Notice", format: "portal", hint: "Payer portal / email export", accept: ".txt,.eml,text/plain" },
];

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // strip the "data:application/pdf;base64," prefix
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function isPdfFile(file: File): boolean {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending Review",
  approved: "Approved",
  rejected: "Rejected",
  routed_to_appeal: "Appeal",
  submitted: "Submitted",
};

function formatCurrency(amount: number | null | undefined): string {
  if (amount == null) return "—";
  return `$${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[parts.length - 1]?.[0] ?? "")).toUpperCase();
}

export function QueuePage({ onSelect }: { onSelect: (id: string) => void }) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingFormat = useRef<SourceFormat | null>(null);

  const refresh = () => {
    getQueue().then(setItems).catch(console.error);
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleIngestSample = async (sample: (typeof SAMPLES)[number]) => {
    setLoading(true);
    try {
      await ingest(sample.format, sample.text);
      refresh();
    } catch (e) {
      alert(`Ingest failed: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const [uploadAccept, setUploadAccept] = useState(".txt");

  const triggerUpload = (format: SourceFormat, accept: string) => {
    pendingFormat.current = format;
    setUploadAccept(accept);
    setTimeout(() => fileInputRef.current?.click(), 0);
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const format = pendingFormat.current;
    e.target.value = "";
    if (!file || !format) return;

    setLoading(true);
    try {
      if (isPdfFile(file)) {
        const base64 = await readFileAsBase64(file);
        await ingestPdf(format, base64);
      } else {
        const text = await file.text();
        await ingest(format, text);
      }
      refresh();
    } catch (err) {
      alert(`Ingest failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const pendingCount = items.filter((i) => i.status === "pending").length;
  const resolvedCount = items.filter((i) => i.status === "approved" || i.status === "submitted").length;
  const appealCount = items.filter((i) => i.status === "routed_to_appeal").length;

  return (
    <div>
      <input type="file" accept={uploadAccept} ref={fileInputRef} onChange={handleFileSelected} hidden />

      <div className="page-heading">
        <h1>Today's Summary</h1>
        <p>Track incoming denials, review proposed corrections, and route each claim to resolution.</p>
      </div>

      <div className="stats-row">
        <div className="card stat-card">
          <div className="stat-icon stat-icon-total">◆</div>
          <div className="stat-body">
            <span className="stat-value">{items.length}</span>
            <span className="stat-label">Total Claims</span>
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-icon stat-icon-pending">●</div>
          <div className="stat-body">
            <span className="stat-value">{pendingCount}</span>
            <span className="stat-label">Pending Review</span>
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-icon stat-icon-approved">✓</div>
          <div className="stat-body">
            <span className="stat-value">{resolvedCount}</span>
            <span className="stat-label">Resolved</span>
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-icon stat-icon-appeal">!</div>
          <div className="stat-body">
            <span className="stat-value">{appealCount}</span>
            <span className="stat-label">Appeals</span>
          </div>
        </div>
      </div>

      <div className="card intake-card">
        <div className="intake-section">
          <h3>Upload a Denied Claim</h3>
          <div className="intake-buttons">
            {UPLOAD_TARGETS.map((target) => (
              <button
                key={target.label}
                className="upload-btn"
                disabled={loading}
                onClick={() => triggerUpload(target.format, target.accept)}
              >
                <span className="upload-btn-label">{target.label}</span>
                <span className="upload-btn-hint">{target.hint}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="intake-divider">
          <span>or try a sample</span>
        </div>

        <div className="intake-section">
          <div className="sample-buttons">
            {SAMPLES.map((sample) => (
              <button key={sample.label} className="sample-chip" disabled={loading} onClick={() => handleIngestSample(sample)}>
                {sample.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card queue-table-card">
        <div className="queue-table-header">
          <h3>Recent Claims</h3>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Claim</th>
              <th>Patient</th>
              <th>Payer</th>
              <th>Billed</th>
              <th>Category</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td className="mono-cell">{item.claim.claim_id}</td>
                <td>
                  <div className="patient-cell">
                    <span className="avatar">{initials(item.claim.patient_name)}</span>
                    <span>{item.claim.patient_name}</span>
                  </div>
                </td>
                <td className="muted-cell">{item.claim.payer ?? "—"}</td>
                <td>{formatCurrency(item.claim.billed_amount)}</td>
                <td>
                  <span className={`category-badge category-${item.correction.category}`}>
                    {item.correction.category.replace("_", " ")}
                  </span>
                </td>
                <td>
                  <span className={`status-pill status-${item.status}`}>
                    {STATUS_LABELS[item.status] ?? item.status}
                  </span>
                </td>
                <td>
                  <button className="review-link-btn" onClick={() => onSelect(item.id)}>
                    Review <span aria-hidden>›</span>
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr className="empty-row">
                <td colSpan={7}>No denials in queue yet — upload a file or try a sample above.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
