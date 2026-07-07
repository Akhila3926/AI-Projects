# Care Intelligence

An AI-powered healthcare revenue cycle management platform with autonomous agents for patient access, billing & coding, and denial management.

## Overview

Care Intelligence uses a multi-agent AI workforce to automate healthcare administrative tasks:

- **Patient Access Agent** — Handles appointment scheduling, cancellations, and no-show recovery
- **Billing & Coding Agent** — Assigns ICD-10/CPT codes from encounter notes and scrubs claims before submission
- **Denial Management Agent** — Diagnoses denied claims and drafts payer appeal letters
- **Chat Interface** — Natural language interface to query data and trigger any agent action
- **Dashboard** — Real-time analytics including claim status, denial rates by payer, and revenue metrics

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Recharts |
| Backend | FastAPI, Python 3.8+ |
| Database | SQLite (via SQLAlchemy) |
| AI | Groq API (llama-3.3-70b-versatile) |
| Streaming | Server-Sent Events (SSE) |

## Project Structure

```
care-intelligence/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── billing_coding.py       # ICD-10/CPT coding + claim scrubbing
│   │   │   ├── denial_management.py    # Denial diagnosis + appeal drafting
│   │   │   └── patient_access.py       # Scheduling + no-show recovery
│   │   ├── data/
│   │   │   ├── models.py               # SQLAlchemy models
│   │   │   └── store.py                # Data access layer
│   │   ├── orchestrator/
│   │   │   └── orchestrator.py         # Agent routing + chat handling
│   │   ├── llm.py                      # Groq LLM wrapper
│   │   └── main.py                     # FastAPI app + SSE streaming
│   ├── data_store/
│   │   ├── seed_data.json              # Fallback seed data
│   │   └── care_intelligence.db        # SQLite database (gitignored)
│   ├── migrate_to_db.py                # One-time JSON → SQLite migration
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx                     # Main app + all views
    │   ├── App.css                     # Styling + CSS variables
    │   └── api.js                      # API client
    ├── package.json
    └── vite.config.js
```

## Setup

### Prerequisites

- Python 3.8+
- Node.js 18+
- A [Groq API key](https://console.groq.com)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your GROQ_API_KEY to .env

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5173` with the API at `http://localhost:8000`.

### Database

The app uses a SQLite database at `backend/data_store/care_intelligence.db`.

To migrate from the seed JSON file to the database:

```bash
cd backend
python migrate_to_db.py
```

## Environment Variables

Create `backend/.env` with:

```
GROQ_API_KEY=your_groq_api_key_here
```

## Features

### Chat
Ask natural language questions about your data:
- `"show me denied claims"`
- `"denial rate by payer"`
- `"which payer has the highest denials"`
- `"revenue breakdown"`
- `"total patients"`
- `"show humana claims"`
- `"recover no-show appointments"`

### Dashboard
- Outcome metrics (appointments recovered, revenue recovered, denials won, hours saved)
- Activity feed with real-time agent actions
- Analytics tab: claim status breakdown, denial rate by payer, revenue billed vs recovered
- Patient, appointment, encounter, and claim tables

### Agents Tab
Manually trigger individual agents or run the full autonomous workflow.

## License

Private — all rights reserved.
