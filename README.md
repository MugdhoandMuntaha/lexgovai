# LexGOV AI

Enterprise Multi-Agent RAG compliance benchmarking engine for Bangladeshi SMEs.

LexGOV AI automatically benchmarks company Standard Operating Procedures (SOPs) against National Board of Revenue (NBR) Value Added Tax (VAT) regulatory amendments, computes mathematical confidence scores on citations, flags potential hallucinations for human review, drafts audit-ready policy rewrites, and compiles actionable engineering/operational checklists.

```
compliance/
├── backend/               FastAPI service + 5-agent RAG pipeline
│   ├── app/               Agents, vector store, SQLite DB, report exporter, API
│   ├── data/              Before/after regulations and sample SOP documents
│   ├── tests/             Offline pytest suite with deterministic mock LLM
│   └── requirements.txt
└── frontend/              Next.js 16 + React 19 + Tailwind CSS dashboard
    ├── src/app/           Overview, Upload, Watcher diff, Pipeline, Action plan
    ├── src/components/    Navbar (with mobile drawer), LegalDisclaimer, BackendStatus
    └── src/lib/           API client (with SSE streaming reader), session workspace
```

---

## The 5-Agent Pipeline

| # | Agent | Role | Implementation |
|---|---|---|---|
| **01** | **Watcher** | Cryptographic diff & obligation extractor | Line diff + SHA-256 hash of `regulation_before.txt` vs `regulation_after.txt`, then Gemini summarises changes and extracts concrete testable obligations (cached per version hash + model). |
| **02** | **Retriever** | Multi-agent vector RAG | Embeds each extracted obligation (`gemini-embedding-001`) and queries ChromaDB for top-k matching SOP sections. |
| **03** | **Impact Analyzer** | Compliance gap & risk evaluator | Gemini compares obligations against retrieved SOP chunks using structured JSON output (`gap`, `conflict`, `outdated_reference`), rating impact (0-100) and urgency. |
| **04** | **Action Plan Generator** | Policy redliner & fix engineer | Drafts replacement SOP clauses in audit-ready legal language and lists operational technical fixes. |
| **05** | **Critic / Verifier** | Deterministic citation verifier | **No LLM (deterministic).** RapidFuzz partial-ratio string matching verifies every quotation against actual source texts, replaces snippets with verbatim source spans, calculates mathematical confidence, and flags citations under 75% for mandatory human review. |

---

## Quickstart

### 1. Start the Backend

Requires Python 3.12+ (tested on Python 3.14).

```powershell
cd d:\compliance\backend

# Create virtual environment (already set up in .venv)
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure your Gemini API key:
Copy-Item .env.example .env
# Edit .env and set: GEMINI_API_KEY=your_key_here

# Start API server on http://localhost:8000
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --port 8000
```

> **Note:** The backend boots cleanly even without an API key: `/api/health` and `/api/regulations/current` will work immediately, while AI-powered routes return clean `503` notices until a key is supplied.

To run the offline test suite (22 comprehensive tests):
```powershell
cd d:\compliance\backend
.\.venv\Scripts\python.exe -m pytest -v
```

### Management CLI
LexGOV AI includes a built-in administrative CLI for managing workspaces, users, and audit retention:
```powershell
cd d:\compliance\backend
# Create a user and workspace with a chosen plan (free, starter, growth, professional):
.\.venv\Scripts\python.exe -m app.cli create-user founder@sme.com.bd SecurePassword123 --plan starter --name "Junaid"

# Upgrade or set plan for an existing user or workspace:
.\.venv\Scripts\python.exe -m app.cli set-plan founder@sme.com.bd growth

# Purge expired action plans based on workspace retention rules:
.\.venv\Scripts\python.exe -m app.cli purge-expired
```

### 2. Start the Frontend

Requires Node.js 18+ (tested on Node.js 22+).

```powershell
cd d:\compliance\frontend

npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Subscription Plans & Metering (Phase 1)

LexGOV AI implements a 4-tier workspace subscription framework:
- **Free (৳0/mo):** 9-question launch questionnaire, general policy recommendations, basic company profile.
- **Starter (৳999/mo):** SOP upload & indexing, 10 detailed analyses/mo, 5 SOP documents, basic personalized checklist, markdown report export, 30-day retention.
- **Growth (৳2,999/mo):** 50 detailed analyses/mo, 25 SOP documents, full policy drafts, technical operational fixes, 365-day retention.
- **Professional (৳7,999/mo):** 200 detailed analyses/mo, 100 SOP documents, advanced technical recommendations & risk scoring, 1,095-day retention, priority support.

Enforcement is strictly server-side fail-closed; client routes are protected via Next.js 16 `src/proxy.ts`. See [`docs/adr/0001-subscriptions-and-entitlements.md`](docs/adr/0001-subscriptions-and-entitlements.md) for full architectural documentation.

---

## Key Features

- **Interactive Policy Redlines:** Word-level Longest Common Subsequence (LCS) diff viewer supporting Track Changes (inline redline), Side-by-Side split, and Clean Policy Draft modes with one-click copy.
- **Audit-Ready Markdown & PDF Print Reports:** Export Markdown (`.md`) reports or trigger official browser print/PDF generation stamped with Bangladesh Value Added Tax & Supplementary Duty Act 2012 compliance verification, SHA-256 version integrity hash, and executive sign-off blocks.
- **Live Server-Sent Events (SSE):** The pipeline execution page streams status and timing as each individual agent starts and finishes in real time.
- **Offline / Local Safe:** Full 48-test regression test suite runs offline without making billable LLM calls.

