import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from 'recharts'
import './App.css'

// ── Icons ──────────────────────────────────────────────────────────────────

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg className="spin" width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M21 12a9 9 0 1 1-2.6-6.4" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function CILogo({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      {/* Heart outline */}
      <path
        d="M50 28 C37 12 6 16 6 39 C6 59 27 74 50 89 C73 74 94 59 94 39 C94 16 63 12 50 28Z"
        fill="none" stroke="#1a6fba" strokeWidth="6" strokeLinejoin="round"
      />
      {/* Medical cross — vertical bar */}
      <rect x="39" y="21" width="22" height="49" rx="4" fill="#1a6fba" />
      {/* Medical cross — horizontal bar */}
      <rect x="23" y="38" width="54" height="16" rx="4" fill="#1a6fba" />
      {/* Circuit traces */}
      <line x1="57" y1="42" x2="75" y2="42" stroke="white" strokeWidth="3" strokeLinecap="round" />
      <circle cx="57" cy="42" r="3.5" fill="white" />
      <circle cx="75" cy="42" r="3.5" fill="white" />
      <line x1="57" y1="49" x2="71" y2="49" stroke="white" strokeWidth="3" strokeLinecap="round" />
      <circle cx="57" cy="49" r="3.5" fill="white" />
      <circle cx="71" cy="49" r="3.5" fill="white" />
      <line x1="57" y1="56" x2="75" y2="56" stroke="white" strokeWidth="3" strokeLinecap="round" />
      <circle cx="57" cy="56" r="3.5" fill="white" />
      <circle cx="75" cy="56" r="3.5" fill="white" />
      {/* Cupped hand */}
      <path
        d="M27 73 Q33 61 43 64 Q47 66 50 69 Q53 66 57 64 Q67 61 73 73 Q65 81 50 83 Q35 81 27 73Z"
        fill="#0f4a8a"
      />
    </svg>
  )
}

// ── Constants ──────────────────────────────────────────────────────────────

const SUGGESTED_PROMPTS = [
  { text: "Process today's completed visits", desc: "Code and submit all pending encounter claims" },
  { text: "Run today's full workflow",        desc: "Book, code, and submit end-to-end for a patient" },
  { text: "Recover no-show appointments",     desc: "Contact missed patients and rebook" },
  { text: "Generate today's summary",         desc: "Review outcomes and agent performance" },
  { text: "Show pending approvals",           desc: "Review items waiting for staff sign-off" },
]

const AGENT_META = {
  patient_access:    { label: 'Patient Access Agent',    color: '#2563eb' },
  billing_coding:    { label: 'Billing & Coding Agent',  color: '#16a34a' },
  denial_management: { label: 'Denial Management Agent', color: '#dc2626' },
}

const STATUS_COLOR = {
  idle:    'rgba(255,255,255,0.16)',
  working: '#f5a534',
  done:    '#52b87a',
  error:   '#e05252',
}

const CLAIM_STATUS_STYLE = {
  submitted:              { bg: '#e8f4ec', color: '#2d7a4a', label: 'Submitted' },
  denied:                 { bg: '#fdecea', color: '#b3402f', label: 'Denied'    },
  appeal_pending_approval:{ bg: '#fef6e4', color: '#b4781e', label: 'Appeal Pending' },
  appealed:               { bg: '#e8eef8', color: '#3a5f8a', label: 'Appealed'  },
  draft:                  { bg: '#f2f0eb', color: '#7a6a55', label: 'Draft'     },
}

const APPT_STATUS_STYLE = {
  booked:            { bg: '#e8f4ec', color: '#2d7a4a' },
  cancelled:         { bg: '#fdecea', color: '#b3402f' },
  completed:         { bg: '#e8eef8', color: '#3a5f8a' },
  no_show_recovered: { bg: '#fef6e4', color: '#b4781e' },
  no_show:           { bg: '#fdecea', color: '#b3402f' },
}

function initials(name = '') {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

// ── Reply renderer ─────────────────────────────────────────────────────────

function ReplyText({ text }) {
  const lines = (text || '').split('\n')
  const groups = []
  let bullets = []

  lines.forEach((line, i) => {
    const t = line.trim()
    if (t.startsWith('•') || t.startsWith('-')) {
      const html = t.slice(1).trim()
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
      bullets.push(<li key={i} dangerouslySetInnerHTML={{ __html: html }} />)
    } else {
      if (bullets.length) {
        groups.push(<ul key={`ul-${i}`} className="reply-list">{bullets}</ul>)
        bullets = []
      }
      if (t) {
        const html = t
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/`(.*?)`/g, '<code>$1</code>')
        groups.push(<p key={i} className="reply-line" dangerouslySetInnerHTML={{ __html: html }} />)
      }
    }
  })
  if (bullets.length) groups.push(<ul key="ul-end" className="reply-list">{bullets}</ul>)
  return <>{groups}</>
}

// ── Step row ───────────────────────────────────────────────────────────────

function StepRow({ step }) {
  const agent = step.agent && AGENT_META[step.agent]
  return (
    <div className={`step-row step-${step.status}`}>
      <span className="step-icon">
        {step.status === 'done'    && <CheckIcon />}
        {step.status === 'active'  && <SpinnerIcon />}
        {step.status === 'pending' && <span className="step-dot-sm" />}
      </span>
      <span className="step-msg">{step.message}</span>
      {agent && step.status === 'active' && (
        <span className="step-badge" style={{ color: agent.color, borderColor: agent.color + '50' }}>
          {agent.label}
        </span>
      )}
    </div>
  )
}

// ── AI message ─────────────────────────────────────────────────────────────

function AiMessage({ msg, onAction }) {
  const agent = msg.agent && AGENT_META[msg.agent]
  return (
    <div className="msg-ai">
      <div className="ai-avatar"><CILogo size={20} /></div>
      <div className="ai-body">
        {agent && (
          <div className="ai-agent-tag" style={{ color: agent.color }}>{agent.label}</div>
        )}
        {msg.steps.length > 0 && (
          <div className="steps-wrap">
            {msg.steps.map((s, i) => <StepRow key={i} step={s} />)}
          </div>
        )}
        {msg.reply && (
          <div className={`ai-reply${msg.steps.length > 0 ? ' with-divider' : ''}`}>
            <ReplyText text={msg.reply} />
          </div>
        )}
        {!msg.done && !msg.reply && <span className="cursor-blink" />}
      </div>
    </div>
  )
}

// ── Welcome screen ─────────────────────────────────────────────────────────

