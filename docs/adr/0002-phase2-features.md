# ADR 0002: Implementation of Phase 2 Subscription Capabilities

**Status:** Accepted  
**Date:** 2026-11-08  
**Context:** Bangladesh SME Corporate Compliance & Regulatory Intelligence Automation

---

## 1. Context & Objectives

LexGOV AI has established its baseline subscription catalog (`app/plans.py`), entitlement enforcement (`app/entitlements.py`), usage metering (`app/usage.py`), and mandatory authentication wall. Several capabilities were cataloged with `implemented=false` (e.g., `regulatory_news`, `automated_monitoring`, `deadline_reminders`, `ai_assistant`, `team_collaboration`, `api_integrations`, `priority_support`).

This ADR defines the technical architecture, module boundaries, data schemas, background job worker, ports & adapters, permission matrices, and security controls required to deliver these features vertically across plans.

---

## 2. Non-Negotiable Architecture Principles

1. **Single Source of Truth:** `app/plans.py` governs plan tiers and limits. Level-dependent feature behavior is defined strictly in `app/feature_options.py` as typed data structures.
2. **Fail-Closed Server-Side Enforcement:** Every endpoint and resource validates workspace membership, user role, and subscription entitlements. Foreign resources return HTTP 404 (preventing IDOR and existence leakage).
3. **Strict-Subset Invariance:** Lower subscription tiers always receive a strict subset of higher tiers, never degraded or fundamentally alternate logic.
4. **Agent Logic Preservation:** Multi-agent pipeline core logic (`agents.py`) remains pure. The verification engine is extracted into `app/verification.py` as a pure refactor used by agents, assistant, and deadline extractors.
5. **Ports and Adapters:** External boundaries (`Clock`, `Notifier`, `SourceFetcher`, `LLM`) are accessed via abstract interfaces with deterministic fakes for offline test suites.
6. **Zero Legal Hallucination:** Regulatory changes, citations, and derived deadlines must strictly trace to published regulatory text verified via deterministic string similarity (`RapidFuzz`). Seed or synthetic data is explicitly tagged `is_sample=True`.
7. **Idempotency Everywhere:** Background jobs, reminder notifications, fan-out alerts, invites, and webhook events utilize unique idempotency keys.

---

## 3. Module Boundaries & System Decomposition

```
backend/app/
├── plans.py               # Pure catalog: Plans, capabilities, ordered levels, and limits
├── feature_options.py     # Typed options & constants per level (ADR assumptions)
├── verification.py        # RapidFuzz deterministic quotation & snippet verification
├── ports/                 # Abstract Protocols (Clock, Notifier, SourceFetcher, LLM)
├── adapters/              # Implementations (InAppNotifier, SmtpNotifier, ConsoleNotifier, UrlPollAdapter)
├── worker.py              # Background job runner (lease management, retries, dead-letter)
├── admin.py               # Platform admin API endpoints and CLI tooling
├── news.py                # Public & sector-specific regulatory news feeds
├── monitoring.py          # SSRF-guarded poller, diff detector, and change manager
├── deadlines.py           # Checklist due dates and regulation-derived deadline extractor
├── assistant.py           # Grounded compliance assistant SSE streaming & injection guards
├── collaboration.py       # RBAC, invites, finding reviews, adjusted impact scoring
├── api_v1.py              # Scoped Bearer API key endpoints (/api/v1)
└── support.py             # Plan-prioritized support ticketing
```

---

## 4. Data Model & Migrations (`schema_version = 3`)

Migrations are executed idempotently in `app/db.py`:

1. **`regulations`**: High-level regulatory acts (e.g., "NBR Value Added Tax Act 2012").
2. **`regulation_versions`**: Specific amendments (`version_label`, `text`, `content_hash`, `effective_date`, `status: draft|pending_review|published`, `is_sample`, `published_by`, `published_at`).
3. **`regulation_sources`**: Ingestion configurations (`kind: manual|url_poll`, `url`, `poll_interval`, `enabled`, `last_checked`, `last_hash`, `failure_count`, `last_error`).
4. **`regulatory_changes`**: Diff summaries between versions (`from_version_id`, `to_version_id`, `summary`, `change_type`, `obligations`, `tags`, `detected_at`, UNIQUE on `from+to`).
5. **`news_items`**: Curated news & announcements (`title`, `content`, `sector`, `jurisdiction`, `published_at`, `source_url`, `regulation_id`).
6. **`monitor_subscriptions`**: Workspace source subscriptions (`workspace_id`, `regulation_id`, UNIQUE).
7. **`notifications`**: User/workspace notifications (`workspace_id`, `user_id`, `title`, `body`, `link`, `channel`, `dedupe_key` UNIQUE, `read_at`, `created_at`).
8. **`notification_preferences`**: Channel toggles (`workspace_id`, `user_id`, `email_enabled`, `in_app_enabled`, `frequency: instant|daily_digest`).
9. **`outbox`**: Transactional messaging queue (`channel`, `destination`, `payload`, `status: pending|sent|failed`, `attempts`, `next_attempt_at`, `error`).
10. **`jobs`**: Background job queue (`type`, `payload`, `run_at`, `status: pending|running|completed|failed|dead_letter`, `attempts`, `lease_until`, `idempotency_key` UNIQUE).
11. **`deadlines`**: Compliance dates (`workspace_id`, `title`, `due_date`, `source_type: manual|regulation`, `regulation_id`, `checklist_item_id`, `status: pending_review|active|completed`).
12. **`reminder_log`**: Deduplication log (`deadline_id`, `lead_days`, `sent_at`, UNIQUE on `deadline_id + lead_days`).
13. **`assistant_threads` & `assistant_messages`**: Chat history (`thread_id`, `workspace_id`, `user_id`, `role`, `content`, `citations`, `created_at`).
14. **`invites`**: Team invitations (`workspace_id`, `email`, `role`, `token_hash`, `expires_at`, `accepted_at`, `revoked_at`).
15. **`activity_events`**: Workspace audit log (`workspace_id`, `user_id`, `event_type`, `description`, `created_at`).
16. **`comments`**: Finding and checklist discussions (`workspace_id`, `resource_type`, `resource_id`, `user_id`, `content`, `created_at`).
17. **`finding_reviews`**: Human-in-the-loop verification (`workspace_id`, `plan_id`, `finding_id`, `status: approved|rejected|edited`, `reviewer_id`, `note`, `edited_citation`, `reviewed_at`).
18. **`api_keys`**: Workspace integration keys (`workspace_id`, `prefix`, `key_hash`, `name`, `scopes`, `last_used_at`, `revoked_at`, `created_at`).
19. **`support_tickets`**: Customer inquiries (`workspace_id`, `user_id`, `subject`, `message`, `priority: standard|priority|urgent`, `status: open|in_progress|resolved`, `created_at`).

