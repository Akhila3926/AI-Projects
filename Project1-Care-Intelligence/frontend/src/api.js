const BASE = "http://localhost:8000";

async function req(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  getFeed: () => req("/api/feed"),
  getOutcomes: () => req("/api/outcomes"),
  getApprovals: () => req("/api/approvals"),
  getDataSummary: () => req("/api/data-summary"),

  recoverNoShows: () =>
    req("/api/agents/patient-access/recover-no-shows", { method: "POST" }),

  sendPatientRequest: (requestText) =>
    req("/api/agents/patient-access/request", {
      method: "POST",
      body: JSON.stringify({ request_text: requestText }),
    }),

  sendChatMessage: (requestText) =>
    req("/api/chat", {
      method: "POST",
      body: JSON.stringify({ request_text: requestText }),
    }),

  runBillingCoding: (encounterId) =>
    req(`/api/agents/billing-coding/${encounterId}`, { method: "POST" }),

  runDenialDiagnosis: (claimId) =>
    req(`/api/agents/denial-management/diagnose/${claimId}`, { method: "POST" }),

  approveDenial: (claimId) =>
    req(`/api/agents/denial-management/approve/${claimId}`, { method: "POST" }),

  dismissApproval: (approvalId) =>
    req(`/api/approvals/${approvalId}/dismiss`, { method: "POST" }),

  runCascade: (patientId, provider, dateIso) =>
    req("/api/cascade/run", {
      method: "POST",
      body: JSON.stringify({ patient_id: patientId, provider, date_iso: dateIso }),
    }),
};
