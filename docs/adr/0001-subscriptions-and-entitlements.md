# ADR 0001: Subscriptions, Entitlements, and Usage Metering Architecture (Phase 1)

**Status:** Accepted  
**Date:** 2026-11-08  
**Context:** Bangladesh SME Corporate Compliance & Regulatory Intelligence Automation

---

## 1. Context & Problem Statement

LexGOV AI provides multi-agent AI analysis comparing Bangladeshi SME Standard Operating Procedures (SOPs) against National Board of Revenue (NBR) regulatory statutory orders (SROs). To commercialize this platform while maintaining a low barrier to entry for early-stage entrepreneurs, we require a subscription, entitlement gating, and usage metering framework.

### Non-Negotiable Requirements
1. **Single Source of Truth:** Plan pricing, limits, and capability matrices must exist in pure typed Python data (`app/plans.py`) without I/O and be exposed dynamically to the frontend via `GET /api/plans`. No prices, limits, or levels may be hardcoded on the client.
2. **Workspace-Centric Subscriptions:** Subscriptions belong to a `Workspace`, not a `User`. Users are members of workspaces. In Phase 1, each user owns their primary workspace.
3. **Fail-Closed Server-Side Enforcement:** UI gating is cosmetic; all endpoints and resources enforce capability checks and quotas server-side before execution.
4. **Agent Logic Preservation:** Multi-agent pipeline core logic (`agents.py`) must remain pure and unmodified. Lower tiers receive deterministic subsets of the professional output through `AnalysisOptions` post-processing. Professional tier output is 100% identical to baseline.
5. **Billing Port/Adapter Architecture:** Real payment gateway integration (SSLCommerz, bKash) is deferred to Phase 2; Phase 1 requires an abstract `BillingProvider` protocol with a `MockBillingProvider` adapter guarded against accidental production use.
6. **Strict Workspace Isolation (Anti-IDOR):** Every resource lookup (documents, action plans, ChromaDB embeddings, checklists) must enforce workspace ownership checks.
7. **Zero-Dependency Security:** All password hashing, session generation, and token verification must utilize the Python 3.14 standard library (`hashlib.scrypt`, `secrets`, `hmac`).
8. **Next.js 16 Alignment:** Route protection must utilize the Next.js 16 `src/proxy.ts` convention (`middleware.ts` is deprecated).

---

## 2. Decision & Architecture

### 2.1 Plan Catalog (`app/plans.py`)
Four tiers are defined in Bangladesh Taka (BDT):
- **Free (৳0/mo):** 9-question launch questionnaire, general policy recommendations, basic company profile.
- **Starter (৳999/mo):** SOP upload & indexing, 10 detailed analyses/mo, 5 SOP documents, basic personalized checklist, markdown report export, 30-day retention.
- **Growth (৳2,999/mo):** 50 detailed analyses/mo, 25 SOP documents, full policy drafts, technical operational fixes, 365-day retention.
- **Professional (৳7,999/mo):** 200 detailed analyses/mo, 100 SOP documents, advanced technical recommendations & risk scoring, 1,095-day (3-year) retention, priority support.

Unimplemented features (regulatory news, automated monitoring, team collaboration, API integrations) are registered in the catalog with `implemented=false` so the UI marks them "Coming soon" without advertising unbuilt features.

### 2.2 Versioned Database Schema (`app/db.py`)
A versioned migration engine (`schema_version`) manages seamless transitions:
- `users`: Standard library `scrypt` hashed passwords with unique salts.
- `workspaces`: Workspace entities.
- `memberships`: User-to-workspace mapping with owner/member roles.
- `sessions`: High-entropy `secrets.token_urlsafe(32)` tokens stored with expiration.
- `subscriptions`: Active subscription records with `period_start`, `period_end`, and `cancel_at_period_end`.
- `subscription_events`: Append-only audit ledger of plan changes and cancellations.
- `usage_counters`: Aggregated counter ledgers per workspace, metric, and window.
- `usage_events`: Two-phase transaction logs (`reserved`, `committed`, `released`) with idempotency keys.
- `checklist_items`: Interactive compliance tasks seeded by the Start Fresh wizard.
- `webhook_events`: Idempotency tracking for external billing events.

