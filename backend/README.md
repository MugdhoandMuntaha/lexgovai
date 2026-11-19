# LexGOV AI Backend

FastAPI service that powers the LexGOV AI dashboard. It runs a 5-agent pipeline that compares a company's
SOP against a regulatory change (NBR VAT SRO Clause 4.2) using Gemini, ChromaDB and RapidFuzz.

| # | Agent | How it works |
|---|-------|--------------|
| 1 | Watcher | Deterministic line diff + SHA-256 version hash of `data/regulations/*`, then Gemini summarises the change and extracts obligations. Cached per version hash + model. |
| 2 | Retriever | Embeds each obligation (`gemini-embedding-001`) and queries ChromaDB for the top-k SOP chunks of the uploaded document. |
| 3 | Impact Analyzer | Gemini (structured JSON output) compares obligations vs. retrieved SOP text and returns findings with verbatim citations, impact score and urgency. |
| 4 | Generator | Gemini drafts replacement SOP clauses and operational fixes. |
| 5 | Critic / Verifier | No LLM. RapidFuzz matches every citation against the real SOP/regulation text, replaces it with the exact source span, sets `confidence`, and flags anything below `REVIEW_THRESHOLD` for human review. |

## Setup

Requires Python 3.12+ (tested on 3.14).

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env   # then put your GEMINI_API_KEY in .env
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --port 8000
```

Without `GEMINI_API_KEY` the server still starts: `/api/health` and `/api/regulations/current` work, while
LLM-backed endpoints return `503` with an explanatory message.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Status, configured model, whether an API key is present |
| POST | `/api/company-profile` | Create a company profile |
| POST | `/api/documents/upload` | Multipart `company_profile_id` + `file` (.pdf/.txt, max 10 MB); chunks, embeds and indexes |
| POST | `/api/documents/sample` | Index the bundled sample SOP (`data/samples/`) for a company |
| GET | `/api/regulations/current` | Before/after regulation text, line diff, version hash (no LLM) |
| POST | `/api/regulations/detect-change` | Watcher agent output (summary, changed clauses, obligations) |
| POST | `/api/analyze` | Run the full pipeline and return the action plan |
| POST | `/api/analyze/stream` | Same, as Server-Sent Events: `agent_started`, `agent_completed`, `completed`, `error` |
| GET | `/api/action-plans/{id}` | Fetch a saved action plan |
| GET | `/api/action-plans/{id}/report` | Download the plan as Markdown |

Data is stored in `storage/` (SQLite + ChromaDB). To analyse a different regulation, replace
`data/regulations/regulation_before.txt` / `regulation_after.txt`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use a deterministic fake LLM, so they run offline and need no API key.

