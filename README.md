# ComplianceOS — Frontend

Next.js 16 (App Router) + React 19 + Tailwind CSS frontend dashboard for ComplianceOS.

## Pages

- **`/` (Overview):** Executive dashboard explaining the 5-agent compliance pipeline and Bangladesh NBR VAT 2025 standard.
- **`/upload` (SOP Ingestion):** Upload corporate SOPs (.pdf / .txt up to 10MB) or one-click index the bundled Apex Logistics Bangladesh sample document into ChromaDB.
- **`/regulations` (Watcher Diff):** Cryptographic text diff comparing `regulation_before.txt` and `regulation_after.txt` with SHA-256 version hashes and on-demand Agent 1 summaries.
- **`/analysis` (Pipeline):** Real-time Server-Sent Events (SSE) streaming of the 5 agents with live status badges, processing spinners, and millisecond durations.
- **`/action-plan/[id]` (Report):** Verified audit report with mathematical confidence ratings, verbatim source citations, human review flags, redlined policy rewrites, interactive task checkboxes, and direct `.md` report download.

## Scripts

```bash
npm run dev    # Start dev server on http://localhost:3000
npm run build  # Production build (Turbopack + TypeScript check)
npm run start  # Start production server
npm run lint   # Run ESLint check
```

## Backend Connection

Defaults to `http://localhost:8000/api`. To customize, configure in `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```
