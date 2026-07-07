import type { Claim, Correction } from "../api";

const FIELD_LABELS: Record<keyof Claim, string> = {
  claim_id: "Claim ID",
  patient_name: "Patient Name",
  patient_identifier: "Patient Identifier",
  payer: "Payer",
  provider: "Provider",
  date_of_service: "Date of Service",
  procedure_code: "Procedure Code",
  procedure_desc: "Procedure Description",
  billed_amount: "Billed Amount",
  allowed_amount: "Allowed Amount",
  paid_amount: "Paid Amount",
};

export function ClaimDiff({ original, corrected, correction }: { original: Claim; corrected?: Claim | null; correction: Correction }) {
  if (!corrected) {
    return (
      <div className="card claim-diff no-correction">
        <p>No corrected claim — this denial cannot be resolved by resubmission (see appeal guidance).</p>
      </div>
    );
  }

  const fields = Object.keys(FIELD_LABELS) as (keyof Claim)[];

  return (
    <div className="card claim-diff">
      <table>
        <thead>
          <tr>
            <th>Field</th>
            <th>Original Claim</th>
            <th>Corrected Claim</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const before = original[field];
            const after = corrected[field];
            const changed = String(before ?? "") !== String(after ?? "");
            return (
              <tr key={field} className={changed ? "changed" : ""}>
                <td>{FIELD_LABELS[field]}</td>
                <td>{before ?? "—"}</td>
                <td>{after ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {Object.keys(correction.corrected_fields).length > 0 && (
        <div className="field-notes">
          <strong>Change notes:</strong>
          <ul>
            {Object.entries(correction.corrected_fields).map(([field, note]) => (
              <li key={field}>
                <strong>{field}:</strong> {note}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