Pre-existing records are automatically assigned to `workspace_legacy` with a seeded professional subscription during migration to prevent regression of legacy tests.

### 2.3 Two-Phase Usage Metering (`app/usage.py`)
Usage counters (`detailed_analyses`, `sop_documents`, `general_ai_questions`) utilize a two-phase commit protocol:
1. **Reserve:** Verifies quota and atomically increments the counter with `status='reserved'`. SQLite `RLock` prevents race conditions and over-allocation under concurrent requests.
2. **Commit:** Upon pipeline or upload completion, marks the event `status='committed'`.
3. **Release:** If the multi-agent pipeline encounters an error or is aborted, the counter is immediately decremented and the event is marked `status='released'`.

Free tier counters reset on Asia/Dhaka calendar month boundaries; paid tier counters align with workspace billing renewal periods.

### 2.4 Analysis Tiering via Post-Processing (`app/entitlements.py`)
The pipeline runs through all necessary agents; before output persistence, `AnalysisOptions.apply(plan)` enforces tiering:
- **Findings Cap:** Free: 0, Starter: 3, Growth: 10, Professional: unlimited.
- **Policy Drafts:** Subsets generated clauses according to plan level.
- **Technical Recommendations:** Truncated to 0 on Starter, 5 on Growth, unlimited on Professional.
- **Locked Metadata:** Any withheld items are logged in `plan['locked']` with `section`, `required_plan`, and `hidden_count`, allowing the frontend to present transparent upgrade opportunities without leaking private data.

### 2.5 Route Protection & Client Gating
- **Next.js 16 Proxy (`frontend/src/proxy.ts`):** Evaluates incoming requests on protected paths (`/upload`, `/analysis`, `/action-plan`, `/account`) and redirects unauthenticated users to `/login`.
- **Client Auth Provider (`src/context/AuthContext.tsx`):** Provides session state, capability checker `hasCapability()`, and modal controller `openUpgradeModal()`.
- **Feature Gate Component (`src/components/FeatureGate.tsx`):** Renders children if the workspace possesses the required capability; otherwise renders an accessible locked preview card with direct upgrade CTA.

---

## 3. Phase 2 Extension Points

1. **Payment Gateway Integration:** Implement `SSLCommerzBillingProvider` and `BKashBillingProvider` implementing `BillingProvider` protocol.
2. **Regulatory Monitoring Engine:** Dedicated background workers polling NBR gazettes, updating `monitored_sources` gauge.
3. **Team Invites & Multi-Seat RBAC:** Workspaces can invite additional team members capped by the `team_members` gauge.
4. **API Keys & Webhooks:** High-volume ERP integrations using workspace-scoped API keys with rate-limiting.

---

## 4. Verification & Testing

The architecture is covered by 22 automated backend pytest tests:
- **Golden Catalog Drift Test:** Independent assertion of all plan prices, limits, and capabilities to catch accidental schema drift.
- **Capability Matrix Enforcement:** Parametrized test across all 4 plans verifying 200 vs 403 status codes.
- **Quota 429 Test:** Exhaustion of Starter analysis quota returning HTTP 429 with `{code, metric, limit, used, upgrade_to}`.
- **Thread Concurrency Test:** Multi-threaded pool competing for a single remaining quota slot; exactly 1 succeeds, 5 fail, database ledger remains strictly bounded.
- **Cross-Workspace IDOR Test:** Prevents User B from accessing, analyzing, or downloading documents and plans belonging to User A.
- **Audit Retention & Purge:** Verifies plans older than `audit_history_days` are hidden and physically cleaned up by CLI `purge-expired`.
- **Schema Migration Test:** Upgrades a V1 database to V2 and verifies legacy records are preserved.