---

## 5. Job & Worker Design (`app/worker.py`)

- **Concurrency & Leases:** SQLite-safe transactional lease locking. Workers acquire pending or expired leases (`lease_until < now`) atomically.
- **Backoff & Poison Pills:** Exponential backoff (`base_delay * 2 ** attempts`). Jobs are quarantined to `dead_letter` after 5 failed attempts.
- **Execution Modes:** Long-running daemon (`python -m app.worker`) and one-shot execution (`python -m app.worker --once`) for cron integration.
- **Admin Visibility:** Protected endpoint `GET /api/admin/queue` providing queue depth, lease statistics, and worker heartbeats.

---

## 6. Permission Matrix (RBAC)

| Action | Owner | Admin | Member | Viewer |
| :--- | :---: | :---: | :---: | :---: |
| Billing & Plan Changes | Yes | No | No | No |
| Invite & Remove Team Members | Yes | Yes | No | No |
| Manage Sources & API Keys | Yes | Yes | No | No |
| Run SOP Analysis (Consumes Quota) | Yes | Yes | Yes | No |
| Edit Checklist & Mark Complete | Yes | Yes | Yes | No |
| Add Comments & Review Findings | Yes | Yes | Yes | No |
| View Documents, Reports & News | Yes | Yes | Yes | Yes |
| Export Reports | Yes | Yes | Yes | Yes |

### Seat Limits & Downgrade Behavior
- Free / Starter: 1 seat (Owner).
- Growth: 3 seats.
- Professional: 10 seats.
- **Downgrade:** Existing memberships are preserved. Any seats exceeding the new tier limit (ordered by newest `created_at`) are automatically restricted to read-only status until seats are re-allocated by the Owner.

---

## 7. Security & Defenses

1. **SSRF Defense (`UrlPollAdapter`):**
   - Protocol restricted to `http` and `https`.
   - DNS resolution filters out private (RFC 1918), loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), and cloud metadata IP ranges (`169.254.169.254`).
   - Resolved IP is pinned to prevent DNS rebinding.
   - Redirects re-validate the target IP before following.
   - Max body size capped at 5 MB; timeouts capped at 10 seconds; robots.txt checked.
2. **Prompt Injection & Grounding (`ai_assistant`):**
   - Untrusted user and SOP text are encapsulated within isolation delimiters.
   - Assistant model has no function-calling or destructive tools.
   - Strict business/compliance scope guard redirects off-topic or adversarial prompts.
3. **API Keys (`/api/v1`):**
   - Tokens use `secrets.token_urlsafe(32)`. Only `prefix` (first 8 chars) is visible after generation; full key is hashed using `hashlib.sha256`.
   - Cookies are strictly rejected on `/api/v1` (keys only).
   - Rate limit: 60 requests/minute per key with HTTP 429 + `Retry-After`.

---

## 8. Tunable Constants (`app/feature_options.py`)

- `POLLER_MAX_BODY_BYTES = 5 * 1024 * 1024` (5 MB)
- `POLLER_TIMEOUT_SECONDS = 10`
- `POLLER_MIN_HOST_INTERVAL_SECONDS = 10`
- `API_KEY_RATE_LIMIT_PER_MINUTE = 60`
- `DEFAULT_REMINDER_LEAD_DAYS = [14, 7, 1]`
- `ASSISTANT_BURST_LIMIT_PER_MINUTE = 10`
- `ASSISTANT_RETRIEVAL_TOP_K = 3`
- `ASSISTANT_DISTANCE_THRESHOLD = 0.85`
- `ADJUSTED_SCORE_SEVERITY_WEIGHTS = {"high": 1.0, "medium": 0.5, "low": 0.2}`
