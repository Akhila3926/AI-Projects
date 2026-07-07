from __future__ import annotations
"""SMTP email sender for automated reports."""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def send_report(subject: str, html_body: str) -> bool:
    """Send an HTML email report. Returns True on success."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    to_email  = os.getenv("REPORT_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("[Emailer] SMTP_USER / SMTP_PASS not configured — skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        print(f"[Emailer] Report sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Emailer] Failed to send email: {e}")
        return False


def build_denial_report_html(report: dict) -> str:
    """Build HTML email focused on the top 3 highest-value denied claims."""
    now          = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    scanned      = report["scanned"]
    recovered    = report["recovered"]
    still_denied = report["still_denied"]
    revenue      = report["revenue_recovered"]
    top3         = report.get("top3_claims", [])

    rank_colors = ["#1a6fba", "#0f4a8a", "#2563eb"]
    rank_labels = ["#1 Highest", "#2 Second", "#3 Third"]

    top3_cards = ""
    for i, c in enumerate(top3):
        status = "Appealed" if c in report.get("recovered_claims", []) else "Still Denied"
        status_color = "#3a7a5a" if status == "Appealed" else "#c0392b"
        status_bg    = "#d4edda"  if status == "Appealed" else "#fdecea"
        top3_cards += f"""
        <div style="border:1px solid #e4dccf; border-radius:10px; padding:20px; margin-bottom:16px; border-left: 4px solid {rank_colors[i]};">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <span style="font-size:11px; font-weight:700; color:{rank_colors[i]}; text-transform:uppercase; letter-spacing:0.06em;">{rank_labels[i]} Denied Claim</span>
            <span style="background:{status_bg}; color:{status_color}; font-size:11px; font-weight:700; padding:3px 10px; border-radius:10px;">{status}</span>
          </div>
          <div style="font-size:20px; font-weight:700; color:#1a1714; margin-bottom:4px;">${c['amount']:,.0f}</div>
          <div style="font-size:14px; font-weight:600; color:#3a2e1e; margin-bottom:8px;">{c['patient']}</div>
          <table style="width:100%; font-size:13px; border-collapse:collapse;">
            <tr><td style="color:#9b8b72; padding:3px 0; width:110px;">Claim ID</td><td style="color:#1a1714; font-weight:500;">{c['id']}</td></tr>
            <tr><td style="color:#9b8b72; padding:3px 0;">Payer</td><td style="color:#1a1714; font-weight:500;">{c['payer']}</td></tr>
            <tr><td style="color:#9b8b72; padding:3px 0;">Denial Reason</td><td style="color:#1a1714; font-weight:500;">{c['denial_reason']}</td></tr>
          </table>
        </div>"""

    return f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: Arial, sans-serif; color: #1a1714; background: #f7f4ef; margin: 0; padding: 0; }}
  .container {{ max-width: 640px; margin: 30px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  .header {{ background: linear-gradient(135deg, #1a6fba, #0f4a8a); padding: 32px; color: white; }}
  .header h1 {{ margin: 0; font-size: 21px; }}
  .header p {{ margin: 6px 0 0; opacity: 0.85; font-size: 13px; }}
  .metrics {{ display: flex; padding: 20px 24px; gap: 12px; background: #faf8f5; border-bottom: 1px solid #e4dccf; }}
  .metric {{ flex: 1; text-align: center; padding: 12px 8px; background: white; border-radius: 8px; border: 1px solid #e4dccf; }}
  .metric .num {{ font-size: 22px; font-weight: 700; color: #1a6fba; }}
  .metric .label {{ font-size: 10px; color: #9b8b72; text-transform: uppercase; margin-top: 3px; letter-spacing: 0.04em; }}
  .section {{ padding: 24px; }}
  .section h2 {{ font-size: 14px; font-weight: 700; color: #5a4830; margin: 0 0 16px; text-transform: uppercase; letter-spacing: 0.06em; }}
  .footer {{ padding: 16px 24px; text-align: center; font-size: 11px; color: #9b8b72; background: #faf8f5; border-top: 1px solid #e4dccf; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🏥 Care Intelligence — Denial Alert</h1>
    <p>Top 3 highest-value denied claims · {now}</p>
  </div>

  <div class="metrics">
    <div class="metric">
      <div class="num">{scanned}</div>
      <div class="label">Scanned</div>
    </div>
    <div class="metric">
      <div class="num" style="color:#3a7a5a">{recovered}</div>
      <div class="label">Appealed</div>
    </div>
    <div class="metric">
      <div class="num" style="color:#c0392b">{still_denied}</div>
      <div class="label">Still Denied</div>
    </div>
    <div class="metric">
      <div class="num" style="color:#1a6fba">${revenue:,.0f}</div>
      <div class="label">Revenue</div>
    </div>
  </div>

  <div class="section">
    <h2>🚨 Top 3 Claims Requiring Attention</h2>
    {top3_cards if top3_cards else '<p style="color:#9b8b72; font-size:13px;">No denied claims found.</p>'}
  </div>

  <div class="footer">
    Care Intelligence · Autonomous Denial Management Agent · Generated automatically every cycle.
  </div>
</div>
</body>
</html>
"""
