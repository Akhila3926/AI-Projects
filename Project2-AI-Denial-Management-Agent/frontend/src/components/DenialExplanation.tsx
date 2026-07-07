import type { Denial, Correction } from "../api";

const CATEGORY_LABELS: Record<string, string> = {
  data_error: "Data Error — Correctable",
  auth_gap: "Authorization Gap — Correctable",
  medical_necessity: "Medical Necessity — Requires Appeal",
  other: "Unrecognized — Needs Manual Review",
};

export function DenialExplanation({ denial, correction }: { denial: Denial; correction: Correction }) {
  return (
    <div className="card explanation">
      <span className={`category-badge category-${correction.category}`}>
        {CATEGORY_LABELS[correction.category] ?? correction.category}
      </span>
      <p className="explanation-text">{correction.explanation}</p>
      <div className="codes">
        {denial.carc_codes.map((code, i) => (
          <div key={`carc-${code}`} className="code-row">
            <strong>CO-{code}</strong>: {denial.carc_descriptions[i]}
          </div>
        ))}
        {denial.rarc_codes.map((code, i) => (
          <div key={`rarc-${code}`} className="code-row">
            <strong>{code}</strong>: {denial.rarc_descriptions[i]}
          </div>
        ))}
      </div>
      {correction.appeal_notes && (
        <div className="appeal-notes">
          <strong>Appeal guidance:</strong> {correction.appeal_notes}
        </div>
      )}
    </div>
  );
}