function WelcomeScreen({ onPrompt, onActivate }) {
  return (
    <div className="welcome">
      <div className="welcome-icon"><CILogo size={56} /></div>
      <h1 className="welcome-title">Care Intelligence</h1>
      <p className="welcome-sub">Your autonomous AI agent workforce is standing by.</p>
      <button className="activate-btn" onClick={onActivate}>
        <svg className="activate-icon" width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        <span className="activate-btn-text">
          <span className="activate-btn-title">Activate All Agents</span>
          <span className="activate-btn-desc">Scan, discover, and autonomously process all open work items</span>
        </span>
      </button>
      <div className="prompts-divider"><span>or ask a specific question</span></div>
      <div className="prompts-grid">
        {SUGGESTED_PROMPTS.map(p => (
          <button key={p.text} className="prompt-chip" onClick={() => onPrompt(p.text)}>
            <span className="prompt-main">{p.text}</span>
            <span className="prompt-desc">{p.desc}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Autonomous multi-agent message ─────────────────────────────────────────

function AutonomousPhase({ phase }) {
  const meta = AGENT_META[phase.agent]
  return (
    <div className={`auto-phase auto-phase-${phase.status}`}>
      <div className="auto-phase-header">
        <span className="auto-phase-icon">
          {phase.status === 'done'    && <CheckIcon />}
          {phase.status === 'active'  && <SpinnerIcon />}
          {phase.status === 'pending' && <span className="step-dot-sm" />}
        </span>
        <span className="auto-phase-label" style={{ color: meta?.color }}>{meta?.label}</span>
        {phase.status === 'done' && phase.count > 0 && (
          <span className="auto-phase-count" style={{ borderColor: meta?.color + '60', color: meta?.color }}>
            {phase.count} processed
          </span>
        )}
      </div>
      {phase.steps.map((s, i) => (
        <div key={i} className="auto-step-line">{s}</div>
      ))}
      {phase.result && (
        <div className={`auto-phase-result${phase.count === 0 ? ' muted' : ''}`}>{phase.result}</div>
      )}
    </div>
  )
}

function AutonomousMessage({ msg }) {
  return (
    <div className="msg-ai">
      <div className="ai-avatar"><CILogo size={20} /></div>
      <div className="ai-body">
        <div className="ai-agent-tag auto-run-tag">Autonomous Run — All Agents</div>
        <div className="auto-phases">
          {msg.phases.map((p, i) => <AutonomousPhase key={i} phase={p} />)}
        </div>
        {msg.summary && (
          <div className="ai-reply with-divider">
            <ReplyText text={msg.summary} />
          </div>
        )}
        {!msg.done && !msg.summary && <span className="cursor-blink" />}
      </div>
    </div>
  )
}

// ── Dashboard view ─────────────────────────────────────────────────────────

function StatusPill({ status, map }) {
  const s = map[status] || { bg: '#f2f0eb', color: '#7a6a55', label: status }
  return (
    <span className="status-pill" style={{ background: s.bg, color: s.color }}>
      {s.label || status}
    </span>
  )
}

// ── Patient detail drawer ──────────────────────────────────────────────────

function PatientDrawer({ patient, data, onClose }) {
  if (!patient) return null

  const payers     = data?.payers     || []
  const appts      = data?.appointments || []
  const encounters = data?.encounters || []
  const claims     = data?.claims     || []

  const payerMap = Object.fromEntries(payers.map(p => [p.id, p]))
  const payer    = payerMap[patient.payer_id]

  const patAppts      = appts.filter(a => a.patient_id === patient.id)
  const patEncounters = encounters.filter(e => e.patient_id === patient.id)
  const patClaims     = claims.filter(c => c.patient_id === patient.id)

  const overallStatus = patClaims.some(c => c.status === 'denied')
    ? { label: 'Has Denied Claims', bg: '#fdecea', color: '#b3402f' }
    : patClaims.some(c => c.status === 'appeal_pending_approval')
    ? { label: 'Appeal Pending', bg: '#fef6e4', color: '#b4781e' }
    : patClaims.some(c => c.status === 'submitted' || c.status === 'appealed')
    ? { label: 'Claims Active', bg: '#e8f4ec', color: '#2d7a4a' }
    : { label: 'No Claims', bg: '#f2f0eb', color: '#7a6a55' }

  const totalBilled = patClaims.reduce((s, c) => s + (c.amount || 0), 0)

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">

        {/* ── Header ── */}
        <div className="pd-header">
          <div className="pd-banner" />
          <button className="drawer-close pd-close-btn" onClick={onClose}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
          <div className="pd-identity">
            <div className="pd-avatar">{initials(patient.name)}</div>
            <div className="pd-name-block">
              <div className="pd-name">{patient.name}</div>
              <div className="pd-sub">{payer?.name || patient.payer_id} · {patient.phone}</div>
              <div className="pd-badges">
                <span className="status-pill" style={{ background: overallStatus.bg, color: overallStatus.color }}>
                  {overallStatus.label}
                </span>
                {patient.is_new_patient && (
                  <span className="status-pill" style={{ background: '#e8f0fe', color: '#3a5f8a' }}>
                    New Patient
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="drawer-body">

          {/* ── KPI strip ── */}
          <div className="pd-kpi-row">
            <div className="pd-kpi">
              <span className="pd-kpi-n">{patAppts.length}</span>
              <span className="pd-kpi-l">Appointments</span>
            </div>
            <div className="pd-kpi-divider" />
            <div className="pd-kpi">
              <span className="pd-kpi-n">{patEncounters.length}</span>
              <span className="pd-kpi-l">Encounters</span>
            </div>
            <div className="pd-kpi-divider" />
            <div className="pd-kpi">
              <span className="pd-kpi-n">{patClaims.length}</span>
              <span className="pd-kpi-l">Claims</span>
            </div>
            <div className="pd-kpi-divider" />
            <div className="pd-kpi">
              <span className="pd-kpi-n">${totalBilled.toLocaleString()}</span>
              <span className="pd-kpi-l">Total Billed</span>
            </div>
          </div>

          {/* ── Appointments ── */}
          <div className="pd-section">
            <div className="pd-section-hd">
              <span className="pd-section-title">Appointments</span>
              <span className="pd-section-count">{patAppts.length}</span>
            </div>
            {patAppts.length === 0
              ? <p className="drawer-empty">No appointments on file.</p>
              : patAppts.map(a => {
                const s = APPT_STATUS_STYLE[a.status] || { bg: '#f2f0eb', color: '#7a6a55' }
                return (
                  <div key={a.id} className="pd-card">
                    <div className="pd-card-top">
                      <span className="pd-card-title">{a.provider}</span>
                      <span className="status-pill" style={{ background: s.bg, color: s.color }}>
                        {a.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="pd-card-meta">
                      {a.date?.slice(0, 16).replace('T', '  ·  ')}
                    </div>
                  </div>
                )
              })
            }
          </div>

          {/* ── Encounters ── */}
          <div className="pd-section">
            <div className="pd-section-hd">
              <span className="pd-section-title">Encounters</span>
              <span className="pd-section-count">{patEncounters.length}</span>
            </div>
            {patEncounters.length === 0
              ? <p className="drawer-empty">No encounters recorded.</p>
              : patEncounters.map(e => (
                <div key={e.id} className="pd-card">
                  <div className="pd-card-top">
                    <span className="pd-card-title">{e.chief_complaint}</span>
                    <span className="pd-card-date">{e.date}</span>
                  </div>
                  <div className="pd-card-meta">
                    {e.provider}
                    <span className="pd-dot" />
                    <span style={{ textTransform: 'capitalize' }}>{e.visit_type?.replace(/_/g, ' ')}</span>
                  </div>
                  {e.diagnoses?.length > 0 && (
                    <div className="drawer-tags" style={{ marginTop: 8 }}>
                      {e.diagnoses.map((d, i) => <span key={i} className="drawer-tag">{d}</span>)}
                    </div>
                  )}
                </div>
              ))
            }
          </div>

          {/* ── Claims ── */}
          <div className="pd-section">
            <div className="pd-section-hd">
              <span className="pd-section-title">Claims</span>
              <span className="pd-section-count">{patClaims.length}</span>
            </div>
            {patClaims.length === 0
              ? <p className="drawer-empty">No claims submitted.</p>
              : patClaims.map(c => {
                const s = CLAIM_STATUS_STYLE[c.status] || { bg: '#f2f0eb', color: '#7a6a55', label: c.status }
                return (
                  <div key={c.id} className="pd-card">
                    <div className="pd-card-top">
                      <span className="pd-card-title pd-amount">${(c.amount || 0).toLocaleString()}</span>
                      <span className="status-pill" style={{ background: s.bg, color: s.color }}>{s.label}</span>
                    </div>
                    <div className="pd-card-meta pd-claim-id">{c.id}</div>
                    {c.denial_code && (
                      <div className="pd-denial">
                        <span className="pd-denial-label">Denial Code</span>
                        <span className="pd-denial-code">{c.denial_code}</span>
                      </div>
                    )}
                    <div className="drawer-tags" style={{ marginTop: 8 }}>
                      {(c.icd10_codes || []).map(code => (
                        <span key={code} className="code-tag icd">{code}</span>
                      ))}
                      {(c.cpt_codes || []).map(code => (
                        <span key={code} className="code-tag cpt">{code}</span>
                      ))}
                    </div>
                  </div>
                )
              })
            }
          </div>

        </div>
      </div>
    </>
  )
}

// ── Pagination helpers ─────────────────────────────────────────────────────

function buildPageList(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  if (current <= 4)        return [1, 2, 3, 4, 5, '…', total]
  if (current >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '…', current - 1, current, current + 1, '…', total]
}

function TablePagination({ total, page, pageSize, onPage, onPageSize, noun }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const safePage   = Math.min(page, totalPages)
  const start      = total === 0 ? 0 : (safePage - 1) * pageSize + 1
  const end        = Math.min(safePage * pageSize, total)
  const pages      = buildPageList(safePage, totalPages)

  return (
    <div className="table-footer">
      <span className="table-footer-info">
        Showing {start.toLocaleString()} to {end.toLocaleString()} of {total.toLocaleString()} {noun}
      </span>
      <div className="table-footer-right">
        <div className="table-pagination">
          <button className="page-btn page-btn-text" disabled={safePage === 1}
            onClick={() => onPage(safePage - 1)}>
            ← Prev
          </button>
          {pages.map((p, i) =>
            p === '…'
              ? <span key={`gap-${i}`} className="page-gap">…</span>
              : <button key={p}
                  className={`page-btn${p === safePage ? ' active' : ''}`}
                  onClick={() => onPage(p)}>
                  {p}
                </button>
          )}
          <button className="page-btn page-btn-text" disabled={safePage === totalPages}
            onClick={() => onPage(safePage + 1)}>
            Next →
          </button>
        </div>
        <select className="page-size-select" value={pageSize}
          onChange={e => { onPageSize(Number(e.target.value)); onPage(1) }}>
          <option value={25}>25 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
          <option value={250}>250 / page</option>
        </select>
      </div>
    </div>
  )
}

// ── Dashboard view ─────────────────────────────────────────────────────────

function DashboardView({ data, approvals, outcomes, onApprove, onDismiss }) {
  const [activeSection, setActiveSection] = useState('approvals')
  const [selectedPatient, setSelectedPatient] = useState(null)

  // Filter + sort state
  const [patientSearch,   setPatientSearch]   = useState('')
  const [patientPayer,    setPatientPayer]    = useState('')
  const [patientSort,     setPatientSort]     = useState('name')
  const [patientPage,     setPatientPage]     = useState(1)
  const [patientPageSize, setPatientPageSize] = useState(50)
  const [claimStatus,     setClaimStatus]     = useState('')
  const [claimPayer,      setClaimPayer]      = useState('')
  const [claimSort,       setClaimSort]       = useState('amount_desc')
  const [claimPage,       setClaimPage]       = useState(1)
  const [claimPageSize,   setClaimPageSize]   = useState(50)
  const [payerSort,       setPayerSort]       = useState('denial_desc')

  if (!data) return (
    <div className="dashboard-skeleton">
      <div className="skel-strip">
        {[1,2,3,4,5,6].map(i => <div key={i} className="skel-stat" />)}
      </div>
      <div className="skel-body">
        {[1,2,3,4,5].map(i => <div key={i} className="skel-row" />)}
      </div>
    </div>
  )

  const patients   = data?.patients   || []
  const claims     = data?.claims     || []
  const appts      = data?.appointments || []
  const payers     = data?.payers     || []
  const encounters = data?.encounters || []

  const patientMap = Object.fromEntries(patients.map(p => [p.id, p]))
  const payerMap   = Object.fromEntries(payers.map(p => [p.id, p]))

  const sections = [
    { key: 'approvals', label: 'Approvals', count: approvals.length },
    { key: 'patients',  label: 'Patients',  count: patients.length  },
    { key: 'claims',    label: 'Claims',    count: claims.length    },
    { key: 'payers',    label: 'Payers',    count: payers.length    },
    { key: 'charts',    label: 'Analytics', count: 0                },
  ]

  // ── Chart data ──────────────────────────────────────────────────────────
  const STATUS_COLORS = {
    submitted: '#5b8fd4',
    denied:    '#c0392b',
    appealed:  '#8a5c9a',
    appeal_pending_approval: '#e67e22',
    draft:     '#aaa',
  }
  const STATUS_LABELS = {
    submitted: 'Submitted',
    denied:    'Denied',
    appealed:  'Appealed',
    appeal_pending_approval: 'Pending Approval',
    draft:     'Draft',
  }

  const claimStatusData = Object.entries(
    claims.reduce((acc, c) => {
      acc[c.status] = (acc[c.status] || 0) + 1
      return acc
    }, {})
  ).map(([status, count]) => ({
    name:  STATUS_LABELS[status] || status,
    value: count,
    color: STATUS_COLORS[status] || '#ccc',
  }))

  // Payer denial rate
  const payerDenialData = payers.map(payer => {
    const payerClaims = claims.filter(c => c.payer_id === payer.id)
    const denied      = payerClaims.filter(c => c.status === 'denied' || c.status === 'appealed').length
    const rate        = payerClaims.length ? Math.round((denied / payerClaims.length) * 100) : 0
    return { name: payer.name.replace('Blue Cross Blue Shield', 'BCBS'), total: payerClaims.length, denied, rate }
  }).filter(p => p.total > 0).sort((a, b) => b.rate - a.rate)

  // Revenue by payer: billed vs recovered
  const revenueData = payers.map(payer => {
    const payerClaims = claims.filter(c => c.payer_id === payer.id)
    const billed      = payerClaims.reduce((s, c) => s + (c.amount || 0), 0)
    const recovered   = payerClaims
      .filter(c => ['submitted', 'approved', 'paid'].includes(c.status))
      .reduce((s, c) => s + (c.paid_amount || (c.charges - c.balance) || c.amount * 0.75 || 0), 0)
    return { name: payer.name.replace('Blue Cross Blue Shield', 'BCBS'), billed: Math.round(billed), recovered: Math.round(recovered) }
  }).filter(p => p.billed > 0)

  return (
    <div className="dashboard">
      {/* Stat strip */}
      <div className="dash-stat-strip">
        <div className="dash-stat">
          <span className="dash-stat-n">{outcomes.appointments_recovered}</span>
          <span className="dash-stat-l">Appointments Recovered</span>
        </div>
        <div className="dash-divider" />
        <div className="dash-stat">
          <span className="dash-stat-n">
            ${Number(outcomes.revenue_recovered).toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
          <span className="dash-stat-l">Revenue Recovered</span>
        </div>
        <div className="dash-divider" />
        <div className="dash-stat">
          <span className="dash-stat-n">{outcomes.denials_overturned}</span>
          <span className="dash-stat-l">Denials Overturned</span>
        </div>
        <div className="dash-divider" />
        <div className="dash-stat">
          <span className="dash-stat-n">{Number(outcomes.hours_saved).toFixed(1)}h</span>
          <span className="dash-stat-l">Staff Hours Saved</span>
        </div>
        <div className="dash-divider" />
        <div className="dash-stat">
          <span className="dash-stat-n">{claims.filter(c => c.status === 'denied').length}</span>
          <span className="dash-stat-l">Open Denials</span>
        </div>
        <div className="dash-divider" />
        <div className="dash-stat">
          <span className="dash-stat-n">{appts.filter(a => a.status === 'booked').length}</span>
          <span className="dash-stat-l">Upcoming Appointments</span>
        </div>
      </div>

      {/* Section tabs */}
      <div className="dash-tabs">
        {sections.map(s => (
          <button
            key={s.key}
            className={`dash-tab${activeSection === s.key ? ' active' : ''}`}
            onClick={() => setActiveSection(s.key)}
          >
            {s.label}
            {s.count > 0 && (
              <span className={`tab-count${activeSection === s.key ? ' active' : ''}`}>
                {s.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Section content */}
      <div className="dash-content">

        {/* Analytics / Charts */}
        {activeSection === 'charts' && (
          <div className="dash-section charts-section">

            <div className="charts-row">
              {/* Claim Status Donut */}
              <div className="chart-card">
                <div className="chart-card-title">Claim Status Breakdown</div>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={claimStatusData}
                      cx="50%" cy="50%"
                      innerRadius={60} outerRadius={90}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {claimStatusData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v, n) => [v + ' claims', n]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="chart-legend">
                  {claimStatusData.map((d, i) => (
                    <span key={i} className="legend-item">
                      <span className="legend-dot" style={{ background: d.color }} />
                      {d.name} ({d.value})
                    </span>
                  ))}
                </div>
              </div>

              {/* Payer Denial Rate */}
              <div className="chart-card">
                <div className="chart-card-title">Denial Rate by Payer</div>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={payerDenialData} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e4dccf" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#9b8b72' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#9b8b72' }} allowDecimals={false} />
                    <Tooltip formatter={(v, n) => [v + ' claims', n]} />
                    <Legend wrapperStyle={{ fontSize: 12, color: '#9b8b72' }} />
                    <Bar dataKey="total"  name="Total"  fill="#5b8fd4" radius={[4,4,0,0]} />
                    <Bar dataKey="denied" name="Denied" fill="#c0392b" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Revenue Billed vs Recovered */}
            <div className="chart-card chart-card-wide">
              <div className="chart-card-title">Revenue: Billed vs Recovered by Payer</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={revenueData} margin={{ top: 8, right: 20, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e4dccf" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#9b8b72' }} />
                  <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: '#9b8b72' }} />
                  <Tooltip formatter={v => [`$${Number(v).toLocaleString()}`, '']} />
                  <Legend wrapperStyle={{ fontSize: 12, color: '#9b8b72' }} />
                  <Bar dataKey="billed"    name="Billed"    fill="#5b8fd4" radius={[4,4,0,0]} />
                  <Bar dataKey="recovered" name="Recovered" fill="#3a7a5a" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

          </div>
        )}

        {/* Approvals */}
        {activeSection === 'approvals' && (
          <div className="dash-section">
            {approvals.length === 0 ? (
              <div className="dash-empty">
                <span className="dash-empty-icon">✓</span>
                <p>All clear — no items awaiting approval.</p>
              </div>
            ) : (
              <div className="approval-list">
                {approvals.map(a => (
                  <div key={a.id} className="approval-card">
                    <div className="approval-card-header">
                      <span className={`approval-type-badge ${a.type}`}>
                        {a.type === 'appeal_resubmission' ? 'Appeal Resubmission' : 'Unclear Request'}
                      </span>
                      <button className="btn-ghost" onClick={() => onDismiss(a.id)}>Dismiss</button>
                    </div>

                    {a.type === 'appeal_resubmission' && (
                      <>
                        <div className="approval-meta">
                          <span className="meta-label">Claim</span>
                          <span className="meta-val">{a.claim_id}</span>
                          {a.diagnosis && (
                            <>
                              <span className="meta-label">Denial Code</span>
                              <span className="meta-val">{a.diagnosis.denial_code}</span>
                              <span className="meta-label">Root Cause</span>
                              <span className="meta-val">{a.diagnosis.root_cause}</span>
                            </>
                          )}
                        </div>
                        {a.appeal_letter && (
                          <div className="appeal-letter">
                            <div className="appeal-letter-label">Appeal Letter</div>
                            <p className="appeal-letter-text">{a.appeal_letter}</p>
                          </div>
                        )}
                        <div className="approval-actions">
                          <button className="btn-approve" onClick={() => onApprove(a.claim_id)}>
                            Approve &amp; Resubmit
                          </button>
                        </div>
                      </>
                    )}

                    {a.type === 'unclear_request' && (
                      <div className="approval-request-text">
                        "{a.request_text}"
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Patients */}
        {activeSection === 'patients' && (() => {
          const filteredPatients = patients
            .filter(p => {
              const q = patientSearch.toLowerCase()
              const matchSearch = !q || p.name?.toLowerCase().includes(q) || p.id?.toLowerCase().includes(q)
              const matchPayer  = !patientPayer || p.payer_id === patientPayer
              return matchSearch && matchPayer
            })
            .sort((a, b) => {
              const aClaims = claims.filter(c => c.patient_id === a.id)
              const bClaims = claims.filter(c => c.patient_id === b.id)
              if (patientSort === 'name')        return (a.name||'').localeCompare(b.name||'')
              if (patientSort === 'name_desc')   return (b.name||'').localeCompare(a.name||'')
              if (patientSort === 'claims_desc') return bClaims.length - aClaims.length
              if (patientSort === 'denied') {
                const aD = aClaims.some(c => c.status === 'denied') ? 0 : 1
                const bD = bClaims.some(c => c.status === 'denied') ? 0 : 1
                return aD - bD
              }
              return 0
            })

          const safePage = Math.min(patientPage, Math.max(1, Math.ceil(filteredPatients.length / patientPageSize)))
          const start    = (safePage - 1) * patientPageSize
          const pageRows = filteredPatients.slice(start, start + patientPageSize)

          return (
            <div className="dash-section">
              <div className="filter-bar">
                <input className="filter-input" placeholder="Search name or ID…" value={patientSearch}
                  onChange={e => { setPatientSearch(e.target.value); setPatientPage(1) }} />
                <select className="filter-select" value={patientPayer}
                  onChange={e => { setPatientPayer(e.target.value); setPatientPage(1) }}>
                  <option value="">All Payers</option>
                  {payers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <select className="filter-select" value={patientSort}
                  onChange={e => { setPatientSort(e.target.value); setPatientPage(1) }}>
                  <option value="name">Sort: Name A–Z</option>
                  <option value="name_desc">Sort: Name Z–A</option>
                  <option value="claims_desc">Sort: Most Claims</option>
                  <option value="denied">Sort: Has Denials First</option>
                </select>
                <span className="table-hint" style={{ marginLeft: 'auto', marginBottom: 0 }}>Click any row to view details</span>
              </div>
              <div className="table-card">
                <table className="data-table">
                  <colgroup>
                    <col style={{ width: '26%' }} />
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '13%' }} />
                    <col style={{ width: '17%' }} />
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '13%' }} />
                    <col style={{ width: '11%' }} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Patient</th>
                      <th>DOB</th>
                      <th>Phone</th>
                      <th>Insurance</th>
                      <th>Status</th>
                      <th>Appt Type</th>
                      <th>Claim Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map(p => {
                      const payer    = payerMap[p.payer_id]
                      const patAppt  = appts.find(a => a.patient_id === p.id)
                      const patClaim = claims.find(c => c.patient_id === p.id)
                      const isDenied = patClaim?.status === 'denied'
                      const claimStyle = isDenied
                        ? { background: '#fee2e2', color: '#dc2626' }
                        : patClaim?.status === 'submitted' || patClaim?.status === 'appealed'
                          ? { background: '#e8f4ec', color: '#16a34a' }
                          : { background: '#f2f0eb', color: '#7a6a55' }
                      return (
                        <tr key={p.id} className="row-clickable" onClick={() => setSelectedPatient(p)}>
                          <td>
                            <div className="patient-cell">
                              <div className="avatar-sm">{initials(p.name)}</div>
                              <div className="patient-info">
                                <div className="patient-name">{p.name}</div>
                                <div className="patient-id">{p.id}</div>
                              </div>
                            </div>
                          </td>
                          <td className="td-mono">{p.dob}</td>
                          <td className="td-mono">{p.phone}</td>
                          <td>{payer?.name || p.payer_id}</td>
                          <td>
                            {p.is_new_patient
                              ? <span className="status-pill" style={{ background: '#e8f0fe', color: '#3a5f8a' }}>New</span>
                              : <span className="status-pill" style={{ background: '#f2f0eb', color: '#7a6a55' }}>Returning</span>
                            }
                          </td>
                          <td className="td-mono">{patAppt?.type || '—'}</td>
                          <td>
                            {patClaim
                              ? <span className="status-pill" style={claimStyle}>{patClaim.status}</span>
                              : <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>—</span>
                            }
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <TablePagination
                  total={filteredPatients.length}
                  page={safePage}
                  pageSize={patientPageSize}
                  onPage={setPatientPage}
                  onPageSize={setPatientPageSize}
                  noun="patients"
                />
              </div>
            </div>
          )
        })()}

        {/* Patient detail drawer */}
        <PatientDrawer
          patient={selectedPatient}
          data={data}
          onClose={() => setSelectedPatient(null)}
        />

        {/* Claims */}
        {activeSection === 'claims' && (() => {
          const filteredClaims = claims
            .filter(c => {
              const matchStatus = !claimStatus || c.status === claimStatus
              const matchPayer  = !claimPayer  || c.payer_id === claimPayer
              return matchStatus && matchPayer
            })
            .sort((a, b) => {
              const pA = patientMap[a.patient_id]
              const pB = patientMap[b.patient_id]
              if (claimSort === 'amount_desc') return (b.amount||0) - (a.amount||0)
              if (claimSort === 'amount_asc')  return (a.amount||0) - (b.amount||0)
              if (claimSort === 'status')      return (a.status||'').localeCompare(b.status||'')
              if (claimSort === 'patient')     return (pA?.name||'').localeCompare(pB?.name||'')
              return 0
            })

          const safePage = Math.min(claimPage, Math.max(1, Math.ceil(filteredClaims.length / claimPageSize)))
          const start    = (safePage - 1) * claimPageSize
          const pageRows = filteredClaims.slice(start, start + claimPageSize)

          return (
            <div className="dash-section">
              <div className="filter-bar">
                <select className="filter-select" value={claimStatus}
                  onChange={e => { setClaimStatus(e.target.value); setClaimPage(1) }}>
                  <option value="">All Statuses</option>
                  <option value="denied">Denied</option>
                  <option value="appealed">Appealed</option>
                  <option value="submitted">Submitted</option>
                  <option value="approved">Approved</option>
                  <option value="draft">Draft</option>
                </select>
                <select className="filter-select" value={claimPayer}
                  onChange={e => { setClaimPayer(e.target.value); setClaimPage(1) }}>
                  <option value="">All Payers</option>
                  {payers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <select className="filter-select" value={claimSort}
                  onChange={e => { setClaimSort(e.target.value); setClaimPage(1) }}>
                  <option value="amount_desc">Sort: Highest Amount</option>
                  <option value="amount_asc">Sort: Lowest Amount</option>
                  <option value="status">Sort: Status</option>
                  <option value="patient">Sort: Patient Name</option>
                </select>
              </div>
              <div className="table-card">
                <table className="data-table">
                  <colgroup>
                    <col style={{ width: '12%' }} />
                    <col style={{ width: '22%' }} />
                    <col style={{ width: '18%' }} />
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '12%' }} />
                    <col style={{ width: '26%' }} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Claim ID</th>
                      <th>Patient</th>
                      <th>Payer</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th>Denial Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map(c => {
                      const patient = patientMap[c.patient_id]
                      const payer   = payerMap[c.payer_id] || payerMap[patient?.payer_id]
                      return (
                        <tr key={c.id}>
                          <td className="td-mono td-dim">{c.id}</td>
                          <td>
                            <div className="patient-cell">
                              <div className="avatar-sm">{initials(patient?.name)}</div>
                              <span className="patient-name">{patient?.name || c.patient_id}</span>
                            </div>
                          </td>
                          <td>{payer?.name || c.payer_id || '—'}</td>
                          <td className="td-mono">${Number(c.amount || 0).toLocaleString()}</td>
                          <td><StatusPill status={c.status} map={CLAIM_STATUS_STYLE} /></td>
                          <td className="td-mono td-dim">{c.denial_reason || '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <TablePagination
                  total={filteredClaims.length}
                  page={safePage}
                  pageSize={claimPageSize}
                  onPage={setClaimPage}
                  onPageSize={setClaimPageSize}
                  noun="claims"
                />
              </div>
            </div>
          )
        })()}

        {/* Payers */}
        {activeSection === 'payers' && (
          <div className="dash-section">
            <div className="filter-bar">
              <select className="filter-select" value={payerSort} onChange={e => setPayerSort(e.target.value)}>
                <option value="denial_desc">Sort: Highest Denial Rate</option>
                <option value="denial_asc">Sort: Lowest Denial Rate</option>
                <option value="claims_desc">Sort: Most Claims</option>
                <option value="name">Sort: Name A–Z</option>
              </select>
            </div>
          <div className="payers-grid">
            {payers
              .map(p => {
                const payerClaims  = claims.filter(c => c.payer_id === p.id)
                const deniedClaims = payerClaims.filter(c => c.status === 'denied' || c.status === 'appealed')
                const rate = payerClaims.length ? deniedClaims.length / payerClaims.length : 0
                return { ...p, _rate: rate, _total: payerClaims.length, _denied: deniedClaims.length }
              })
              .sort((a, b) => {
                if (payerSort === 'denial_desc')  return b._rate - a._rate
                if (payerSort === 'denial_asc')   return a._rate - b._rate
                if (payerSort === 'claims_desc')  return b._total - a._total
                if (payerSort === 'name')         return a.name.localeCompare(b.name)
                return 0
              })
              .map(p => {
            const rate         = p._rate || 0
            const ratePct      = (rate * 100).toFixed(1)
            const rateColor    = rate > 0.20 ? '#b3402f' : rate > 0.10 ? '#b4781e' : '#2d7a4a'
            const deniedClaims = claims.filter(c => c.payer_id === p.id && (c.status === 'denied' || c.status === 'appealed'))

            const reasonCounts = {}
            deniedClaims.forEach(c => {
              const reason = c.denial_reason || 'Unknown'
              reasonCounts[reason] = (reasonCounts[reason] || 0) + 1
            })
            const topReasons = Object.entries(reasonCounts)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 3)

            return (
              <div key={p.id} className="payer-card">
                <div className="payer-header">
                  <span className="payer-name">{p.name}</span>
                  <span className="payer-rate" style={{ color: rateColor }}>
                    {ratePct}% denial rate
                  </span>
                </div>
                <div className="payer-rate-bar">
                  <div
                    className="payer-rate-fill"
                    style={{ width: `${Math.min(rate * 100 / 30 * 100, 100)}%`, background: rateColor + 'cc' }}
                  />
                </div>
                <div style={{ fontSize: 11, color: '#9b8b72', marginTop: 6, marginBottom: 10 }}>
                  {p._denied} denied · {p._total} total claims
                </div>
                {topReasons.length > 0 && (
                  <>
                    <div className="payer-section-label">Common Denial Reasons</div>
                    {topReasons.map(([reason, count]) => (
                      <div key={reason} className="denial-reason">
                        <span className="denial-code">{count}×</span>
                        <span className="denial-desc">{reason}</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )
          })}
          </div>
          </div>
        )}

      </div>
    </div>
  )
}

// ── Agents view ───────────────────────────────────────────────────────────

function ActionResult({ result, error }) {
  if (!result && !error) return null
  if (error) return <div className="action-result error">{error}</div>
  const msg = result.feed_message || result.message || result.reply ||
    (result.recovered ? `${result.recovered.length} no-shows recovered` : null) ||
    (result.processed != null ? `${result.processed} encounters processed` : null) ||
    JSON.stringify(result).slice(0, 120)
  const isOk = result.action !== 'error'
  return <div className={`action-result ${isOk ? 'ok' : 'error'}`}>{msg}</div>
}

function AgentCard({ color, icon, label, description, status, currentTask, lastActivity, onOpen }) {
  const statusConfig = {
    monitoring: { label: 'Monitoring', cls: 'status-monitoring' },
    ready:      { label: 'Ready',      cls: 'status-ready'      },
    active:     { label: 'Active',     cls: 'status-active'     },
    idle:       { label: 'Idle',       cls: 'status-idle'       },
    processing: { label: 'Processing', cls: 'status-processing' },
  }
  const sc = statusConfig[status] || statusConfig.idle
  return (
    <div className="ac-card" style={{ '--ac-color': color }}>
      <div className="ac-top">
        <div className="ac-icon">{icon}</div>
        <div className="ac-title-group">
          <div className="ac-name">{label}</div>
          <span className={`ac-status ${sc.cls}`}>{sc.label}</span>
        </div>
      </div>
      <p className="ac-desc">{description}</p>
      <div className="ac-meta">
        <div className="ac-meta-row">
          <span className="ac-meta-label">Current Task</span>
          <span className="ac-meta-val">{currentTask}</span>
        </div>
        <div className="ac-meta-row">
          <span className="ac-meta-label">Last Activity</span>
          <span className="ac-meta-val">{lastActivity}</span>
        </div>
      </div>
      <button className="ac-btn" onClick={onOpen}>Open Agent</button>
    </div>
  )
}

function AgentDrawer({ agent, onClose, children }) {
  if (!agent) return null
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer" style={{ '--ac-color': agent.color }}>
        <div className="drawer-header">
          <div className="drawer-icon">{agent.icon}</div>
          <div style={{ flex: 1 }}>
            <div className="drawer-title">{agent.label}</div>
            <div className="drawer-desc">{agent.description}</div>
          </div>
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </>
  )
}

function AgentsView({ data, onRefresh }) {
  const patients   = data?.patients   || []
  const appts      = data?.appointments || []
  const encounters = data?.encounters || []
  const claims     = data?.claims     || []

  const bookedAppts   = appts.filter(a => a.status === 'booked')
  const noShowAppts   = appts.filter(a => a.status === 'no_show')
  const claimedEncIds = new Set(claims.map(c => c.encounter_id))
  const pendingEncs   = encounters.filter(e => !claimedEncIds.has(e.id))
  const deniedClaims  = claims.filter(c => c.status === 'denied')
  const patientMap    = Object.fromEntries(patients.map(p => [p.id, p]))

  const [openAgent, setOpenAgent] = useState(null)

  // ── Patient Access ──
  const [paForm, setPaForm]     = useState({ patient_id: '', provider: 'Dr. Alvarez', date: '' })
  const [paCancel, setPaCancel] = useState('')
  const [paLoading, setPaLoading] = useState('')
  const [paResult, setPaResult]   = useState({})

  const runPaAction = async (action, body, key) => {
    setPaLoading(key); setPaResult(prev => ({ ...prev, [key]: null }))
    try {
      let url, opts
      if (action === 'schedule') {
        url = '/api/agents/patient-access/schedule'
        opts = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      } else if (action === 'cancel') {
        url = `/api/agents/patient-access/cancel/${body.appointment_id}`
        opts = { method: 'POST' }
      } else {
        url = '/api/agents/patient-access/recover-no-shows'
        opts = { method: 'POST' }
      }
      const r = await fetch(url, opts).then(x => x.json())
      setPaResult(prev => ({ ...prev, [key]: r }))
      onRefresh()
    } catch (e) {
      setPaResult(prev => ({ ...prev, [key]: null, [`${key}_err`]: e.message }))
    }
    setPaLoading('')
  }

  // ── Billing ──
  const [bcEnc, setBcEnc]         = useState('')
  const [bcLoading, setBcLoading] = useState('')
  const [bcResult, setBcResult]   = useState({})

  const runBcAction = async (action, encId) => {
    setBcLoading(action); setBcResult({})
    try {
      if (action === 'all') {
        const results = []
        for (const enc of pendingEncs) {
          const r = await fetch(`/api/agents/billing-coding/${enc.id}`, { method: 'POST' }).then(x => x.json())
          results.push(r)
        }
        setBcResult({ processed: results.length, results })
      } else {
        const r = await fetch(`/api/agents/billing-coding/${encId}`, { method: 'POST' }).then(x => x.json())
        setBcResult(r)
      }
      onRefresh()
    } catch (e) { setBcResult({ action: 'error', message: e.message }) }
    setBcLoading('')
  }

  // ── Denial ──
  const [dmClaim, setDmClaim]     = useState('')
  const [dmLoading, setDmLoading] = useState('')
  const [dmResult, setDmResult]   = useState({})

  const runDmAction = async (action, claimId) => {
    setDmLoading(action); setDmResult({})
    try {
      if (action === 'all') {
        const results = []
        for (const c of deniedClaims) {
          const r = await fetch(`/api/agents/denial-management/diagnose/${c.id}`, { method: 'POST' }).then(x => x.json())
          results.push(r)
        }
        setDmResult({ processed: results.length, results })
      } else {
        const r = await fetch(`/api/agents/denial-management/diagnose/${claimId}`, { method: 'POST' }).then(x => x.json())
        setDmResult(r)
      }
      onRefresh()
    } catch (e) { setDmResult({ action: 'error', message: e.message }) }
    setDmLoading('')
  }

  // ── Prior Auth ──
  const [pauthRequests, setPauthRequests] = useState([])
  const [pauthRunning, setPauthRunning] = useState(false)
  const [pauthRunResult, setPauthRunResult] = useState(null)
  useEffect(() => {
    const load = () => fetch('/api/agents/prior-auth/requests').then(r => r.json()).then(setPauthRequests).catch(() => {})
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const pauthApproved = pauthRequests.filter(r => r.status === 'approved').length
  const pauthDenied   = pauthRequests.filter(r => r.status === 'denied').length

  const AGENTS = [
    {
      key: 'prior_auth', color: '#7c3aed',
      label: 'Prior Authorization Agent',
      description: 'Checks if procedures need insurance approval before appointments proceed.',
      status: pauthRequests.length > 0 ? 'monitoring' : 'ready',
      currentTask: `Monitoring ${bookedAppts.length} booked appointments`,
      lastActivity: pauthRequests.length > 0
        ? `${pauthApproved} approved · ${pauthDenied} denied`
        : 'No auth requests yet',
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 12l2 2 4-4"/><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/></svg>,
    },
    {
      key: 'patient_access', color: '#2563eb',
      label: 'Patient Access Agent',
      description: 'Manages appointments — scheduling, cancellations, and no-show recovery.',
      status: noShowAppts.length > 0 ? 'active' : 'monitoring',
      currentTask: `Monitoring ${bookedAppts.length} scheduled appointments`,
      lastActivity: noShowAppts.length > 0
        ? `${noShowAppts.length} no-show(s) awaiting recovery`
        : 'All appointments up to date',
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 9a3 3 0 1 0 0-6M19.5 20a5.5 5.5 0 0 0-4-5.3"/></svg>,
    },
    {
      key: 'billing', color: '#16a34a',
      label: 'Billing & Coding Agent',
      description: 'Assigns ICD-10 and CPT codes, scrubs claims, and submits clean claims.',
      status: pendingEncs.length > 0 ? 'active' : 'ready',
      currentTask: pendingEncs.length > 0
        ? `${pendingEncs.length} encounter(s) pending coding`
        : 'All encounters processed',
      lastActivity: `${claims.filter(c => c.status === 'submitted').length} claims submitted`,
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M7 3h8l4 4v14H7z"/><path d="M15 3v4h4M9 12h6M9 16h6M9 8h2"/></svg>,
    },
    {
      key: 'denial', color: '#dc2626',
      label: 'Denial Management Agent',
      description: 'Diagnoses denied claims, drafts appeal letters, and queues for resubmission.',
      status: deniedClaims.length > 0 ? 'active' : 'monitoring',
      currentTask: deniedClaims.length > 0
        ? `${deniedClaims.length} denied claim(s) to appeal`
        : 'Monitoring for new denials',
      lastActivity: `${claims.filter(c => c.status === 'appealed').length} appeals submitted`,
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 3 6v6c0 5 3.8 8.7 9 10 5.2-1.3 9-5 9-10V6z"/></svg>,
    },
  ]

  const activeAgent = AGENTS.find(a => a.key === openAgent)

  return (
    <div className="agents-view">
      <div className="agents-grid">
        {AGENTS.map(ag => (
          <AgentCard key={ag.key} {...ag} onOpen={() => setOpenAgent(ag.key)} />
        ))}
      </div>

      <AgentDrawer agent={activeAgent} onClose={() => setOpenAgent(null)}>
        {openAgent === 'prior_auth' && (
          <div className="drawer-section">
            <div className="drawer-section-title">Run Prior Authorization</div>
            <p className="drawer-section-desc">Scans all booked appointments and submits auth requests to payers that require it.</p>
            <button
              className="ac-btn"
              style={{ '--ac-color': '#7c3aed' }}
              disabled={pauthRunning}
              onClick={async () => {
                setPauthRunning(true)
                setPauthRunResult(null)
                setAgentStatus(prev => ({ ...prev, prior_auth: 'working' }))
                try {
                  const r = await fetch('/api/agents/prior-auth/run', { method: 'POST' })
                  const d = await r.json()
                  setPauthRunResult(d)
                  setAgentStatus(prev => ({ ...prev, prior_auth: 'done' }))
                  fetch('/api/agents/prior-auth/requests').then(r => r.json()).then(setPauthRequests)
                } catch(e) {
                  setPauthRunResult({ error: e.message })
                  setAgentStatus(prev => ({ ...prev, prior_auth: 'idle' }))
                } finally {
                  setPauthRunning(false)
                }
              }}
            >
              {pauthRunning ? <><SpinnerIcon /> Running…</> : 'Run Prior Auth'}
            </button>
            {pauthRunResult && (
              <div className={`action-result ${pauthRunResult.error ? 'err' : 'ok'}`}>
                {pauthRunResult.error
                  ? pauthRunResult.error
                  : `Processed ${pauthRunResult.processed ?? 0} authorization request(s)`}
              </div>
            )}

            {pauthRequests.length > 0 && (
              <>
                <div className="drawer-section-title" style={{ marginTop: 20 }}>Authorization Requests ({pauthRequests.length})</div>
                <div className="pauth-list">
                  {pauthRequests.slice(0, 20).map((r, i) => (
                    <div key={i} className={`pauth-item pauth-${r.status}`}>
                      <div className="pauth-top">
                        <span className="pauth-name">{r.patient_name}</span>
                        <span className={`pauth-badge pauth-badge-${r.status}`}>{r.status === 'approved' ? 'Approved' : 'Denied'}</span>
                      </div>
                      <div className="pauth-detail">{r.procedure} · {r.payer}</div>
                      {r.reason && <div className="pauth-reason">{r.reason}</div>}
                    </div>
                  ))}
                </div>
              </>
            )}
            {pauthRequests.length === 0 && !pauthRunning && !pauthRunResult && (
              <p className="drawer-empty" style={{ marginTop: 12 }}>No auth requests yet — click Run Prior Auth to start.</p>
            )}
          </div>
        )}

        {openAgent === 'patient_access' && (
          <>
            <div className="drawer-section">
              <div className="drawer-section-title">Recover No-Show Appointments</div>
              <p className="drawer-section-desc">{noShowAppts.length} no-show(s) in the system</p>
              <button className="ac-btn" style={{ '--ac-color': '#2563eb' }} disabled={paLoading === 'recover'} onClick={() => runPaAction('recover', {}, 'recover')}>
                {paLoading === 'recover' ? <><SpinnerIcon /> Running…</> : 'Run Recovery'}
              </button>
              <ActionResult result={paResult.recover} error={paResult.recover_err} />
            </div>
            <div className="drawer-divider" />
            <div className="drawer-section">
              <div className="drawer-section-title">Schedule Appointment</div>
              <div className="action-form">
                <div className="form-row"><label>Patient</label>
                  <select value={paForm.patient_id} onChange={e => setPaForm(f => ({ ...f, patient_id: e.target.value }))}>
                    <option value="">Select patient…</option>
                    {patients.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div className="form-row"><label>Provider</label>
                  <select value={paForm.provider} onChange={e => setPaForm(f => ({ ...f, provider: e.target.value }))}>
                    <option>Dr. Alvarez</option><option>Dr. Chen</option><option>Dr. Patel</option>
                  </select>
                </div>
                <div className="form-row"><label>Date &amp; Time</label>
                  <input type="datetime-local" value={paForm.date} onChange={e => setPaForm(f => ({ ...f, date: e.target.value }))} />
                </div>
              </div>
              <button className="ac-btn" style={{ '--ac-color': '#2563eb' }} disabled={paLoading === 'schedule' || !paForm.patient_id || !paForm.date}
                onClick={() => runPaAction('schedule', { patient_id: paForm.patient_id, provider: paForm.provider, date_iso: new Date(paForm.date).toISOString() }, 'schedule')}>
                {paLoading === 'schedule' ? <><SpinnerIcon /> Scheduling…</> : 'Schedule'}
              </button>
              <ActionResult result={paResult.schedule} error={paResult.schedule_err} />
            </div>
            <div className="drawer-divider" />
            <div className="drawer-section">
              <div className="drawer-section-title">Cancel Appointment</div>
              <div className="action-form">
                <div className="form-row"><label>Appointment</label>
                  <select value={paCancel} onChange={e => setPaCancel(e.target.value)}>
                    <option value="">Select appointment…</option>
                    {bookedAppts.map(a => (
                      <option key={a.id} value={a.id}>{patientMap[a.patient_id]?.name || a.patient_id} — {a.provider} · {a.date?.slice(0, 10)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button className="ac-btn ac-btn-danger" disabled={paLoading === 'cancel' || !paCancel}
                onClick={() => runPaAction('cancel', { appointment_id: paCancel }, 'cancel')}>
                {paLoading === 'cancel' ? <><SpinnerIcon /> Cancelling…</> : 'Cancel Appointment'}
              </button>
              <ActionResult result={paResult.cancel} error={paResult.cancel_err} />
            </div>
          </>
        )}

        {openAgent === 'billing' && (
          <>
            <div className="drawer-section">
              <div className="drawer-section-title">Process All Pending Encounters</div>
              <p className="drawer-section-desc">{pendingEncs.length} encounter(s) awaiting coding and submission</p>
              <button className="ac-btn" style={{ '--ac-color': '#16a34a' }} disabled={bcLoading === 'all' || pendingEncs.length === 0} onClick={() => runBcAction('all')}>
                {bcLoading === 'all' ? <><SpinnerIcon /> Processing…</> : `Process All (${pendingEncs.length})`}
              </button>
              {bcResult.processed != null && <div className="action-result ok">Processed {bcResult.processed} encounter(s). Claims coded and submitted.</div>}
            </div>
            <div className="drawer-divider" />
            <div className="drawer-section">
              <div className="drawer-section-title">Process Specific Encounter</div>
              <div className="action-form">
                <div className="form-row"><label>Encounter</label>
                  <select value={bcEnc} onChange={e => setBcEnc(e.target.value)}>
                    <option value="">Select encounter…</option>
                    {pendingEncs.map(e => (
                      <option key={e.id} value={e.id}>{patientMap[e.patient_id]?.name || e.patient_id} — {e.chief_complaint} · {e.date}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button className="ac-btn" style={{ '--ac-color': '#16a34a' }} disabled={bcLoading === 'single' || !bcEnc} onClick={() => runBcAction('single', bcEnc)}>
                {bcLoading === 'single' ? <><SpinnerIcon /> Coding…</> : 'Code & Submit'}
              </button>
              {bcResult.feed_message && bcResult.processed == null && <ActionResult result={bcResult} />}
            </div>
          </>
        )}

        {openAgent === 'denial' && (
          <>
            <div className="drawer-section">
              <div className="drawer-section-title">Draft Appeals for All Denied Claims</div>
              <p className="drawer-section-desc">{deniedClaims.length} denied claim(s) — will queue appeals for review</p>
              <button className="ac-btn" style={{ '--ac-color': '#dc2626' }} disabled={dmLoading === 'all' || deniedClaims.length === 0} onClick={() => runDmAction('all')}>
                {dmLoading === 'all' ? <><SpinnerIcon /> Diagnosing…</> : `Draft Appeals for All (${deniedClaims.length})`}
              </button>
              {dmResult.processed != null && <div className="action-result ok">Drafted {dmResult.processed} appeal(s). Review in Dashboard → Approvals.</div>}
            </div>
            <div className="drawer-divider" />
            <div className="drawer-section">
              <div className="drawer-section-title">Diagnose Specific Claim</div>
              <div className="action-form">
                <div className="form-row"><label>Denied Claim</label>
                  <select value={dmClaim} onChange={e => setDmClaim(e.target.value)}>
                    <option value="">Select claim…</option>
                    {deniedClaims.map(c => (
                      <option key={c.id} value={c.id}>{patientMap[c.patient_id]?.name || c.patient_id} — {c.id} · ${c.amount}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button className="ac-btn" style={{ '--ac-color': '#dc2626' }} disabled={dmLoading === 'single' || !dmClaim} onClick={() => runDmAction('single', dmClaim)}>
                {dmLoading === 'single' ? <><SpinnerIcon /> Drafting…</> : 'Diagnose & Draft Appeal'}
              </button>
              {dmResult.feed_message && dmResult.processed == null && <ActionResult result={dmResult} />}
            </div>
            <div className="drawer-divider" />
            <div className="drawer-section">
              <div className="drawer-section-title">Email Denial Report</div>
              <p className="drawer-section-desc">Send top 3 denied claims report to your inbox now.</p>
              <button className="ac-btn" style={{ '--ac-color': '#dc2626' }} disabled={dmLoading === 'report'}
                onClick={async () => {
                  setDmLoading('report')
                  try {
                    const r = await fetch('/api/agents/denial-management/send-report', { method: 'POST' })
                    const d = await r.json()
                    setDmResult({ feed_message: `Report sent — ${d.scanned} claims scanned, top 3 emailed to your inbox.` })
                  } catch(e) {
                    setDmResult({ feed_message: 'Failed to send report.' })
                  } finally {
                    setDmLoading(null)
                  }
                }}>
                {dmLoading === 'report' ? <><SpinnerIcon /> Sending…</> : 'Send Report Now'}
              </button>
              {dmLoading !== 'report' && dmResult.feed_message?.includes('Report sent') && <div className="action-result ok">{dmResult.feed_message}</div>}
            </div>
          </>
        )}
      </AgentDrawer>
    </div>
  )
}

// ── Sidebar ────────────────────────────────────────────────────────────────

function Sidebar({ outcomes, feed, approvals, agentStatus }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <CILogo size={22} />
          <span className="brand-name">Care Intelligence</span>
        </div>
      </div>

      <div className="sidebar-block">
        <div className="block-label">Outcomes</div>
        <div className="stats-grid">
          <div className="stat-cell">
            <span className="stat-num">{outcomes.appointments_recovered}</span>
            <span className="stat-lbl">Recovered</span>
          </div>
          <div className="stat-cell">
            <span className="stat-num">
              ${Number(outcomes.revenue_recovered).toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </span>
            <span className="stat-lbl">Revenue</span>
          </div>
          <div className="stat-cell">
            <span className="stat-num">{outcomes.denials_overturned}</span>
            <span className="stat-lbl">Denials Won</span>
          </div>
          <div className="stat-cell">
            <span className="stat-num">{Number(outcomes.hours_saved).toFixed(1)}h</span>
            <span className="stat-lbl">Hours Saved</span>
          </div>
        </div>
      </div>

      <div className="sidebar-block">
        <div className="block-label">
          Agent Workforce
          {approvals.length > 0 && (
            <span className="review-badge">{approvals.length} pending</span>
          )}
        </div>
        {[
          { key: 'patient_access',    label: 'Patient Access',    agentColor: '#2563eb' },
          { key: 'billing_coding',    label: 'Billing & Coding',  agentColor: '#16a34a' },
          { key: 'denial_management', label: 'Denial Management', agentColor: '#dc2626' },
          { key: 'prior_auth',        label: 'Prior Auth',        agentColor: '#7c3aed' },
        ].map(({ key, label, agentColor }) => {
          const s = agentStatus[key] || 'idle'
          return (
            <div key={key} className="agent-row" style={{ '--ag-color': agentColor }}>
              <span className={`agent-dot${s === 'working' ? ' pulsing' : ''}`}
                style={{ background: agentColor, opacity: s === 'idle' ? 0.4 : 1 }} />
              <span className="agent-name">{label}</span>
              <span className="agent-status-pill" style={{
                background: `${agentColor}20`,
                color: agentColor,
                border: `1px solid ${agentColor}55`,
                opacity: s === 'idle' ? 0.6 : 1,
              }}>{s}</span>
            </div>
          )
        })}
      </div>

      <div className="sidebar-block feed-block">
        <div className="block-label">Activity Feed</div>
        {feed.length === 0 && (
          <p className="feed-empty">No activity yet. Send a message to begin.</p>
        )}
        {feed.slice(0, 12).map((item, i) => (
          <div key={i} className={`feed-entry kind-${item.kind}`}>
            <span className="feed-pip" />
            <span className="feed-txt">{item.message}</span>
          </div>
        ))}
      </div>
    </aside>
  )
}

// ── Messages list with collapse ───────────────────────────────────────────

function MessagesList({ messages, bottomRef, onAction }) {
  const [showAllMessages, setShowAllMessages] = useState(false)
  const visibleMessages = showAllMessages || messages.length <= 8
    ? messages
    : messages.slice(messages.length - 8)
  const hiddenCount = messages.length - visibleMessages.length
  return (
    <div className="messages-list">
      {hiddenCount > 0 && (
        <button className="show-earlier-btn" onClick={() => setShowAllMessages(true)}>
          Show {hiddenCount} earlier messages
        </button>
      )}
      {visibleMessages.map((msg, i) =>
        msg.role === 'user'
          ? (
            <div key={i} className="msg-user">
              <div className="user-bubble">{msg.content}</div>
            </div>
          )
          : msg.role === 'autonomous'
          ? <AutonomousMessage key={msg.id} msg={msg} />
          : <AiMessage key={msg.id} msg={msg} onAction={onAction} />
      )}
      <div ref={bottomRef} style={{ height: 1 }} />
    </div>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [activeTab, setActiveTab]     = useState('chat')
  const [messages, setMessages]       = useState([])
  const [input, setInput]             = useState('')
  const [streaming, setStreaming]     = useState(false)
  const [agentStatus, setAgentStatus] = useState({
    patient_access: 'idle',
    billing_coding: 'idle',
    denial_management: 'idle',
    prior_auth: 'idle',
  })
  const [outcomes, setOutcomes] = useState({
    appointments_recovered: 0,
    revenue_recovered: 0,
    denials_overturned: 0,
    hours_saved: 0,
  })
  const [feed, setFeed]           = useState([])
  const [approvals, setApprovals] = useState([])
  const [data, setData]           = useState(null)
  const [lastReply, setLastReply] = useState('')
  const [chatHistory, setChatHistory] = useState([])

  const bottomRef    = useRef(null)
  const inputRef     = useRef(null)
  const statusTimers = useRef({})

  // Data refresh
  const refreshDashboard = useCallback(async () => {
    try {
      const [o, f, a] = await Promise.all([
        fetch('/api/outcomes').then(r => r.json()),
        fetch('/api/feed').then(r => r.json()),
        fetch('/api/approvals').then(r => r.json()),
      ])
      setOutcomes(o)
      setFeed(f)
      setApprovals(a)
    } catch (_) {}
  }, [])

  const refreshData = useCallback(async () => {
    try {
      const d = await fetch('/api/data-summary').then(r => r.json())
      setData(d)
    } catch (_) {}
  }, [])

  useEffect(() => {
    refreshDashboard()
    refreshData()
    const t1 = setInterval(refreshDashboard, 6000)
    const t2 = setInterval(refreshData, 10000)
    return () => { clearInterval(t1); clearInterval(t2) }
  }, [refreshDashboard, refreshData])

  // Switch to dashboard tab → refresh data immediately
  useEffect(() => {
    if (activeTab === 'dashboard') refreshData()
  }, [activeTab, refreshData])

  // Auto-scroll chat
  useEffect(() => {
    if (activeTab === 'chat') bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeTab])

  // Agent status helpers
  const setAgentWorking = useCallback((key) => {
    if (!key || !AGENT_META[key]) return
    if (statusTimers.current[key]) clearTimeout(statusTimers.current[key])
    setAgentStatus(prev => ({ ...prev, [key]: 'working' }))
  }, [])

  const setAgentDone = useCallback((key) => {
    if (!key || !AGENT_META[key]) return
    setAgentStatus(prev => ({ ...prev, [key]: 'done' }))
    statusTimers.current[key] = setTimeout(() => {
      setAgentStatus(prev => ({ ...prev, [key]: 'idle' }))
    }, 5000)
  }, [])

  // Approval actions
  const handleApprove = useCallback(async (claimId) => {
    await fetch(`/api/agents/denial-management/approve/${claimId}`, { method: 'POST' })
    await Promise.all([refreshDashboard(), refreshData()])
  }, [refreshDashboard, refreshData])

  const handleDismiss = useCallback(async (approvalId) => {
    await fetch(`/api/approvals/${approvalId}/dismiss`, { method: 'POST' })
    await refreshDashboard()
  }, [refreshDashboard])

  // Autonomous agent run
  const runAutonomous = useCallback(async () => {
    if (streaming) return
    setActiveTab('chat')

    const AGENTS_ORDER = ['patient_access', 'billing_coding', 'denial_management']
    const msgId = Date.now()
    setMessages(prev => [...prev, {
      role: 'autonomous',
      id: msgId,
      phases: AGENTS_ORDER.map(a => ({ agent: a, status: 'pending', steps: [], result: null, count: 0 })),
      summary: null,
      done: false,
    }])
    setStreaming(true)

    try {
      const resp = await fetch('/api/agents/autonomous/stream', { method: 'POST' })
      const reader = resp.body.getReader()
      const dec = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let ev
          try { ev = JSON.parse(line.slice(6)) } catch { continue }

          if (ev.type === 'agent_start') {
            setAgentWorking(ev.agent)
            setMessages(prev => prev.map(m => {
              if (m.id !== msgId) return m
              return {
                ...m,
                phases: m.phases.map(p =>
                  p.agent === ev.agent ? { ...p, status: 'active', steps: [ev.message] } : p
                ),
              }
            }))
          }

          if (ev.type === 'step_info') {
            setMessages(prev => prev.map(m => {
              if (m.id !== msgId) return m
              return {
                ...m,
                phases: m.phases.map(p =>
                  p.agent === ev.agent ? { ...p, steps: [...p.steps, ev.message] } : p
                ),
              }
            }))
          }

          if (ev.type === 'agent_result') {
            setAgentDone(ev.agent)
            setMessages(prev => prev.map(m => {
              if (m.id !== msgId) return m
              return {
                ...m,
                phases: m.phases.map(p =>
                  p.agent === ev.agent
                    ? { ...p, status: 'done', result: ev.message, count: ev.count || 0 }
                    : p
                ),
              }
            }))
          }

          if (ev.type === 'auto_summary') {
            const o = ev.outcomes
            const total = (o.appointments_recovered || 0) + (o.denials_overturned || 0)
            const summary = total > 0
              ? `**Autonomous run complete.** The agents processed all open work items:\n\n` +
                `• **${o.appointments_recovered} no-show appointment${o.appointments_recovered !== 1 ? 's' : ''}** recovered and rebooked\n` +
                `• **${o.denials_overturned} denial${o.denials_overturned !== 1 ? 's' : ''} overturned** — $${Number(o.revenue_recovered).toLocaleString()} revenue recovered\n` +
                `• **${Number(o.hours_saved).toFixed(1)} staff hours saved** through autonomous processing\n\n` +
                `All three agents are now monitoring for new work.`
              : `**Autonomous scan complete.** The agents reviewed all queues and found everything in order. ` +
                `No pending encounters, no-shows, or denied claims requiring action.\n\n` +
                `All three agents are standing by.`
            setMessages(prev => prev.map(m => m.id === msgId ? { ...m, summary } : m))
          }

          if (ev.type === 'done') {
            setMessages(prev => prev.map(m => m.id === msgId ? { ...m, done: true } : m))
            setStreaming(false)
            refreshDashboard()
            refreshData()
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, summary: `Agent run failed — ${err.message}`, done: true } : m
      ))
      setStreaming(false)
    }
  }, [streaming, setAgentWorking, setAgentDone, refreshDashboard, refreshData])

  // Send + stream
  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim()
    if (!trimmed || streaming) return
    setInput('')
    setActiveTab('chat')
    inputRef.current?.focus()

    const aiId = Date.now()
    setMessages(prev => [
      ...prev,
      { role: 'user', content: trimmed },
      { role: 'ai', id: aiId, steps: [], reply: null, agent: null, done: false, actions: [] },
    ])
    setStreaming(true)

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
        request_text: trimmed,
        context: lastReply,
        history: chatHistory.slice(-6),
      }),
      })

      const reader = resp.body.getReader()
      const dec    = new TextDecoder()
      let buf      = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let ev
          try { ev = JSON.parse(line.slice(6)) } catch { continue }

          if (ev.type === 'step') {
            if (ev.agent) setAgentWorking(ev.agent)
            setMessages(prev => prev.map(m => {
              if (m.id !== aiId) return m
              const steps = m.steps.map((s, i) =>
                i === m.steps.length - 1 ? { ...s, status: 'done' } : s
              )
              return {
                ...m,
                steps: [...steps, { message: ev.message, agent: ev.agent, status: 'active' }],
                agent: ev.agent || m.agent,
              }
            }))
          }

          if (ev.type === 'result') {
            if (ev.agent) setAgentDone(ev.agent)
            setLastReply(ev.reply || '')
            setChatHistory(prev => [
              ...prev,
              { role: 'user', content: trimmed },
              { role: 'assistant', content: ev.reply || '' },
            ])
            setMessages(prev => prev.map(m => {
              if (m.id !== aiId) return m
              return {
                ...m,
                steps: m.steps.map(s => ({ ...s, status: 'done' })),
                reply: ev.reply || '',
                agent: ev.agent || m.agent,
              }
            }))
          }

          if (ev.type === 'actions') {
            setMessages(prev => prev.map(m =>
              m.id !== aiId ? m : { ...m, actions: ev.suggestions || [] }
            ))
          }

          if (ev.type === 'done') {
            setMessages(prev => prev.map(m =>
              m.id === aiId ? { ...m, done: true } : m
            ))
            setStreaming(false)
            refreshDashboard()
            refreshData()
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === aiId
          ? { ...m, reply: `Something went wrong — ${err.message}`, done: true }
          : m
      ))
      setStreaming(false)
    }
  }, [streaming, setAgentWorking, setAgentDone, refreshDashboard, refreshData])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="app">
      <Sidebar
        outcomes={outcomes}
        feed={feed}
        approvals={approvals}
        agentStatus={agentStatus}
      />

      <div className="main-area">
        {/* Top nav tabs */}
        <div className="main-topbar">
          <div className="main-tabs">
            <button
              className={`main-tab${activeTab === 'chat' ? ' active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              Chat
            </button>
            {activeTab === 'chat' && messages.length > 0 && (
              <button className="new-chat-btn" onClick={() => { setMessages([]); setChatHistory([]); setLastReply('') }}>
                + New conversation
              </button>
            )}
            <button
              className={`activate-topbar-btn${streaming ? ' disabled' : ''}`}
              onClick={runAutonomous}
              disabled={streaming}
              title="Run all agents autonomously"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Activate Agents
            </button>
            <button
              className={`main-tab${activeTab === 'dashboard' ? ' active' : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              Dashboard
              {approvals.length > 0 && (
                <span className="tab-alert">{approvals.length}</span>
              )}
            </button>
            <button
              className={`main-tab${activeTab === 'agents' ? ' active' : ''}`}
              onClick={() => setActiveTab('agents')}
            >
              Agents
            </button>
          </div>
        </div>

        {/* Chat view */}
        {activeTab === 'chat' && (
          <div className="chat-area">
            <div className="messages-scroller">
              {messages.length === 0
                ? <WelcomeScreen onPrompt={sendMessage} onActivate={runAutonomous} />
                : <MessagesList messages={messages} bottomRef={bottomRef} onAction={sendMessage} />
              }
            </div>

            <div className="input-bar">
              <div className="input-wrap">
                <textarea
                  ref={inputRef}
                  className="chat-input"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Care Intelligence to do something…"
                  rows={1}
                  disabled={streaming}
                />
                <button
                  className="send-btn"
                  onClick={() => sendMessage(input)}
                  disabled={!input.trim() || streaming}
                  aria-label="Send"
                >
                  {streaming
                    ? <svg className="spin" width="16" height="16" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <path d="M21 12a9 9 0 1 1-2.6-6.4" />
                      </svg>
                    : <SendIcon />
                  }
                </button>
              </div>
              <p className="input-hint">Enter to send · Shift+Enter for new line</p>
            </div>
          </div>
        )}

        {/* Dashboard view */}
        {activeTab === 'dashboard' && (
          <DashboardView
            data={data}
            approvals={approvals}
            outcomes={outcomes}
            onApprove={handleApprove}
            onDismiss={handleDismiss}
          />
        )}

        {/* Agents view */}
        {activeTab === 'agents' && (
          <AgentsView
            data={data}
            onRefresh={() => { refreshDashboard(); refreshData() }}
          />
        )}
      </div>
    </div>
  )
}
