"""SQLite persistence layer with versioned migrations, workspace scoping, and usage ledgers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS company_profiles (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry TEXT NOT NULL,
    country TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    company_profile_id TEXT NOT NULL REFERENCES company_profiles(id),
    filename TEXT NOT NULL,
    text TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS action_plans (
    id TEXT PRIMARY KEY,
    company_profile_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watcher_results (
    cache_key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SCHEMA_V2 = """
-- Users & Workspaces
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    full_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memberships (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, workspace_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Subscriptions & Lifecycle Events
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT UNIQUE NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscription_events (
    id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_plan TEXT,
    new_plan TEXT,
    old_status TEXT,
    new_status TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);

-- Metering & Usage Ledgers
CREATE TABLE IF NOT EXISTS usage_counters (
    workspace_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    window_start TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(workspace_id, metric, window_start)
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    workspace_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL, -- 'reserved', 'committed', 'released'
    ref TEXT,
    created_at TEXT NOT NULL
);

-- Checklist Items
CREATE TABLE IF NOT EXISTS checklist_items (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    company_profile_id TEXT NOT NULL,
    title TEXT NOT NULL,
    tier TEXT NOT NULL,
    reason TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    done_at TEXT,
    created_at TEXT NOT NULL
);

-- Webhook Idempotency
CREATE TABLE IF NOT EXISTS webhook_events (
    provider_event_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    payload TEXT NOT NULL,
    processed_at TEXT NOT NULL
);
"""

SCHEMA_V3 = """
-- Regulations & Versions
CREATE TABLE IF NOT EXISTS regulations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT 'Bangladesh',
    sector TEXT,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regulation_versions (
    id TEXT PRIMARY KEY,
    regulation_id TEXT NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
    version_label TEXT NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    effective_date TEXT,
    status TEXT NOT NULL DEFAULT 'published', -- 'draft', 'pending_review', 'published'
    is_sample INTEGER NOT NULL DEFAULT 0,
    published_by TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regulation_sources (
    id TEXT PRIMARY KEY,
    regulation_id TEXT REFERENCES regulations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'url_poll', -- 'manual', 'url_poll'
    url TEXT,
    poll_interval INTEGER NOT NULL DEFAULT 86400,
    enabled INTEGER NOT NULL DEFAULT 0,
    last_checked TEXT,
    last_hash TEXT,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regulatory_changes (
    id TEXT PRIMARY KEY,
    regulation_id TEXT NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
    from_version_id TEXT NOT NULL REFERENCES regulation_versions(id),
    to_version_id TEXT NOT NULL REFERENCES regulation_versions(id),
    summary TEXT NOT NULL,
    change_type TEXT NOT NULL DEFAULT 'Amendment',
    obligations TEXT NOT NULL, -- JSON array of string obligations
    tags TEXT NOT NULL DEFAULT '[]', -- JSON array of string tags
    detected_at TEXT NOT NULL,
    UNIQUE(from_version_id, to_version_id)
);

CREATE TABLE IF NOT EXISTS news_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    sector TEXT,
    jurisdiction TEXT NOT NULL DEFAULT 'Bangladesh',
    published_at TEXT NOT NULL,
    source_url TEXT,
    regulation_id TEXT REFERENCES regulations(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_subscriptions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    regulation_id TEXT NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE(workspace_id, regulation_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    link TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'in_app', -- 'in_app', 'email'
    dedupe_key TEXT UNIQUE,
    read_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    email_enabled INTEGER NOT NULL DEFAULT 1,
    in_app_enabled INTEGER NOT NULL DEFAULT 1,
    frequency TEXT NOT NULL DEFAULT 'instant', -- 'instant', 'daily_digest'
    created_at TEXT NOT NULL,
    UNIQUE(workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL, -- 'email', 'webhook'
    destination TEXT NOT NULL,
    payload TEXT NOT NULL, -- JSON
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'sent', 'failed'
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    payload TEXT NOT NULL, -- JSON
    run_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'dead_letter'
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until TEXT,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deadlines (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    due_date TEXT NOT NULL, -- YYYY-MM-DD
    source_type TEXT NOT NULL DEFAULT 'manual', -- 'manual', 'regulation'
    regulation_id TEXT REFERENCES regulations(id),
    checklist_item_id TEXT REFERENCES checklist_items(id),
    status TEXT NOT NULL DEFAULT 'active', -- 'pending_review', 'active', 'completed'
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminder_log (
    id TEXT PRIMARY KEY,
    deadline_id TEXT NOT NULL REFERENCES deadlines(id) ON DELETE CASCADE,
    lead_days INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    UNIQUE(deadline_id, lead_days)
);

CREATE TABLE IF NOT EXISTS assistant_threads (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assistant_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES assistant_threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- 'user', 'assistant'
    content TEXT NOT NULL,
    citations TEXT NOT NULL DEFAULT '[]', -- JSON
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invites (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    accepted_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id),
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}', -- JSON
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL, -- 'finding', 'checklist_item'
    resource_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS finding_reviews (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    status TEXT NOT NULL, -- 'approved', 'rejected', 'edited'
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    note TEXT,
    edited_citation TEXT,
    reviewed_at TEXT NOT NULL,
    UNIQUE(workspace_id, plan_id, finding_id)
);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT NOT NULL DEFAULT '["read"]',
    last_used_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'standard', -- 'standard', 'priority', 'urgent'
    status TEXT NOT NULL DEFAULT 'open', -- 'open', 'in_progress', 'resolved'
    created_at TEXT NOT NULL
);
"""

SCHEMA_V5 = """
CREATE TABLE IF NOT EXISTS law_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    crawl_config TEXT NOT NULL DEFAULT '{}',
    rate_limit REAL NOT NULL DEFAULT 1.0,
    last_run_at TEXT,
    last_status TEXT
);

CREATE TABLE IF NOT EXISTS laws (
    id TEXT PRIMARY KEY,
    canonical_title_en TEXT NOT NULL,
    canonical_title_bn TEXT,
    act_number TEXT,
    year INTEGER,
    law_type TEXT NOT NULL, -- 'act', 'ordinance', 'sro', 'rule', 'circular', 'order', 'gazette_notice'
    issuing_body TEXT NOT NULL,
    language_available TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'in_force', -- 'in_force', 'amended', 'repealed', 'unknown'
    status_confidence REAL NOT NULL DEFAULT 1.0,
    domain_tags TEXT NOT NULL DEFAULT '[]', -- JSON array of tags
    summary_ai TEXT,
    summary_verified INTEGER NOT NULL DEFAULT 0,
    publish_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'pending_review', 'published', 'rejected'
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS law_versions (
    id TEXT PRIMARY KEY,
    law_id TEXT NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    version_hash TEXT NOT NULL,
    source_url TEXT,
    fetched_at TEXT NOT NULL,
    extraction_method TEXT NOT NULL DEFAULT 'text', -- 'text', 'ocr_gemini', 'ocr_tesseract'
    ocr_quality REAL,
    raw_text_path TEXT,
    is_current INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS law_sections (
    id TEXT PRIMARY KEY,
    law_version_id TEXT NOT NULL REFERENCES law_versions(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES law_sections(id) ON DELETE SET NULL,
    level TEXT NOT NULL, -- 'chapter', 'section', 'subsection', 'schedule'
    number_label TEXT NOT NULL,
    heading TEXT,
    text TEXT NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS law_relations (
    id TEXT PRIMARY KEY,
    from_law_id TEXT NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    to_law_id TEXT NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    relation TEXT NOT NULL -- 'amends', 'repeals', 'supersedes', 'refers_to', 'implements'
);

CREATE TABLE IF NOT EXISTS law_ingest_runs (
    id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES law_sources(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    discovered INTEGER NOT NULL DEFAULT 0,
    new INTEGER NOT NULL DEFAULT 0,
    changed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    cost_estimate REAL NOT NULL DEFAULT 0.0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS law_watchlist (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    law_id TEXT NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, user_id, law_id)
);

CREATE TABLE IF NOT EXISTS law_review_queue (
    id TEXT PRIMARY KEY,
    law_id TEXT NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_by TEXT REFERENCES users(id),
    resolution TEXT, -- 'approved', 'rejected'
    resolved_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS law_sections_fts USING fts5(
    section_id UNINDEXED,
    law_id UNINDEXED,
    version_id UNINDEXED,
    heading,
    text,
    number_label
);
"""

SCHEMA_V6 = """
CREATE TABLE IF NOT EXISTS alert_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL, -- 'info', 'low', 'medium', 'high', 'critical'
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    version_hash TEXT,
    payload TEXT NOT NULL, -- JSON
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_events_ws_type ON alert_events(workspace_id, event_type);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    alert_event_id TEXT NOT NULL REFERENCES alert_events(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    recipient_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL, -- 'pending', 'held', 'sent', 'partially_failed', 'failed', 'digested', 'acknowledged', 'escalated', 'expired'
    held_until TEXT,
    ack_required INTEGER NOT NULL DEFAULT 0,
    acked_at TEXT,
    acked_via TEXT, -- 'in_app', 'email', 'sms', 'whatsapp'
    escalation_level INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_ws_recipient ON alerts(workspace_id, recipient_user_id, status);

CREATE TABLE IF NOT EXISTS alert_deliveries (
    id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    channel TEXT NOT NULL, -- 'in_app', 'email', 'sms', 'whatsapp', 'telegram', 'slack', 'web_push'
    provider TEXT NOT NULL,
    status TEXT NOT NULL, -- 'queued', 'sent', 'delivered', 'read', 'failed', 'rejected'
    provider_message_id TEXT,
    error_code TEXT,
    segments INTEGER NOT NULL DEFAULT 1,
    cost_estimate REAL NOT NULL DEFAULT 0.0,
    attempt INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_deliveries_alert ON alert_deliveries(alert_id);

CREATE TABLE IF NOT EXISTS user_channels (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL, -- 'email', 'sms', 'whatsapp', 'telegram', 'slack', 'web_push'
    address TEXT NOT NULL, -- phone number or email address
    display_address TEXT, -- masked e.g. +8801X****XXXX
    verified_at TEXT,
    whatsapp_opt_in_at TEXT,
    opted_out_at TEXT,
    locale TEXT NOT NULL DEFAULT 'en', -- 'bn' | 'en'
    PRIMARY KEY(user_id, channel)
);

CREATE TABLE IF NOT EXISTS alert_preferences (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(user_id, event_type, channel)
);
"""

SCHEMA_V7 = """
CREATE TABLE IF NOT EXISTS compliance_owners (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    domain_tag TEXT NOT NULL,
    primary_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    backup_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY(workspace_id, domain_tag)
);

CREATE TABLE IF NOT EXISTS workspace_alert_settings (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    quiet_hours_start TEXT NOT NULL DEFAULT '22:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '08:00',
    timezone TEXT NOT NULL DEFAULT 'Asia/Dhaka',
    weekend_days TEXT NOT NULL DEFAULT '[4, 5]', -- JSON list e.g. [4, 5] for Fri/Sat
    escalation_critical_hours INTEGER NOT NULL DEFAULT 4,
    escalation_high_hours INTEGER NOT NULL DEFAULT 24,
    monthly_sms_cap INTEGER NOT NULL DEFAULT 100,
    monthly_whatsapp_cap INTEGER NOT NULL DEFAULT 100,
    digest_hour_bst INTEGER NOT NULL DEFAULT 9,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sms_otps (
    id TEXT PRIMARY KEY,
    phone_number TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sms_otps_user ON sms_otps(user_id, phone_number);

CREATE TABLE IF NOT EXISTS short_links (
    code TEXT PRIMARY KEY,
    original_url TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL
);
"""

SCHEMA_V8 = """
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id);
"""

LEGACY_WORKSPACE_ID = "workspace_legacy"
LEGACY_USER_ID = "user_legacy"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._migrate()

    def get_schema_version(self) -> int:
        row = self._fetchone("SELECT MAX(version) as ver FROM schema_version")
        return int(row["ver"]) if row and row["ver"] is not None else 0

    def close(self) -> None:
        self._conn.close()

    def _execute(self, sql: str, params: tuple | list = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _fetchone(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetchall(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # -----------------------------------------------------------------------
    # Versioned Migrations
    # -----------------------------------------------------------------------
    def _migrate(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        self._conn.commit()

        row = self._conn.execute("SELECT MAX(version) as ver FROM schema_version").fetchone()
        current_ver = row["ver"] or 0

        if current_ver < 1:
            self._conn.executescript(SCHEMA_V1)
            self._conn.execute("INSERT INTO schema_version VALUES (1, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 1

        if current_ver < 2:
            self._conn.executescript(SCHEMA_V2)

            # Add workspace_id columns to existing tables if not present
            for table in ("company_profiles", "documents", "action_plans"):
                cols = [c[1] for c in self._conn.execute(f"PRAGMA table_info({table})").fetchall()]
                if "workspace_id" not in cols:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id TEXT")

            # Seed legacy workspace and subscription for backwards compatibility
            now = utcnow()
            self._conn.execute(
                "INSERT OR IGNORE INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
                (LEGACY_WORKSPACE_ID, "Legacy Default Workspace", now),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO subscriptions (id, workspace_id, plan_id, status, period_start, period_end, cancel_at_period_end, created_at) "
                "VALUES (?, ?, 'professional', 'active', ?, '2099-01-01T00:00:00Z', 0, ?)",
                (f"sub_{LEGACY_WORKSPACE_ID}", LEGACY_WORKSPACE_ID, now, now),
            )

            # Assign pre-existing orphan rows to legacy workspace
            for table in ("company_profiles", "documents", "action_plans"):
                self._conn.execute(
                    f"UPDATE {table} SET workspace_id = ? WHERE workspace_id IS NULL OR workspace_id = ''",
                    (LEGACY_WORKSPACE_ID,),
                )

            self._conn.execute("INSERT INTO schema_version VALUES (2, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 2

        if current_ver < 3:
            self._conn.executescript(SCHEMA_V3)

            # Add is_platform_admin to users if not present
            user_cols = [c[1] for c in self._conn.execute("PRAGMA table_info(users)").fetchall()]
            if "is_platform_admin" not in user_cols:
                self._conn.execute("ALTER TABLE users ADD COLUMN is_platform_admin INTEGER NOT NULL DEFAULT 0")

            # Seed default NBR VAT SRO regulation and versions if not present
            reg_id = "nbr-vat-sro-4.2"
            now = utcnow()
            existing_reg = self._conn.execute("SELECT id FROM regulations WHERE id = ?", (reg_id,)).fetchone()
            if not existing_reg:
                self._conn.execute(
                    "INSERT INTO regulations (id, title, country, sector, description, created_at) "
                    "VALUES (?, ?, 'Bangladesh', 'Logistics / Trade', 'NBR Value Added Tax Filing Deadline & Officer Order', ?)",
                    (reg_id, "NBR VAT SRO Clause 4.2", now),
                )
                from pathlib import Path
                base_dir = Path(__file__).resolve().parent.parent
                reg_dir = base_dir / "data" / "regulations"
                before_path = reg_dir / "regulation_before.txt"
                after_path = reg_dir / "regulation_after.txt"
                before_text = before_path.read_text(encoding="utf-8").strip() if before_path.exists() else ""
                after_text = after_path.read_text(encoding="utf-8").strip() if after_path.exists() else ""

                hash_v1 = hashlib.sha256(before_text.encode("utf-8")).hexdigest()
                hash_v2 = hashlib.sha256(after_text.encode("utf-8")).hexdigest()

                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, 'v1.0 (Original)', ?, ?, 'published', 1, ?, ?)",
                    (f"{reg_id}_v1", reg_id, before_text, hash_v1, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, 'v2.0 (Amendment)', ?, ?, 'published', 1, ?, ?)",
                    (f"{reg_id}_v2", reg_id, after_text, hash_v2, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulatory_changes (id, regulation_id, from_version_id, to_version_id, summary, change_type, obligations, tags, detected_at) "
                    "VALUES (?, ?, ?, ?, ?, 'Amendment', ?, ?, ?)",
                    (
                        f"change_{reg_id}_v1_v2",
                        reg_id,
                        f"{reg_id}_v1",
                        f"{reg_id}_v2",
                        "Filing deadline reduced from 30 to 15 days; certified VAT Filing Officer designation is now mandatory.",
                        json.dumps(["File VAT return within 15 days", "Designate certified VAT Filing Officer"]),
                        json.dumps(["VAT", "Logistics", "Taxation"]),
                        now,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO news_items (id, title, content, sector, jurisdiction, published_at, regulation_id, created_at) "
                    "VALUES (?, ?, ?, 'Logistics / Trade', 'Bangladesh', ?, ?, ?)",
                    (
                        f"news_{reg_id}",
                        "NBR Issues SRO 4.2: 15-Day VAT Filing Window Mandatory for Bangladeshi Businesses",
                        "The National Board of Revenue has shortened the monthly VAT return deadline from 30 days to 15 days. Companies must appoint a designated VAT Filing Officer.",
                        now,
                        reg_id,
                        now,
                    ),
                )

            self._conn.execute("INSERT INTO schema_version VALUES (3, ?)", (now,))
            self._conn.commit()
            current_ver = 3

        if current_ver < 4:
            # 1. Add supabase_user_id to users if not present
            user_cols = [c[1] for c in self._conn.execute("PRAGMA table_info(users)").fetchall()]
            if "supabase_user_id" not in user_cols:
                self._conn.execute("ALTER TABLE users ADD COLUMN supabase_user_id TEXT")
                self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase_user_id ON users(supabase_user_id) WHERE supabase_user_id IS NOT NULL")

            # 2. Add OCR metadata columns to documents if not present
            doc_cols = [c[1] for c in self._conn.execute("PRAGMA table_info(documents)").fetchall()]
            if "extraction_method" not in doc_cols:
                self._conn.execute("ALTER TABLE documents ADD COLUMN extraction_method TEXT DEFAULT 'text'")
            if "ocr_confidence" not in doc_cols:
                self._conn.execute("ALTER TABLE documents ADD COLUMN ocr_confidence REAL")
            if "ocr_notes" not in doc_cols:
                self._conn.execute("ALTER TABLE documents ADD COLUMN ocr_notes TEXT")

            self._conn.execute("INSERT INTO schema_version VALUES (4, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 4

        if current_ver < 5:
            self._conn.executescript(SCHEMA_V5)

            # Seed default official law sources from JSON if law_sources table is empty
            count_row = self._conn.execute("SELECT COUNT(*) as c FROM law_sources").fetchone()
            count = count_row["c"] if count_row else 0
            if count == 0:
                from pathlib import Path
                seed_file = Path(__file__).resolve().parent.parent / "data" / "law_sources.json"
                if seed_file.exists():
                    try:
                        sources_data = json.loads(seed_file.read_text(encoding="utf-8"))
                        for src in sources_data:
                            self._conn.execute(
                                "INSERT OR IGNORE INTO law_sources (id, name, base_url, source_type, enabled, crawl_config, rate_limit, last_status) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    src["id"],
                                    src["name"],
                                    src["base_url"],
                                    src["source_type"],
                                    1 if src.get("enabled") else 0,
                                    json.dumps(src.get("crawl_config", {})),
                                    float(src.get("rate_limit", 1.0)),
                                    src.get("last_status", "configured"),
                                ),
                            )
                    except Exception as e:
                        logger.warning(f"Could not seed law sources: {e}")

            self._conn.execute("INSERT INTO schema_version VALUES (5, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 5

        if current_ver < 6:
            self._conn.executescript(SCHEMA_V6)
            # Add additive columns to notifications if not present
            notif_cols = [c[1] for c in self._conn.execute("PRAGMA table_info(notifications)").fetchall()]
            if "severity" not in notif_cols:
                self._conn.execute("ALTER TABLE notifications ADD COLUMN severity TEXT NOT NULL DEFAULT 'info'")
            if "event_type" not in notif_cols:
                self._conn.execute("ALTER TABLE notifications ADD COLUMN event_type TEXT NOT NULL DEFAULT 'general'")
            if "ack_required" not in notif_cols:
                self._conn.execute("ALTER TABLE notifications ADD COLUMN ack_required INTEGER NOT NULL DEFAULT 0")
            if "acked_at" not in notif_cols:
                self._conn.execute("ALTER TABLE notifications ADD COLUMN acked_at TEXT")
            if "deep_link" not in notif_cols:
                self._conn.execute("ALTER TABLE notifications ADD COLUMN deep_link TEXT")
            if "action_buttons" not in notif_cols:
                self._conn.execute("ALTER TABLE notifications ADD COLUMN action_buttons TEXT")

            self._conn.execute("INSERT INTO schema_version VALUES (6, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 6

        if current_ver < 7:
            self._conn.executescript(SCHEMA_V7)
            self._conn.execute("INSERT INTO schema_version VALUES (7, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 7

        if current_ver < 8:
            self._conn.executescript(SCHEMA_V8)
            self._conn.execute("INSERT INTO schema_version VALUES (8, ?)", (utcnow(),))
            self._conn.commit()
            current_ver = 8

        self._seed_regulations()

    def _seed_regulations(self) -> None:
        now = utcnow()
        with self._lock:
            # 1. NBR VAT SRO Clause 4.2
            reg_id = "nbr-vat-sro-4.2"
            existing_reg = self._conn.execute("SELECT id FROM regulations WHERE id = ?", (reg_id,)).fetchone()
            if not existing_reg:
                self._conn.execute(
                    "INSERT INTO regulations (id, title, country, sector, description, created_at) "
                    "VALUES (?, ?, 'Bangladesh', 'Logistics / Trade', 'NBR Value Added Tax Filing Deadline & Officer Order', ?)",
                    (reg_id, "NBR VAT SRO Clause 4.2", now),
                )
                from pathlib import Path
                base_dir = Path(__file__).resolve().parent.parent
                reg_dir = base_dir / "data" / "regulations"
                before_path = reg_dir / "regulation_before.txt"
                after_path = reg_dir / "regulation_after.txt"
                before_text = before_path.read_text(encoding="utf-8").strip() if before_path.exists() else ""
                after_text = after_path.read_text(encoding="utf-8").strip() if after_path.exists() else ""

                hash_v1 = hashlib.sha256(before_text.encode("utf-8")).hexdigest()
                hash_v2 = hashlib.sha256(after_text.encode("utf-8")).hexdigest()

                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, 'v1.0 (Original)', ?, ?, 'published', 1, ?, ?)",
                    (f"{reg_id}_v1", reg_id, before_text, hash_v1, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, 'v2.0 (Amendment)', ?, ?, 'published', 1, ?, ?)",
                    (f"{reg_id}_v2", reg_id, after_text, hash_v2, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulatory_changes (id, regulation_id, from_version_id, to_version_id, summary, change_type, obligations, tags, detected_at) "
                    "VALUES (?, ?, ?, ?, ?, 'Amendment', ?, ?, ?)",
                    (
                        f"change_{reg_id}_v1_v2",
                        reg_id,
                        f"{reg_id}_v1",
                        f"{reg_id}_v2",
                        "Filing deadline reduced from 30 to 15 days; certified VAT Filing Officer designation is now mandatory.",
                        json.dumps(["File VAT return within 15 days", "Designate certified VAT Filing Officer"]),
                        json.dumps(["VAT", "Logistics", "Taxation"]),
                        now,
                    ),
                )

            # 2. Bangladesh Labor Act (Amendment 2023)
            labor_id = "bangladesh-labor-act-2023"
            existing_labor = self._conn.execute("SELECT id FROM regulations WHERE id = ?", (labor_id,)).fetchone()
            if not existing_labor:
                labor_v1 = (
                    "Section 46 - Maternity Benefit Duration: Every woman employed in an establishment shall be entitled to maternity benefit for a period of 16 weeks (8 weeks before and 8 weeks after delivery), amounting to 112 consecutive days.\n\n"
                    "Section 33 - Grievance Redressal Procedure: Any worker who has any grievance in respect of any matter to which this Act applies may submit their grievance in writing to the employer within 30 days of the occurrence of the grievance. The employer shall investigate and communicate the formal decision within 30 days of receipt of such grievance.\n\n"
                    "Section 89 - Safety Committee & Health Insurance: In every establishment wherein 50 or more workers are ordinarily employed, a Safety Committee shall be constituted. Employers in commercial enterprises may provide voluntary health insurance schemes."
                )
                labor_v2 = (
                    "Section 46 - Maternity Benefit Duration: Every woman employed in an establishment shall be entitled to maternity benefit for a period of 120 consecutive days (60 days preceding delivery and 60 days following delivery). Willful denial or reduction of the 120-day maternity benefit is a punishable statutory offense carrying fines of up to BDT 25,000.\n\n"
                    "Section 33 - Grievance Redressal Procedure: Any worker who has any grievance in respect of any matter to which this Act applies may submit their grievance in writing to the employer within 30 days of the occurrence. The employer shall investigate and communicate the formal decision to the worker within 15 days of receipt of such grievance (reduced from 30 days).\n\n"
                    "Section 89 - Safety Committee & Mandatory Health Insurance: In every establishment wherein 50 or more workers are ordinarily employed, an active Safety Committee must meet monthly. For manufacturing and logistics establishments employing 100 or more permanent workers, the employer must provide mandatory group health and life insurance."
                )
                hash_l1 = hashlib.sha256(labor_v1.encode("utf-8")).hexdigest()
                hash_l2 = hashlib.sha256(labor_v2.encode("utf-8")).hexdigest()

                self._conn.execute(
                    "INSERT INTO regulations (id, title, country, sector, description, created_at) "
                    "VALUES (?, ?, 'Bangladesh', 'Human Resources / Manufacturing', 'Maternity leave extended to 120 days, 15-day grievance investigation timeline, and mandatory group health insurance.', ?)",
                    (labor_id, "Bangladesh Labor Act (Amendment 2023)", now),
                )
                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, '2006 Edition', ?, ?, 'published', 1, ?, ?)",
                    (f"{labor_id}_v1", labor_id, labor_v1, hash_l1, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, '2023 Amendment', ?, ?, 'published', 1, ?, ?)",
                    (f"{labor_id}_v2", labor_id, labor_v2, hash_l2, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulatory_changes (id, regulation_id, from_version_id, to_version_id, summary, change_type, obligations, tags, detected_at) "
                    "VALUES (?, ?, ?, ?, ?, 'Amendment', ?, ?, ?)",
                    (
                        f"change_{labor_id}_v1_v2",
                        labor_id,
                        f"{labor_id}_v1",
                        f"{labor_id}_v2",
                        "Maternity leave expanded from 112 to 120 days; employer grievance investigation deadline shortened to 15 days; mandatory group health insurance for 100+ permanent workers.",
                        json.dumps([
                            "Provide 120 consecutive days of paid maternity benefit (60 days before, 60 days after)",
                            "Investigate worker grievances and communicate formal written decisions within 15 days",
                            "Constitute Safety Committee and provide mandatory group health and life insurance for 100+ permanent workers",
                        ]),
                        json.dumps(["Labor", "HR", "Maternity", "Safety", "Employment"]),
                        now,
                    ),
                )

            # 3. Income Tax Act 2023 (Digital Disallowance)
            tax_id = "income-tax-act-2023"
            existing_tax = self._conn.execute("SELECT id FROM regulations WHERE id = ?", (tax_id,)).fetchone()
            if not existing_tax:
                tax_v1 = (
                    "Section 75 - Return of Income: Every company shall file an income tax return in the prescribed paper form on or before the Tax Day. Electronic return submission is optional.\n\n"
                    "Section 30 - Allowable Business Expenses: Any business expenditure incurred wholly and exclusively for the purpose of the business is tax deductible. Commercial payments up to BDT 500,000 may be disbursed in cash without statutory expense disallowance.\n\n"
                    "Section 35 - Maintenance of Accounts: Every company shall maintain books of accounts and commercial records for a minimum period of 3 years from the end of the relevant assessment year."
                )
                tax_v2 = (
                    "Section 166 - Mandatory Electronic Filing: Every registered private and public limited company, irrespective of turnover, must submit its annual income tax return and audited accounts exclusively through the official NBR E-Tax Portal. Paper submissions are null and void without formal commissioner waiver.\n\n"
                    "Section 55 - Strict Non-Banking Cash Disallowance: No deduction shall be allowed in respect of any commercial payment exceeding BDT 50,000 made otherwise than by banking channel, crossed check, or Bangladesh Bank authorized digital financial service (MFS / NPSB). 100% of non-banking cash payments exceeding BDT 50,000 shall be added back to taxable commercial income.\n\n"
                    "Section 72 - Statutory Document Retention: Every commercial enterprise must maintain and preserve financial ledgers, bank statements, tax invoices, and withholding tax certificates for a minimum mandatory retention period of 6 years."
                )
                hash_t1 = hashlib.sha256(tax_v1.encode("utf-8")).hexdigest()
                hash_t2 = hashlib.sha256(tax_v2.encode("utf-8")).hexdigest()

                self._conn.execute(
                    "INSERT INTO regulations (id, title, country, sector, description, created_at) "
                    "VALUES (?, ?, 'Bangladesh', 'Finance / Accounting', 'Mandatory corporate e-tax return filing, 100% expense disallowance on cash disbursements over BDT 50,000, and 6-year books retention.', ?)",
                    (tax_id, "Bangladesh Income Tax Act 2023", now),
                )
                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, '1984 Ordinance Rules', ?, ?, 'published', 1, ?, ?)",
                    (f"{tax_id}_v1", tax_id, tax_v1, hash_t1, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, status, is_sample, published_at, created_at) "
                    "VALUES (?, ?, '2023 Act Rules', ?, ?, 'published', 1, ?, ?)",
                    (f"{tax_id}_v2", tax_id, tax_v2, hash_t2, now, now),
                )
                self._conn.execute(
                    "INSERT INTO regulatory_changes (id, regulation_id, from_version_id, to_version_id, summary, change_type, obligations, tags, detected_at) "
                    "VALUES (?, ?, ?, ?, ?, 'Amendment', ?, ?, ?)",
                    (
                        f"change_{tax_id}_v1_v2",
                        tax_id,
                        f"{tax_id}_v1",
                        f"{tax_id}_v2",
                        "Mandatory corporate e-filing via NBR portal; 100% tax disallowance on commercial payments over BDT 50,000 not paid via banking/MFS channels; accounting records retention extended to 6 years.",
                        json.dumps([
                            "Submit annual corporate tax return exclusively via NBR e-Tax portal",
                            "Disburse all commercial supplier payments exceeding BDT 50,000 through banking or authorized MFS channels",
                            "Retain statutory books of accounts and invoices for minimum 6 years",
                        ]),
                        json.dumps(["Income Tax", "Banking", "Disallowance", "Accounting"]),
                        now,
                    ),
                )

            self._conn.commit()

    # -----------------------------------------------------------------------
    # Auth, Users & Workspaces
    # -----------------------------------------------------------------------
    def create_user(
        self, email: str, password_hash: str, salt: str, full_name: str | None = None
    ) -> dict[str, Any]:
        user_id = new_id()
        now = utcnow()
        record = {
            "id": user_id,
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "salt": salt,
            "full_name": full_name.strip() if full_name else None,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO users (id, email, password_hash, salt, full_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (record["id"], record["email"], record["password_hash"], record["salt"], record["full_name"], now),
        )
        return record

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    def get_user_by_supabase_id(self, supabase_user_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM users WHERE supabase_user_id = ?", (supabase_user_id,))

    def get_or_create_supabase_user(
        self, supabase_user_id: str, email: str, full_name: str | None = None
    ) -> tuple[dict[str, Any], bool]:
        """Returns (user_dict, is_new_user)."""
        # 1. Look up by supabase_user_id
        user = self.get_user_by_supabase_id(supabase_user_id)
        if user:
            return user, False

        # 2. Look up by email (link legacy or pre-existing user)
        user = self.get_user_by_email(email)
        if user:
            self._execute("UPDATE users SET supabase_user_id = ? WHERE id = ?", (supabase_user_id, user["id"]))
            user["supabase_user_id"] = supabase_user_id
            return user, False

        # 3. Create fresh user row
        user_id = new_id()
        now = utcnow()
        self._execute(
            "INSERT INTO users (id, email, password_hash, salt, full_name, supabase_user_id, created_at) VALUES (?, ?, '', '', ?, ?, ?)",
            (user_id, email.strip().lower(), full_name.strip() if full_name else None, supabase_user_id, now),
        )
        new_user = self.get_user_by_id(user_id)
        assert new_user is not None
        return new_user, True

    def create_workspace(self, name: str) -> dict[str, Any]:
        ws_id = new_id()
        now = utcnow()
        record = {"id": ws_id, "name": name.strip(), "created_at": now}
        self._execute("INSERT INTO workspaces (id, name, created_at) VALUES (?, ?, ?)", (ws_id, record["name"], now))
        return record

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM workspaces ORDER BY created_at ASC")

    def create_membership(self, user_id: str, workspace_id: str, role: str = "owner") -> dict[str, Any]:
        mem_id = new_id()
        now = utcnow()
        record = {"id": mem_id, "user_id": user_id, "workspace_id": workspace_id, "role": role, "created_at": now}
        self._execute(
            "INSERT INTO memberships (id, user_id, workspace_id, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (mem_id, user_id, workspace_id, role, now),
        )
        return record

    def get_user_workspace(self, user_id: str) -> dict[str, Any] | None:
        """Returns the primary workspace and role for a user."""
        sql = """
        SELECT w.*, m.role
        FROM workspaces w
        JOIN memberships m ON m.workspace_id = w.id
        WHERE m.user_id = ?
        ORDER BY w.created_at ASC
        LIMIT 1
        """
        return self._fetchone(sql, (user_id,))

    def create_session(self, session_id: str, user_id: str, workspace_id: str, expires_at: str) -> None:
        now = utcnow()
        self._execute(
            "INSERT INTO sessions (id, user_id, workspace_id, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, workspace_id, expires_at, now),
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        now = utcnow()
        return self._fetchone("SELECT * FROM sessions WHERE id = ? AND expires_at > ?", (session_id, now))

    def delete_session(self, session_id: str) -> None:
        self._execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def update_session_expiry(self, session_id: str, new_expires_at: str) -> None:
        self._execute("UPDATE sessions SET expires_at = ? WHERE id = ?", (new_expires_at, session_id))

    def update_session_workspace(self, session_id: str, new_workspace_id: str) -> None:
        self._execute("UPDATE sessions SET workspace_id = ? WHERE id = ?", (new_workspace_id, session_id))

    def delete_user_sessions(self, user_id: str) -> None:
        self._execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    # -----------------------------------------------------------------------
    # Subscriptions & Events
    # -----------------------------------------------------------------------
    def get_subscription(self, workspace_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM subscriptions WHERE workspace_id = ?", (workspace_id,))

    def create_subscription(
        self,
        workspace_id: str,
        plan_id: str,
        status: str,
        period_start: str,
        period_end: str,
        cancel_at_period_end: bool = False,
    ) -> dict[str, Any]:
        sub_id = new_id()
        now = utcnow()
        self._execute(
            "INSERT INTO subscriptions (id, workspace_id, plan_id, status, period_start, period_end, cancel_at_period_end, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sub_id, workspace_id, plan_id, status, period_start, period_end, 1 if cancel_at_period_end else 0, now),
        )
        return {
            "id": sub_id,
            "workspace_id": workspace_id,
            "plan_id": plan_id,
            "status": status,
            "period_start": period_start,
            "period_end": period_end,
            "cancel_at_period_end": cancel_at_period_end,
            "created_at": now,
        }

    def update_subscription(
        self,
        workspace_id: str,
        plan_id: str,
        status: str,
        period_start: str,
        period_end: str,
        cancel_at_period_end: bool,
    ) -> None:
        self._execute(
            "UPDATE subscriptions SET plan_id = ?, status = ?, period_start = ?, period_end = ?, cancel_at_period_end = ? WHERE workspace_id = ?",
            (plan_id, status, period_start, period_end, 1 if cancel_at_period_end else 0, workspace_id),
        )

    def log_subscription_event(
        self,
        subscription_id: str,
        workspace_id: str,
        event_type: str,
        old_plan: str | None = None,
        new_plan: str | None = None,
        old_status: str | None = None,
        new_status: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        event_id = new_id()
        now = utcnow()
        self._execute(
            "INSERT INTO subscription_events (id, subscription_id, workspace_id, event_type, old_plan, new_plan, old_status, new_status, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                subscription_id,
                workspace_id,
                event_type,
                old_plan,
                new_plan,
                old_status,
                new_status,
                json.dumps(metadata or {}),
                now,
            ),
        )

    # -----------------------------------------------------------------------
    # Usage Counters & Idempotent Usage Events
    # -----------------------------------------------------------------------
    def get_usage_counter(self, workspace_id: str, metric: str, window_start: str) -> int:
        row = self._fetchone(
            "SELECT used FROM usage_counters WHERE workspace_id = ? AND metric = ? AND window_start = ?",
            (workspace_id, metric, window_start),
        )
        return int(row["used"]) if row else 0

    def increment_usage_counter(self, workspace_id: str, metric: str, window_start: str, amount: int = 1) -> int:
        """Atomic upsert incrementing usage counter; returns new used amount."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage_counters (workspace_id, metric, window_start, used) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(workspace_id, metric, window_start) DO UPDATE SET used = used + excluded.used",
                (workspace_id, metric, window_start, amount),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT used FROM usage_counters WHERE workspace_id = ? AND metric = ? AND window_start = ?",
                (workspace_id, metric, window_start),
            ).fetchone()
        return int(row["used"]) if row else amount

    def decrement_usage_counter(self, workspace_id: str, metric: str, window_start: str, amount: int = 1) -> int:
        with self._lock:
            self._conn.execute(
                "UPDATE usage_counters SET used = MAX(0, used - ?) WHERE workspace_id = ? AND metric = ? AND window_start = ?",
                (amount, workspace_id, metric, window_start),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT used FROM usage_counters WHERE workspace_id = ? AND metric = ? AND window_start = ?",
                (workspace_id, metric, window_start),
            ).fetchone()
        return int(row["used"]) if row else 0

    def get_all_usage_counters(self, workspace_id: str, window_start: str) -> dict[str, int]:
        rows = self._fetchall(
            "SELECT metric, used FROM usage_counters WHERE workspace_id = ? AND window_start = ?",
            (workspace_id, window_start),
        )
        return {r["metric"]: int(r["used"]) for r in rows}

    def create_usage_event(
        self, idempotency_key: str, workspace_id: str, metric: str, amount: int, status: str, ref: str | None = None
    ) -> bool:
        """Returns True if inserted, False if idempotency_key already exists."""
        event_id = new_id()
        now = utcnow()
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO usage_events (id, idempotency_key, workspace_id, metric, amount, status, ref, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, idempotency_key, workspace_id, metric, amount, status, ref, now),
                )
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_usage_event(self, idempotency_key: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM usage_events WHERE idempotency_key = ?", (idempotency_key,))

    def update_usage_event_status(self, idempotency_key: str, status: str) -> None:
        self._execute("UPDATE usage_events SET status = ? WHERE idempotency_key = ?", (status, idempotency_key))

    # Live Gauge Counts
    def count_business_profiles(self, workspace_id: str) -> int:
        row = self._fetchone("SELECT COUNT(*) as cnt FROM company_profiles WHERE workspace_id = ?", (workspace_id,))
        return int(row["cnt"]) if row else 0

    def count_workspace_members(self, workspace_id: str) -> int:
        row = self._fetchone("SELECT COUNT(*) as cnt FROM memberships WHERE workspace_id = ?", (workspace_id,))
        return int(row["cnt"]) if row else 0

    def count_monitored_sources(self, workspace_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) as cnt FROM monitor_subscriptions WHERE workspace_id = ?",
            (workspace_id,),
        )
        return int(row["cnt"]) if row else 0

    # -----------------------------------------------------------------------
    # Personalized Checklist
    # -----------------------------------------------------------------------
    def save_checklist_items(self, workspace_id: str, company_profile_id: str, items: list[dict[str, Any]]) -> None:
        now = utcnow()
        with self._lock:
            for item in items:
                self._conn.execute(
                    "INSERT INTO checklist_items (id, workspace_id, company_profile_id, title, tier, reason, done, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                    (new_id(), workspace_id, company_profile_id, item["title"], item["tier"], item["reason"], now),
                )
            self._conn.commit()

    def get_checklist_items(self, workspace_id: str, company_profile_id: str | None = None) -> list[dict[str, Any]]:
        if company_profile_id:
            sql = "SELECT * FROM checklist_items WHERE workspace_id = ? AND company_profile_id = ? ORDER BY done ASC, created_at ASC"
            return self._fetchall(sql, (workspace_id, company_profile_id))
        return self._fetchall(
            "SELECT * FROM checklist_items WHERE workspace_id = ? ORDER BY done ASC, created_at ASC", (workspace_id,)
        )

    def update_checklist_item(self, item_id: str, workspace_id: str, done: bool) -> dict[str, Any] | None:
        done_val = 1 if done else 0
        done_at = utcnow() if done else None
        self._execute(
            "UPDATE checklist_items SET done = ?, done_at = ? WHERE id = ? AND workspace_id = ?",
            (done_val, done_at, item_id, workspace_id),
        )
        return self._fetchone("SELECT * FROM checklist_items WHERE id = ? AND workspace_id = ?", (item_id, workspace_id))

    # -----------------------------------------------------------------------
    # Webhook Idempotency
    # -----------------------------------------------------------------------
    def record_webhook_event(self, provider_event_id: str, provider: str, payload: dict) -> bool:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO webhook_events (provider_event_id, provider, payload, processed_at) VALUES (?, ?, ?, ?)",
                    (provider_event_id, provider, json.dumps(payload), utcnow()),
                )
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def is_webhook_processed(self, provider_event_id: str) -> bool:
        return self._fetchone("SELECT 1 FROM webhook_events WHERE provider_event_id = ?", (provider_event_id,)) is not None

    # -----------------------------------------------------------------------
    # Company profiles (Workspace Scoped)
    # -----------------------------------------------------------------------
    def create_company(
        self,
        company_name: str,
        industry: str,
        country: str,
        description: str | None,
        workspace_id: str = LEGACY_WORKSPACE_ID,
    ) -> dict[str, Any]:
        record = {
            "id": new_id(),
            "company_name": company_name,
            "industry": industry,
            "country": country,
            "description": description,
            "created_at": utcnow(),
            "workspace_id": workspace_id,
        }
        self._execute(
            "INSERT INTO company_profiles (id, company_name, industry, country, description, created_at, workspace_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"],
                record["company_name"],
                record["industry"],
                record["country"],
                record["description"],
                record["created_at"],
                record["workspace_id"],
            ),
        )
        return record

    def get_company(self, company_id: str, workspace_id: str | None = None) -> dict[str, Any] | None:
        if workspace_id:
            return self._fetchone(
                "SELECT * FROM company_profiles WHERE id = ? AND workspace_id = ?", (company_id, workspace_id)
            )
        return self._fetchone("SELECT * FROM company_profiles WHERE id = ?", (company_id,))

    def list_companies(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM company_profiles WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,))

    # -----------------------------------------------------------------------
    # Documents (Workspace Scoped)
    # -----------------------------------------------------------------------
    def create_document(
        self,
        company_profile_id: str,
        filename: str,
        text: str,
        chunk_count: int,
        doc_id: str,
        workspace_id: str = LEGACY_WORKSPACE_ID,
        extraction_method: str = "text",
        ocr_confidence: float | None = None,
        ocr_notes: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": doc_id,
            "company_profile_id": company_profile_id,
            "filename": filename,
            "text": text,
            "chunk_count": chunk_count,
            "created_at": utcnow(),
            "workspace_id": workspace_id,
            "extraction_method": extraction_method,
            "ocr_confidence": ocr_confidence,
            "ocr_notes": ocr_notes,
        }
        self._execute(
            "INSERT INTO documents (id, company_profile_id, filename, text, chunk_count, created_at, workspace_id, extraction_method, ocr_confidence, ocr_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"],
                record["company_profile_id"],
                record["filename"],
                record["text"],
                record["chunk_count"],
                record["created_at"],
                record["workspace_id"],
                record["extraction_method"],
                record["ocr_confidence"],
                record["ocr_notes"],
            ),
        )
        return record

    def get_document(self, document_id: str, workspace_id: str | None = None) -> dict[str, Any] | None:
        if workspace_id:
            return self._fetchone(
                "SELECT * FROM documents WHERE id = ? AND workspace_id = ?", (document_id, workspace_id)
            )
        return self._fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))

    def list_documents(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM documents WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,)
        )

    # -----------------------------------------------------------------------
    # Action plans (Workspace Scoped with Retention)
    # -----------------------------------------------------------------------
    def save_action_plan(
        self, plan: dict[str, Any], company_profile_id: str, document_id: str, workspace_id: str = LEGACY_WORKSPACE_ID
    ) -> None:
        self._execute(
            "INSERT INTO action_plans (id, company_profile_id, document_id, data, created_at, workspace_id) VALUES (?, ?, ?, ?, ?, ?)",
            (plan["id"], company_profile_id, document_id, json.dumps(plan), plan["created_at"], workspace_id),
        )

    def get_action_plan(self, plan_id: str, workspace_id: str | None = None) -> dict[str, Any] | None:
        if workspace_id:
            row = self._fetchone(
                "SELECT data FROM action_plans WHERE id = ? AND workspace_id = ?", (plan_id, workspace_id)
            )
        else:
            row = self._fetchone("SELECT data FROM action_plans WHERE id = ?", (plan_id,))
        return json.loads(row["data"]) if row else None

    def list_action_plans(self, workspace_id: str, cutoff_date: str | None = None) -> list[dict[str, Any]]:
        """Lists plans for workspace, filtering out items older than cutoff_date."""
        if cutoff_date:
            sql = "SELECT data FROM action_plans WHERE workspace_id = ? AND created_at >= ? ORDER BY created_at DESC"
            rows = self._fetchall(sql, (workspace_id, cutoff_date))
        else:
            sql = "SELECT data FROM action_plans WHERE workspace_id = ? ORDER BY created_at DESC"
            rows = self._fetchall(sql, (workspace_id,))
        return [json.loads(r["data"]) for r in rows]

    def purge_expired_action_plans(self, cutoff_date: str, workspace_id: str | None = None) -> int:
        with self._lock:
            if workspace_id:
                cur = self._conn.execute(
                    "DELETE FROM action_plans WHERE workspace_id = ? AND created_at < ?", (workspace_id, cutoff_date)
                )
            else:
                cur = self._conn.execute("DELETE FROM action_plans WHERE created_at < ?", (cutoff_date,))
            self._conn.commit()
            return cur.rowcount

    # -----------------------------------------------------------------------
    # Watcher cache
    # -----------------------------------------------------------------------
    def get_watcher_result(self, cache_key: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT data FROM watcher_results WHERE cache_key = ?", (cache_key,))
        return json.loads(row["data"]) if row else None

    def save_watcher_result(self, cache_key: str, data: dict[str, Any]) -> None:
        self._execute(
            "INSERT OR REPLACE INTO watcher_results VALUES (?, ?, ?)",
            (cache_key, json.dumps(data), utcnow()),
        )

    # -----------------------------------------------------------------------
    # Platform Admin
    # -----------------------------------------------------------------------
    def is_platform_admin(self, user_id: str) -> bool:
        row = self._fetchone("SELECT is_platform_admin FROM users WHERE id = ?", (user_id,))
        return bool(row["is_platform_admin"]) if row else False

    def set_platform_admin(self, user_id_or_email: str, is_admin: bool = True) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE users SET is_platform_admin = ? WHERE id = ? OR email = ?",
                (1 if is_admin else 0, user_id_or_email, user_id_or_email.strip().lower()),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_all_users(self) -> list[dict[str, Any]]:
        sql = """
        SELECT 
            u.id, 
            u.email, 
            u.full_name, 
            u.is_platform_admin, 
            u.created_at,
            w.id as workspace_id,
            w.name as workspace_name,
            m.role as role,
            COALESCE(s.plan_id, 'free') as plan_id,
            COALESCE(s.status, 'active') as subscription_status
        FROM users u
        LEFT JOIN memberships m ON m.user_id = u.id
        LEFT JOIN workspaces w ON w.id = m.workspace_id
        LEFT JOIN subscriptions s ON s.workspace_id = w.id
        ORDER BY u.created_at DESC
        """
        return self._fetchall(sql)

    def update_user_password(self, user_id: str, password_hash: str, salt: str) -> bool:
        with self._lock:
            self.delete_user_sessions(user_id)
            cur = self._conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (password_hash, salt, user_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def create_password_reset_token(self, user_id: str, token_hash: str, expires_at: str) -> dict[str, Any]:
        token_id = new_id()
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (token_id, user_id, token_hash, expires_at, now),
            )
            self._conn.commit()
            return {
                "id": token_id,
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "used_at": None,
                "created_at": now,
            }

    def get_password_reset_token(self, token_hash: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM password_reset_tokens WHERE token_hash = ?", (token_hash,))

    def mark_password_reset_token_used(self, token_id: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                (now, token_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def delete_expired_password_reset_tokens(self) -> int:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM password_reset_tokens WHERE expires_at < ? OR used_at IS NOT NULL",
                (now,),
            )
            self._conn.commit()
            return cur.rowcount

    def delete_user(self, user_id: str) -> bool:
        with self._lock:
            self.delete_user_sessions(user_id)
            self._conn.execute("DELETE FROM memberships WHERE user_id = ?", (user_id,))
            cur = self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # Regulations, Versions & Sources
    # -----------------------------------------------------------------------
    def create_regulation(
        self,
        title: str,
        country: str = "Bangladesh",
        sector: str | None = None,
        description: str | None = None,
        regulation_id: str | None = None,
    ) -> dict[str, Any]:
        reg_id = regulation_id or new_id()
        now = utcnow()
        record = {
            "id": reg_id,
            "title": title.strip(),
            "country": country.strip(),
            "sector": sector.strip() if sector else None,
            "description": description.strip() if description else None,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO regulations (id, title, country, sector, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (record["id"], record["title"], record["country"], record["sector"], record["description"], now),
        )
        return record

    def get_regulation(self, reg_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM regulations WHERE id = ?", (reg_id,))

    def list_regulations(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM regulations ORDER BY created_at DESC")

    def create_regulation_version(
        self,
        regulation_id: str,
        version_label: str,
        text: str,
        effective_date: str | None = None,
        status: str = "published",
        is_sample: bool = False,
        published_by: str | None = None,
    ) -> dict[str, Any]:
        ver_id = new_id()
        now = utcnow()
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        published_at = now if status == "published" else None
        record = {
            "id": ver_id,
            "regulation_id": regulation_id,
            "version_label": version_label.strip(),
            "text": text,
            "content_hash": content_hash,
            "effective_date": effective_date,
            "status": status,
            "is_sample": 1 if is_sample else 0,
            "published_by": published_by,
            "published_at": published_at,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO regulation_versions (id, regulation_id, version_label, text, content_hash, effective_date, status, is_sample, published_by, published_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ver_id,
                regulation_id,
                record["version_label"],
                text,
                content_hash,
                effective_date,
                status,
                record["is_sample"],
                published_by,
                published_at,
                now,
            ),
        )
        return record

    def get_regulation_version(self, version_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM regulation_versions WHERE id = ?", (version_id,))

    def list_regulation_versions(self, regulation_id: str, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            return self._fetchall(
                "SELECT * FROM regulation_versions WHERE regulation_id = ? AND status = ? ORDER BY created_at ASC",
                (regulation_id, status),
            )
        return self._fetchall(
            "SELECT * FROM regulation_versions WHERE regulation_id = ? ORDER BY created_at ASC", (regulation_id,)
        )

    def publish_regulation_version(self, version_id: str, published_by: str) -> dict[str, Any] | None:
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "UPDATE regulation_versions SET status = 'published', published_by = ?, published_at = ? WHERE id = ?",
                (published_by, now, version_id),
            )
            self._conn.commit()
        return self.get_regulation_version(version_id)

    def get_latest_published_pair(self, regulation_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Returns the two most recent published versions (before, after) for a regulation."""
        rows = self._fetchall(
            "SELECT * FROM regulation_versions WHERE regulation_id = ? AND status = 'published' ORDER BY created_at ASC, id ASC",
            (regulation_id,),
        )
        if len(rows) < 2:
            return None
        # rows[-2] is before, rows[-1] is after
        return rows[-2], rows[-1]

    # -----------------------------------------------------------------------
    # Sources
    # -----------------------------------------------------------------------
    def create_regulation_source(
        self,
        regulation_id: str | None,
        name: str,
        kind: str = "url_poll",
        url: str | None = None,
        poll_interval: int = 86400,
        enabled: bool = False,
    ) -> dict[str, Any]:
        src_id = new_id()
        now = utcnow()
        record = {
            "id": src_id,
            "regulation_id": regulation_id,
            "name": name.strip(),
            "kind": kind,
            "url": url.strip() if url else None,
            "poll_interval": poll_interval,
            "enabled": 1 if enabled else 0,
            "last_checked": None,
            "last_hash": None,
            "failure_count": 0,
            "last_error": None,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO regulation_sources (id, regulation_id, name, kind, url, poll_interval, enabled, last_checked, last_hash, failure_count, last_error, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                src_id,
                regulation_id,
                record["name"],
                kind,
                record["url"],
                poll_interval,
                record["enabled"],
                None,
                None,
                0,
                None,
                now,
            ),
        )
        return record

    def list_regulation_sources(self, regulation_id: str | None = None) -> list[dict[str, Any]]:
        if regulation_id:
            return self._fetchall("SELECT * FROM regulation_sources WHERE regulation_id = ? ORDER BY created_at DESC", (regulation_id,))
        return self._fetchall("SELECT * FROM regulation_sources ORDER BY created_at DESC")

    def get_regulation_source(self, source_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM regulation_sources WHERE id = ?", (source_id,))

    def update_regulation_source_check(
        self, source_id: str, content_hash: str | None = None, error: str | None = None
    ) -> None:
        now = utcnow()
        with self._lock:
            if error:
                self._conn.execute(
                    "UPDATE regulation_sources SET last_checked = ?, failure_count = failure_count + 1, last_error = ? WHERE id = ?",
                    (now, error, source_id),
                )
            else:
                self._conn.execute(
                    "UPDATE regulation_sources SET last_checked = ?, last_hash = ?, failure_count = 0, last_error = NULL WHERE id = ?",
                    (now, content_hash, source_id),
                )
            self._conn.commit()

    def set_regulation_source_enabled(self, source_id: str, enabled: bool) -> None:
        self._execute("UPDATE regulation_sources SET enabled = ? WHERE id = ?", (1 if enabled else 0, source_id))

    # -----------------------------------------------------------------------
    # Regulatory Changes
    # -----------------------------------------------------------------------
    def create_regulatory_change(
        self,
        regulation_id: str,
        from_version_id: str,
        to_version_id: str,
        summary: str,
        change_type: str = "Amendment",
        obligations: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        chg_id = new_id()
        now = utcnow()
        obs_json = json.dumps(obligations or [])
        tags_json = json.dumps(tags or [])
        record = {
            "id": chg_id,
            "regulation_id": regulation_id,
            "from_version_id": from_version_id,
            "to_version_id": to_version_id,
            "summary": summary,
            "change_type": change_type,
            "obligations": obligations or [],
            "tags": tags or [],
            "detected_at": now,
        }
        self._execute(
            "INSERT OR REPLACE INTO regulatory_changes (id, regulation_id, from_version_id, to_version_id, summary, change_type, obligations, tags, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chg_id, regulation_id, from_version_id, to_version_id, summary, change_type, obs_json, tags_json, now),
        )
        return record

    def list_regulatory_changes(self, regulation_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
        SELECT rc.*, r.title as regulation_title, vf.version_label as from_label, vt.version_label as to_label
        FROM regulatory_changes rc
        JOIN regulations r ON r.id = rc.regulation_id
        JOIN regulation_versions vf ON vf.id = rc.from_version_id
        JOIN regulation_versions vt ON vt.id = rc.to_version_id
        """
        if regulation_id:
            sql += " WHERE rc.regulation_id = ? ORDER BY rc.detected_at DESC"
            rows = self._fetchall(sql, (regulation_id,))
        else:
            sql += " ORDER BY rc.detected_at DESC"
            rows = self._fetchall(sql)

        for r in rows:
            r["obligations"] = json.loads(r["obligations"])
            r["tags"] = json.loads(r["tags"])
        return rows

    def get_regulatory_change(self, change_id: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT * FROM regulatory_changes WHERE id = ?", (change_id,))
        if row:
            row["obligations"] = json.loads(row["obligations"])
            row["tags"] = json.loads(row["tags"])
        return row

    # -----------------------------------------------------------------------
    # News Items
    # -----------------------------------------------------------------------
    def create_news_item(
        self,
        title: str,
        content: str,
        sector: str | None = None,
        jurisdiction: str = "Bangladesh",
        source_url: str | None = None,
        regulation_id: str | None = None,
    ) -> dict[str, Any]:
        news_id = new_id()
        now = utcnow()
        record = {
            "id": news_id,
            "title": title.strip(),
            "content": content.strip(),
            "sector": sector.strip() if sector else None,
            "jurisdiction": jurisdiction.strip(),
            "published_at": now,
            "source_url": source_url.strip() if source_url else None,
            "regulation_id": regulation_id,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO news_items (id, title, content, sector, jurisdiction, published_at, source_url, regulation_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (news_id, record["title"], record["content"], record["sector"], record["jurisdiction"], now, record["source_url"], regulation_id, now),
        )
        return record

    def list_news_items(
        self, sector: str | None = None, jurisdiction: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if sector:
            conditions.append("(sector IS NULL OR sector = ?)")
            params.append(sector)
        if jurisdiction:
            conditions.append("(jurisdiction IS NULL OR jurisdiction = ?)")
            params.append(jurisdiction)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM news_items {where_clause} ORDER BY published_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self._fetchall(sql, tuple(params))

    def get_news_item(self, news_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM news_items WHERE id = ?", (news_id,))

    # -----------------------------------------------------------------------
    # Monitor Subscriptions
    # -----------------------------------------------------------------------
    def subscribe_monitor(self, workspace_id: str, regulation_id: str) -> dict[str, Any]:
        sub_id = new_id()
        now = utcnow()
        self._execute(
            "INSERT OR IGNORE INTO monitor_subscriptions (id, workspace_id, regulation_id, created_at) VALUES (?, ?, ?, ?)",
            (sub_id, workspace_id, regulation_id, now),
        )
        return self._fetchone(
            "SELECT ms.*, r.title, r.sector, r.country FROM monitor_subscriptions ms JOIN regulations r ON r.id = ms.regulation_id WHERE ms.workspace_id = ? AND ms.regulation_id = ?",
            (workspace_id, regulation_id),
        )  # type: ignore[return-value]

    def unsubscribe_monitor(self, workspace_id: str, regulation_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM monitor_subscriptions WHERE workspace_id = ? AND regulation_id = ?",
                (workspace_id, regulation_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_monitor_subscriptions(self, workspace_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT ms.id, ms.regulation_id, ms.created_at, r.title, r.sector, r.country, r.description
        FROM monitor_subscriptions ms
        JOIN regulations r ON r.id = ms.regulation_id
        WHERE ms.workspace_id = ?
        ORDER BY ms.created_at DESC
        """
        return self._fetchall(sql, (workspace_id,))

    def is_subscribed_to_monitor(self, workspace_id: str, regulation_id: str) -> bool:
        row = self._fetchone(
            "SELECT 1 FROM monitor_subscriptions WHERE workspace_id = ? AND regulation_id = ?",
            (workspace_id, regulation_id),
        )
        return bool(row)

    def count_monitor_subscriptions(self, workspace_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) as count FROM monitor_subscriptions WHERE workspace_id = ?", (workspace_id,)
        )
        return int(row["count"]) if row else 0

    def list_workspaces_subscribed_to(self, regulation_id: str) -> list[str]:
        rows = self._fetchall(
            "SELECT workspace_id FROM monitor_subscriptions WHERE regulation_id = ?", (regulation_id,)
        )
        return [r["workspace_id"] for r in rows]

    # -----------------------------------------------------------------------
    # Notifications & Preferences
    # -----------------------------------------------------------------------
    def create_notification(
        self,
        workspace_id: str,
        user_id: str,
        title: str,
        body: str,
        link: str,
        channel: str = "in_app",
        dedupe_key: str | None = None,
    ) -> dict[str, Any] | None:
        notif_id = new_id()
        now = utcnow()
        try:
            self._execute(
                "INSERT INTO notifications (id, workspace_id, user_id, title, body, link, channel, dedupe_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (notif_id, workspace_id, user_id, title, body, link, channel, dedupe_key, now),
            )
            return {
                "id": notif_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "title": title,
                "body": body,
                "link": link,
                "channel": channel,
                "dedupe_key": dedupe_key,
                "read_at": None,
                "created_at": now,
            }
        except sqlite3.IntegrityError:
            # Deduplicated notification
            return None

    def list_notifications(
        self, workspace_id: str, user_id: str, unread_only: bool = False, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM notifications WHERE workspace_id = ? AND user_id = ?"
        params: list[Any] = [workspace_id, user_id]
        if unread_only:
            sql += " AND read_at IS NULL"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self._fetchall(sql, tuple(params))

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE notifications SET read_at = ? WHERE id = ? AND user_id = ?",
                (now, notification_id, user_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def mark_all_notifications_read(self, workspace_id: str, user_id: str) -> int:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE notifications SET read_at = ? WHERE workspace_id = ? AND user_id = ? AND read_at IS NULL",
                (now, workspace_id, user_id),
            )
            self._conn.commit()
            return cur.rowcount

    def get_unread_notification_count(self, workspace_id: str, user_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) as cnt FROM notifications WHERE workspace_id = ? AND user_id = ? AND read_at IS NULL",
            (workspace_id, user_id),
        )
        return int(row["cnt"]) if row else 0

    def get_notification_preferences(self, workspace_id: str, user_id: str) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT * FROM notification_preferences WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id),
        )
        if not row:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "email_enabled": True,
                "in_app_enabled": True,
                "frequency": "instant",
            }
        return {
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "email_enabled": bool(row["email_enabled"]),
            "in_app_enabled": bool(row["in_app_enabled"]),
            "frequency": row["frequency"],
        }

    def set_notification_preferences(
        self, workspace_id: str, user_id: str, email_enabled: bool, in_app_enabled: bool, frequency: str = "instant"
    ) -> dict[str, Any]:
        pref_id = new_id()
        now = utcnow()
        self._execute(
            "INSERT OR REPLACE INTO notification_preferences (id, workspace_id, user_id, email_enabled, in_app_enabled, frequency, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pref_id, workspace_id, user_id, 1 if email_enabled else 0, 1 if in_app_enabled else 0, frequency, now),
        )
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "email_enabled": email_enabled,
            "in_app_enabled": in_app_enabled,
            "frequency": frequency,
        }

    # -----------------------------------------------------------------------
    # Outbox
    # -----------------------------------------------------------------------
    def enqueue_outbox(self, channel: str, destination: str, payload: dict[str, Any]) -> dict[str, Any]:
        outbox_id = new_id()
        now = utcnow()
        record = {
            "id": outbox_id,
            "channel": channel,
            "destination": destination,
            "payload": payload,
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": now,
            "error": None,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO outbox (id, channel, destination, payload, status, attempts, next_attempt_at, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)",
            (outbox_id, channel, destination, json.dumps(payload), now, now),
        )
        return record

    def fetch_pending_outbox(self, limit: int = 20) -> list[dict[str, Any]]:
        now = utcnow()
        rows = self._fetchall(
            "SELECT * FROM outbox WHERE status = 'pending' AND (next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY created_at ASC LIMIT ?",
            (now, limit),
        )
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    def mark_outbox_sent(self, outbox_id: str) -> None:
        self._execute("UPDATE outbox SET status = 'sent', error = NULL WHERE id = ?", (outbox_id,))

    def mark_outbox_failed(self, outbox_id: str, error: str, next_attempt_at: str | None = None) -> None:
        self._execute(
            "UPDATE outbox SET status = 'failed', attempts = attempts + 1, error = ?, next_attempt_at = ? WHERE id = ?",
            (error, next_attempt_at, outbox_id),
        )

    # -----------------------------------------------------------------------
    # Background Job Queue
    # -----------------------------------------------------------------------
    def enqueue_job(
        self, job_type: str, payload: dict[str, Any], run_at: str | None = None, idempotency_key: str | None = None
    ) -> dict[str, Any] | None:
        job_id = new_id()
        now = utcnow()
        target_run_at = run_at or now
        try:
            self._execute(
                "INSERT INTO jobs (id, type, payload, run_at, status, attempts, idempotency_key, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)",
                (job_id, job_type, json.dumps(payload), target_run_at, idempotency_key, now),
            )
            return {
                "id": job_id,
                "type": job_type,
                "payload": payload,
                "run_at": target_run_at,
                "status": "pending",
                "attempts": 0,
                "idempotency_key": idempotency_key,
                "created_at": now,
            }
        except sqlite3.IntegrityError:
            return None

    def acquire_job_lease(self, lease_seconds: int = 60) -> dict[str, Any] | None:
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat(timespec="seconds")
        lease_until = (now_dt + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")

        with self._lock:
            # Find eligible candidate: pending job whose run_at <= now, or running job whose lease expired
            sql_find = """
            SELECT id FROM jobs
            WHERE (status = 'pending' AND run_at <= ?)
               OR (status = 'running' AND lease_until < ?)
            ORDER BY run_at ASC
            LIMIT 1
            """
            candidate = self._conn.execute(sql_find, (now_str, now_str)).fetchone()
            if not candidate:
                return None

            job_id = candidate["id"]
            self._conn.execute(
                "UPDATE jobs SET status = 'running', lease_until = ?, attempts = attempts + 1 WHERE id = ?",
                (lease_until, job_id),
            )
            self._conn.commit()

            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["payload"] = json.loads(res["payload"])
            return res

    def complete_job(self, job_id: str) -> None:
        self._execute("UPDATE jobs SET status = 'completed', lease_until = NULL WHERE id = ?", (job_id,))

    def fail_job(self, job_id: str, error: str, backoff_seconds: int = 30) -> None:
        now_dt = datetime.now(timezone.utc)
        retry_at = (now_dt + timedelta(seconds=backoff_seconds)).isoformat(timespec="seconds")
        with self._lock:
            job = self._conn.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()
            attempts = job["attempts"] if job else 1
            new_status = "dead_letter" if attempts >= 5 else "pending"
            self._conn.execute(
                "UPDATE jobs SET status = ?, run_at = ?, lease_until = NULL WHERE id = ?",
                (new_status, retry_at, job_id),
            )
            self._conn.commit()

    def get_queue_stats(self) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status").fetchall()
            stats = {r["status"]: int(r["cnt"]) for r in rows}
            last_job = self._conn.execute("SELECT created_at FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
            stats["last_enqueued_at"] = last_job["created_at"] if last_job else None
            return stats

    # -----------------------------------------------------------------------
    # Deadlines & Reminders
    # -----------------------------------------------------------------------
    def create_deadline(
        self,
        workspace_id: str,
        title: str,
        due_date: str,
        source_type: str = "manual",
        regulation_id: str | None = None,
        checklist_item_id: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        dl_id = new_id()
        now = utcnow()
        record = {
            "id": dl_id,
            "workspace_id": workspace_id,
            "title": title.strip(),
            "due_date": due_date,
            "source_type": source_type,
            "regulation_id": regulation_id,
            "checklist_item_id": checklist_item_id,
            "status": status,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO deadlines (id, workspace_id, title, due_date, source_type, regulation_id, checklist_item_id, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dl_id, workspace_id, record["title"], due_date, source_type, regulation_id, checklist_item_id, status, now),
        )
        return record

    def list_deadlines(self, workspace_id: str, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            return self._fetchall(
                "SELECT * FROM deadlines WHERE workspace_id = ? AND status = ? ORDER BY due_date ASC",
                (workspace_id, status),
            )
        return self._fetchall(
            "SELECT * FROM deadlines WHERE workspace_id = ? ORDER BY due_date ASC", (workspace_id,)
        )

    def get_deadline(self, deadline_id: str, workspace_id: str | None = None) -> dict[str, Any] | None:
        if workspace_id:
            return self._fetchone(
                "SELECT * FROM deadlines WHERE id = ? AND workspace_id = ?", (deadline_id, workspace_id)
            )
        return self._fetchone("SELECT * FROM deadlines WHERE id = ?", (deadline_id,))

    def update_deadline(
        self,
        deadline_id: str,
        workspace_id: str,
        title: str | None = None,
        due_date: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        fields = []
        params: list[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title.strip())
        if due_date is not None:
            fields.append("due_date = ?")
            params.append(due_date)
        if status is not None:
            fields.append("status = ?")
            params.append(status)

        if not fields:
            return self.get_deadline(deadline_id, workspace_id)

        params.extend([deadline_id, workspace_id])
        sql = f"UPDATE deadlines SET {', '.join(fields)} WHERE id = ? AND workspace_id = ?"
        self._execute(sql, tuple(params))
        return self.get_deadline(deadline_id, workspace_id)

    def delete_deadline(self, deadline_id: str, workspace_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM deadlines WHERE id = ? AND workspace_id = ?",
                (deadline_id, workspace_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_active_deadlines_for_due_date(self, target_due_date: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM deadlines WHERE due_date = ? AND status = 'active'", (target_due_date,)
        )

    def has_reminder_sent(self, deadline_id: str, lead_days: int) -> bool:
        row = self._fetchone(
            "SELECT 1 FROM reminder_log WHERE deadline_id = ? AND lead_days = ?", (deadline_id, lead_days)
        )
        return bool(row)

    def log_reminder(self, deadline_id: str, lead_days: int) -> bool:
        rem_id = new_id()
        now = utcnow()
        try:
            self._execute(
                "INSERT INTO reminder_log (id, deadline_id, lead_days, sent_at) VALUES (?, ?, ?, ?)",
                (rem_id, deadline_id, lead_days, now),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    # -----------------------------------------------------------------------
    # AI Assistant Threads & Messages
    # -----------------------------------------------------------------------
    def create_assistant_thread(self, workspace_id: str, user_id: str, title: str) -> dict[str, Any]:
        thread_id = new_id()
        now = utcnow()
        record = {
            "id": thread_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "title": title.strip(),
            "created_at": now,
        }
        self._execute(
            "INSERT INTO assistant_threads (id, workspace_id, user_id, title, created_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, workspace_id, user_id, record["title"], now),
        )
        return record

    def list_assistant_threads(self, workspace_id: str, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM assistant_threads WHERE workspace_id = ? AND user_id = ? ORDER BY created_at DESC",
            (workspace_id, user_id),
        )

    def get_assistant_thread(self, thread_id: str, workspace_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM assistant_threads WHERE id = ? AND workspace_id = ?", (thread_id, workspace_id)
        )

    def delete_assistant_thread(self, thread_id: str, workspace_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM assistant_threads WHERE id = ? AND workspace_id = ?", (thread_id, workspace_id)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def create_assistant_message(
        self, thread_id: str, role: str, content: str, citations: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        msg_id = new_id()
        now = utcnow()
        citations_json = json.dumps(citations or [])
        record = {
            "id": msg_id,
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "citations": citations or [],
            "created_at": now,
        }
        self._execute(
            "INSERT INTO assistant_messages (id, thread_id, role, content, citations, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, thread_id, role, content, citations_json, now),
        )
        return record

    def list_assistant_messages(self, thread_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT * FROM assistant_messages WHERE thread_id = ? ORDER BY created_at ASC LIMIT ?", (thread_id, limit)
        )
        for r in rows:
            r["citations"] = json.loads(r["citations"])
        return rows

    # -----------------------------------------------------------------------
    # Invites & Workspace Collaboration
    # -----------------------------------------------------------------------
    def create_invite(
        self, workspace_id: str, email: str, role: str, token_hash: str, expires_at: str
    ) -> dict[str, Any]:
        inv_id = new_id()
        now = utcnow()
        clean_email = email.strip().lower()
        record = {
            "id": inv_id,
            "workspace_id": workspace_id,
            "email": clean_email,
            "role": role,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "accepted_at": None,
            "revoked_at": None,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO invites (id, workspace_id, email, role, token_hash, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (inv_id, workspace_id, clean_email, role, token_hash, expires_at, now),
        )
        return record

    def get_invite_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM invites WHERE token_hash = ?", (token_hash,))

    def accept_invite(self, invite_id: str, user_id: str) -> dict[str, Any] | None:
        now = utcnow()
        with self._lock:
            inv = self._conn.execute("SELECT * FROM invites WHERE id = ?", (invite_id,)).fetchone()
            if not inv or inv["accepted_at"] or inv["revoked_at"] or inv["expires_at"] < now:
                return None
            self._conn.execute("UPDATE invites SET accepted_at = ? WHERE id = ?", (now, invite_id))
            # Create membership
            mem_id = new_id()
            self._conn.execute(
                "INSERT OR REPLACE INTO memberships (id, user_id, workspace_id, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (mem_id, user_id, inv["workspace_id"], inv["role"], now),
            )
            self._conn.commit()
            return dict(inv)

    def revoke_invite(self, invite_id: str, workspace_id: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE invites SET revoked_at = ? WHERE id = ? AND workspace_id = ? AND accepted_at IS NULL",
                (now, invite_id, workspace_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_invites(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM invites WHERE workspace_id = ? AND accepted_at IS NULL AND revoked_at IS NULL ORDER BY created_at DESC",
            (workspace_id,),
        )

    def count_team_members(self, workspace_id: str) -> int:
        """Returns total seats occupied: active memberships + pending active invites."""
        with self._lock:
            m_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM memberships WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
            active_mems = int(m_row["cnt"]) if m_row else 0

            now = utcnow()
            i_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM invites WHERE workspace_id = ? AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > ?",
                (workspace_id, now),
            ).fetchone()
            pending_invs = int(i_row["cnt"]) if i_row else 0

            return active_mems + pending_invs

    def list_workspace_members(self, workspace_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT m.id, m.workspace_id, m.user_id, m.role, m.created_at, u.email, u.full_name
        FROM memberships m
        JOIN users u ON u.id = m.user_id
        WHERE m.workspace_id = ?
        ORDER BY m.created_at ASC
        """
        return self._fetchall(sql, (workspace_id,))

    def get_membership(self, user_id: str, workspace_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM memberships WHERE user_id = ? AND workspace_id = ?", (user_id, workspace_id)
        )

    def update_member_role(self, workspace_id: str, user_id: str, new_role: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE memberships SET role = ? WHERE workspace_id = ? AND user_id = ?",
                (new_role, workspace_id, user_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def remove_member(self, workspace_id: str, user_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM memberships WHERE workspace_id = ? AND user_id = ? AND role != 'owner'",
                (workspace_id, user_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def create_comment(
        self, workspace_id: str, resource_type: str, resource_id: str, user_id: str, content: str
    ) -> dict[str, Any]:
        comment_id = new_id()
        now = utcnow()
        record = {
            "id": comment_id,
            "workspace_id": workspace_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "content": content.strip(),
            "created_at": now,
        }
        self._execute(
            "INSERT INTO comments (id, workspace_id, resource_type, resource_id, user_id, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (comment_id, workspace_id, resource_type, resource_id, user_id, record["content"], now),
        )
        return record

    def list_comments(self, workspace_id: str, resource_type: str, resource_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT c.*, u.full_name, u.email
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.workspace_id = ? AND c.resource_type = ? AND c.resource_id = ?
        ORDER BY c.created_at ASC
        """
        return self._fetchall(sql, (workspace_id, resource_type, resource_id))

    def create_or_update_finding_review(
        self,
        workspace_id: str,
        plan_id: str,
        finding_id: str,
        status: str,
        reviewer_id: str,
        note: str | None = None,
        edited_citation: str | None = None,
    ) -> dict[str, Any]:
        rev_id = new_id()
        now = utcnow()
        self._execute(
            "INSERT OR REPLACE INTO finding_reviews (id, workspace_id, plan_id, finding_id, status, reviewer_id, note, edited_citation, reviewed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rev_id, workspace_id, plan_id, finding_id, status, reviewer_id, note, edited_citation, now),
        )
        return {
            "id": rev_id,
            "workspace_id": workspace_id,
            "plan_id": plan_id,
            "finding_id": finding_id,
            "status": status,
            "reviewer_id": reviewer_id,
            "note": note,
            "edited_citation": edited_citation,
            "reviewed_at": now,
        }

    def list_finding_reviews(self, workspace_id: str, plan_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM finding_reviews WHERE workspace_id = ? AND plan_id = ?", (workspace_id, plan_id)
        )

    def create_activity_event(
        self, workspace_id: str, user_id: str | None, event_type: str, description: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        ev_id = new_id()
        now = utcnow()
        meta_json = json.dumps(metadata or {})
        record = {
            "id": ev_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "event_type": event_type,
            "description": description,
            "metadata": metadata or {},
            "created_at": now,
        }
        self._execute(
            "INSERT INTO activity_events (id, workspace_id, user_id, event_type, description, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ev_id, workspace_id, user_id, event_type, description, meta_json, now),
        )
        return record

    def list_activity_events(self, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT ae.*, u.full_name, u.email FROM activity_events ae LEFT JOIN users u ON u.id = ae.user_id WHERE ae.workspace_id = ? ORDER BY ae.created_at DESC LIMIT ?",
            (workspace_id, limit),
        )
        for r in rows:
            r["metadata"] = json.loads(r["metadata"])
        return rows

    # -----------------------------------------------------------------------
    # API Keys
    # -----------------------------------------------------------------------
    def create_api_key(
        self, workspace_id: str, name: str, prefix: str, key_hash: str, scopes: list[str] | None = None
    ) -> dict[str, Any]:
        key_id = new_id()
        now = utcnow()
        scopes_json = json.dumps(scopes or ["read"])
        record = {
            "id": key_id,
            "workspace_id": workspace_id,
            "name": name.strip(),
            "prefix": prefix,
            "key_hash": key_hash,
            "scopes": scopes or ["read"],
            "last_used_at": None,
            "revoked_at": None,
            "created_at": now,
        }
        self._execute(
            "INSERT INTO api_keys (id, workspace_id, name, prefix, key_hash, scopes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key_id, workspace_id, record["name"], prefix, key_hash, scopes_json, now),
        )
        return record

    def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT * FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL", (key_hash,))
        if row:
            row["scopes"] = json.loads(row["scopes"])
        return row

    def list_api_keys(self, workspace_id: str) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT id, workspace_id, name, prefix, scopes, last_used_at, revoked_at, created_at FROM api_keys WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,),
        )
        for r in rows:
            r["scopes"] = json.loads(r["scopes"])
        return rows

    def revoke_api_key(self, key_id: str, workspace_id: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND workspace_id = ?",
                (now, key_id, workspace_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def touch_api_key(self, key_id: str) -> None:
        now = utcnow()
        self._execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now, key_id))

    def count_active_api_keys(self, workspace_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) as cnt FROM api_keys WHERE workspace_id = ? AND revoked_at IS NULL",
            (workspace_id,),
        )
        return int(row["cnt"]) if row else 0

    # -----------------------------------------------------------------------
    # Support Tickets
    # -----------------------------------------------------------------------
    def create_support_ticket(
        self, workspace_id: str, user_id: str, subject: str, message: str, priority: str = "standard"
    ) -> dict[str, Any]:
        t_id = new_id()
        now = utcnow()
        record = {
            "id": t_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "subject": subject.strip(),
            "message": message.strip(),
            "priority": priority,
            "status": "open",
            "created_at": now,
        }
        self._execute(
            "INSERT INTO support_tickets (id, workspace_id, user_id, subject, message, priority, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
            (t_id, workspace_id, user_id, record["subject"], record["message"], priority, now),
        )
        return record

    def list_support_tickets(
        self, workspace_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if workspace_id:
            conditions.append("st.workspace_id = ?")
            params.append(workspace_id)
        if status:
            conditions.append("st.status = ?")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
        SELECT st.*, u.email as user_email, u.full_name as user_name, w.name as workspace_name
        FROM support_tickets st
        JOIN users u ON u.id = st.user_id
        JOIN workspaces w ON w.id = st.workspace_id
        {where_clause}
        ORDER BY
            CASE st.priority
                WHEN 'urgent' THEN 1
                WHEN 'priority' THEN 2
                ELSE 3
            END ASC,
            st.created_at ASC
        """
        return self._fetchall(sql, tuple(params))

    def get_support_ticket(self, ticket_id: str, workspace_id: str | None = None) -> dict[str, Any] | None:
        if workspace_id:
            return self._fetchone(
                "SELECT * FROM support_tickets WHERE id = ? AND workspace_id = ?", (ticket_id, workspace_id)
            )
        return self._fetchone("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))

    def update_support_ticket(self, ticket_id: str, status: str) -> dict[str, Any] | None:
        with self._lock:
            self._conn.execute("UPDATE support_tickets SET status = ? WHERE id = ?", (status, ticket_id))
            self._conn.commit()
        return self.get_support_ticket(ticket_id)

    def get_queue_stats(self) -> dict[str, Any]:
        counts = self._fetchall("SELECT status, count(*) as count FROM jobs GROUP BY status")
        counts_dict = {row["status"]: row["count"] for row in counts}
        running_leases = self._fetchall(
            "SELECT id, type, run_at, lease_until, attempts FROM jobs WHERE status = 'running' ORDER BY lease_until DESC LIMIT 10"
        )
        last_runs = self._fetchall("SELECT type, max(run_at) as last_run_at FROM jobs GROUP BY type")
        return {
            "pending_count": counts_dict.get("pending", 0),
            "running_count": counts_dict.get("running", 0),
            "completed_count": counts_dict.get("completed", 0),
            "failed_count": counts_dict.get("failed", 0),
            "dead_letter_count": counts_dict.get("dead", 0),
            "running_leases": running_leases,
            "last_run_by_type": {row["type"]: row["last_run_at"] for row in last_runs},
        }

    def reject_regulation_version(self, version_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._conn.execute("UPDATE regulation_versions SET status = 'rejected' WHERE id = ?", (version_id,))
            self._conn.commit()
        return self.get_regulation_version(version_id)

    # -----------------------------------------------------------------------
    # Bangladesh Legal Library (schema_version = 5)
    # -----------------------------------------------------------------------
    def create_law_source(
        self,
        name: str,
        base_url: str,
        source_type: str,
        enabled: bool = False,
        crawl_config: dict[str, Any] | None = None,
        rate_limit: float = 1.0,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        sid = source_id or f"src_{new_id()[:8]}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO law_sources (id, name, base_url, source_type, enabled, crawl_config, rate_limit, last_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'configured')",
                (sid, name, base_url, source_type, 1 if enabled else 0, json.dumps(crawl_config or {}), rate_limit),
            )
            self._conn.commit()
        return self.get_law_source(sid)  # type: ignore[return-value]

    def get_law_source(self, source_id: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT * FROM law_sources WHERE id = ?", (source_id,))
        if row and row.get("crawl_config"):
            try:
                row["crawl_config"] = json.loads(row["crawl_config"])
            except Exception:
                row["crawl_config"] = {}
        return row

    def list_law_sources(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM law_sources"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY name ASC"
        rows = self._fetchall(sql)
        for r in rows:
            if r.get("crawl_config"):
                try:
                    r["crawl_config"] = json.loads(r["crawl_config"])
                except Exception:
                    r["crawl_config"] = {}
        return rows

    def update_law_source(self, source_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_law_source(source_id)
        sets = []
        vals = []
        for k, v in fields.items():
            sets.append(f"{k} = ?")
            if k == "crawl_config" and isinstance(v, (dict, list)):
                vals.append(json.dumps(v))
            elif k == "enabled":
                vals.append(1 if v else 0)
            else:
                vals.append(v)
        vals.append(source_id)
        with self._lock:
            self._conn.execute(f"UPDATE law_sources SET {', '.join(sets)} WHERE id = ?", tuple(vals))
            self._conn.commit()
        return self.get_law_source(source_id)

    def create_law(
        self,
        canonical_title_en: str,
        canonical_title_bn: str | None = None,
        act_number: str | None = None,
        year: int | None = None,
        law_type: str = "act",
        issuing_body: str = "",
        language_available: str = "en",
        status: str = "in_force",
        status_confidence: float = 1.0,
        domain_tags: list[str] | None = None,
        summary_ai: str | None = None,
        summary_verified: bool = False,
        publish_state: str = "draft",
        law_id: str | None = None,
    ) -> dict[str, Any]:
        lid = law_id or f"law_{new_id()[:10]}"
        now = utcnow()
        with self._lock:
            self._conn.execute(
                """INSERT INTO laws (
                    id, canonical_title_en, canonical_title_bn, act_number, year, law_type,
                    issuing_body, language_available, status, status_confidence, domain_tags,
                    summary_ai, summary_verified, publish_state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lid,
                    canonical_title_en,
                    canonical_title_bn,
                    act_number,
                    year,
                    law_type,
                    issuing_body,
                    language_available,
                    status,
                    status_confidence,
                    json.dumps(domain_tags or []),
                    summary_ai,
                    1 if summary_verified else 0,
                    publish_state,
                    now,
                ),
            )
            self._conn.commit()
        return self.get_law(lid)  # type: ignore[return-value]

    def get_law(self, law_id: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT * FROM laws WHERE id = ?", (law_id,))
        if row and row.get("domain_tags"):
            try:
                row["domain_tags"] = json.loads(row["domain_tags"])
            except Exception:
                row["domain_tags"] = []
        return row

    def list_laws(
        self,
        q: str | None = None,
        law_type: str | None = None,
        domain_tag: str | None = None,
        status: str | None = None,
        year: int | None = None,
        language: str | None = None,
        issuing_body: str | None = None,
        publish_state: str | None = "published",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []

        if publish_state:
            conditions.append("publish_state = ?")
            params.append(publish_state)
        if law_type:
            conditions.append("law_type = ?")
            params.append(law_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if year:
            conditions.append("year = ?")
            params.append(year)
        if language:
            conditions.append("language_available LIKE ?")
            params.append(f"%{language}%")
        if issuing_body:
            conditions.append("issuing_body LIKE ?")
            params.append(f"%{issuing_body}%")
        if domain_tag:
            conditions.append("domain_tags LIKE ?")
            params.append(f'%"{domain_tag}"%')
        if q:
            conditions.append("(canonical_title_en LIKE ? OR canonical_title_bn LIKE ? OR act_number LIKE ?)")
            q_like = f"%{q.strip()}%"
            params.extend([q_like, q_like, q_like])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM laws {where_clause} ORDER BY year DESC, canonical_title_en ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._fetchall(sql, tuple(params))
        for r in rows:
            if r.get("domain_tags"):
                try:
                    r["domain_tags"] = json.loads(r["domain_tags"])
                except Exception:
                    r["domain_tags"] = []
        return rows

    def count_laws(
        self,
        publish_state: str | None = "published",
        law_type: str | None = None,
        domain_tag: str | None = None,
    ) -> int:
        conditions = []
        params: list[Any] = []
        if publish_state:
            conditions.append("publish_state = ?")
            params.append(publish_state)
        if law_type:
            conditions.append("law_type = ?")
            params.append(law_type)
        if domain_tag:
            conditions.append("domain_tags LIKE ?")
            params.append(f'%"{domain_tag}"%')
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) as c FROM laws {where_clause}"
        row = self._fetchone(sql, tuple(params))
        return int(row["c"]) if row else 0

    def update_law(self, law_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_law(law_id)
        sets = []
        vals = []
        for k, v in fields.items():
            sets.append(f"{k} = ?")
            if k == "domain_tags" and isinstance(v, (list, dict)):
                vals.append(json.dumps(v))
            elif k == "summary_verified":
                vals.append(1 if v else 0)
            else:
                vals.append(v)
        vals.append(law_id)
        with self._lock:
            self._conn.execute(f"UPDATE laws SET {', '.join(sets)} WHERE id = ?", tuple(vals))
            self._conn.commit()
        return self.get_law(law_id)

    def delete_law(self, law_id: str) -> bool:
        with self._lock:
            self._conn.execute("DELETE FROM laws WHERE id = ?", (law_id,))
            self._conn.execute("DELETE FROM law_sections_fts WHERE law_id = ?", (law_id,))
            self._conn.commit()
        return True

    def create_law_version(
        self,
        law_id: str,
        version_hash: str,
        source_url: str | None = None,
        fetched_at: str | None = None,
        extraction_method: str = "text",
        ocr_quality: float | None = None,
        raw_text_path: str | None = None,
        is_current: bool = True,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        vid = version_id or f"ver_{new_id()[:10]}"
        now = fetched_at or utcnow()
        with self._lock:
            if is_current:
                self._conn.execute("UPDATE law_versions SET is_current = 0 WHERE law_id = ?", (law_id,))
            self._conn.execute(
                """INSERT INTO law_versions (
                    id, law_id, version_hash, source_url, fetched_at, extraction_method,
                    ocr_quality, raw_text_path, is_current
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (vid, law_id, version_hash, source_url, now, extraction_method, ocr_quality, raw_text_path, 1 if is_current else 0),
            )
            self._conn.commit()
        return self.get_law_version(vid)  # type: ignore[return-value]

    def get_law_version(self, version_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM law_versions WHERE id = ?", (version_id,))

    def get_current_law_version(self, law_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM law_versions WHERE law_id = ? AND is_current = 1 ORDER BY fetched_at DESC LIMIT 1", (law_id,))

    def list_law_versions(self, law_id: str) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM law_versions WHERE law_id = ? ORDER BY fetched_at DESC", (law_id,))

    def create_law_sections_bulk(
        self,
        law_version_id: str,
        law_id: str,
        sections_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        with self._lock:
            for idx, s in enumerate(sections_data):
                sec_id = s.get("id") or f"sec_{new_id()[:10]}"
                num_label = s.get("number_label", f"{idx + 1}")
                heading = s.get("heading")
                text = s.get("text", "")
                level = s.get("level", "section")
                parent_id = s.get("parent_id")
                order_idx = s.get("order_index", idx)

                self._conn.execute(
                    """INSERT INTO law_sections (
                        id, law_version_id, parent_id, level, number_label, heading, text, order_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sec_id, law_version_id, parent_id, level, num_label, heading, text, order_idx),
                )
                self._conn.execute(
                    """INSERT INTO law_sections_fts (
                        section_id, law_id, version_id, heading, text, number_label
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (sec_id, law_id, law_version_id, heading or "", text, num_label),
                )
                created.append({
                    "id": sec_id,
                    "law_version_id": law_version_id,
                    "parent_id": parent_id,
                    "level": level,
                    "number_label": num_label,
                    "heading": heading,
                    "text": text,
                    "order_index": order_idx,
                })
            self._conn.commit()
        return created

    def get_law_section(self, section_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM law_sections WHERE id = ?", (section_id,))

    def list_law_sections(self, law_version_id: str) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM law_sections WHERE law_version_id = ? ORDER BY order_index ASC", (law_version_id,))

    def search_law_sections_fts(
        self,
        query: str,
        limit: int = 20,
        law_id: str | None = None,
    ) -> list[dict[str, Any]]:
        import re
        clean_q = re.sub(r'["\']', '', query).strip()
        if not clean_q:
            return []

        # Tokenize and format query for FTS5
        words = [re.sub(r'[^a-zA-Z0-9_\u0980-\u09FF]', '', t) for t in clean_q.split()]
        words = [w for w in words if w]
        if not words:
            return []

        stopwords = {"what", "is", "are", "the", "a", "an", "about", "how", "why", "does", "under", "in", "to", "for", "of"}
        content_words = [w for w in words if w.lower() not in stopwords] or words

        and_query = " ".join([f'"{w}"*' for w in content_words])
        or_query = " OR ".join([f'"{w}"*' for w in content_words])

        def _execute(match_q: str) -> list[dict[str, Any]]:
            params: list[Any] = [match_q]
            where_parts = ["law_sections_fts MATCH ?"]
            if law_id:
                where_parts.append("law_id = ?")
                params.append(law_id)
            where_clause = " AND ".join(where_parts)
            params.append(limit)

            sql = f"""
            SELECT section_id, law_id, version_id, heading, text, number_label, rank
            FROM law_sections_fts
            WHERE {where_clause}
            ORDER BY rank
            LIMIT ?
            """
            try:
                return self._fetchall(sql, tuple(params))
            except Exception as e:
                logger.warning(f"FTS search error: {e}")
                return []

        hits = _execute(and_query)
        if not hits and and_query != or_query:
            hits = _execute(or_query)
        return hits

    def create_law_relation(self, from_law_id: str, to_law_id: str, relation: str) -> dict[str, Any]:
        rid = f"rel_{new_id()[:8]}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO law_relations (id, from_law_id, to_law_id, relation) VALUES (?, ?, ?, ?)",
                (rid, from_law_id, to_law_id, relation),
            )
            self._conn.commit()
        return {"id": rid, "from_law_id": from_law_id, "to_law_id": to_law_id, "relation": relation}

    def list_law_relations(self, law_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT lr.*,
               l_to.canonical_title_en as to_law_title, l_to.year as to_law_year,
               l_from.canonical_title_en as from_law_title, l_from.year as from_law_year
        FROM law_relations lr
        JOIN laws l_to ON l_to.id = lr.to_law_id
        JOIN laws l_from ON l_from.id = lr.from_law_id
        WHERE lr.from_law_id = ? OR lr.to_law_id = ?
        """
        return self._fetchall(sql, (law_id, law_id))

    def create_law_ingest_run(self, source_id: str | None = None) -> dict[str, Any]:
        rid = f"run_{new_id()[:10]}"
        now = utcnow()
        with self._lock:
            self._conn.execute(
                """INSERT INTO law_ingest_runs (
                    id, source_id, started_at, discovered, new, changed, failed, cost_estimate
                ) VALUES (?, ?, ?, 0, 0, 0, 0, 0.0)""",
                (rid, source_id, now),
            )
            self._conn.commit()
        return self.get_law_ingest_run(rid)  # type: ignore[return-value]

    def update_law_ingest_run(self, run_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_law_ingest_run(run_id)
        sets = [f"{k} = ?" for k in fields.keys()]
        vals = list(fields.values()) + [run_id]
        with self._lock:
            self._conn.execute(f"UPDATE law_ingest_runs SET {', '.join(sets)} WHERE id = ?", tuple(vals))
            self._conn.commit()
        return self.get_law_ingest_run(run_id)

    def get_law_ingest_run(self, run_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM law_ingest_runs WHERE id = ?", (run_id,))

    def list_law_ingest_runs(self, source_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if source_id:
            return self._fetchall("SELECT * FROM law_ingest_runs WHERE source_id = ? ORDER BY started_at DESC LIMIT ?", (source_id, limit))
        return self._fetchall("SELECT * FROM law_ingest_runs ORDER BY started_at DESC LIMIT ?", (limit,))

    def add_to_law_watchlist(self, workspace_id: str, user_id: str, law_id: str) -> bool:
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO law_watchlist (workspace_id, user_id, law_id, created_at) VALUES (?, ?, ?, ?)",
                (workspace_id, user_id, law_id, now),
            )
            self._conn.commit()
        return True

    def remove_from_law_watchlist(self, workspace_id: str, user_id: str, law_id: str) -> bool:
        with self._lock:
            self._conn.execute(
                "DELETE FROM law_watchlist WHERE workspace_id = ? AND user_id = ? AND law_id = ?",
                (workspace_id, user_id, law_id),
            )
            self._conn.commit()
        return True

    def list_law_watchlist(self, workspace_id: str, user_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT lw.*, l.canonical_title_en, l.canonical_title_bn, l.law_type, l.year, l.status, l.issuing_body
        FROM law_watchlist lw
        JOIN laws l ON l.id = lw.law_id
        WHERE lw.workspace_id = ? AND lw.user_id = ?
        ORDER BY lw.created_at DESC
        """
        return self._fetchall(sql, (workspace_id, user_id))

    def is_law_watched(self, workspace_id: str, user_id: str, law_id: str) -> bool:
        row = self._fetchone(
            "SELECT 1 FROM law_watchlist WHERE workspace_id = ? AND user_id = ? AND law_id = ?",
            (workspace_id, user_id, law_id),
        )
        return row is not None

    def list_workspace_ids_watching_law(self, law_id: str) -> list[str]:
        rows = self._fetchall("SELECT DISTINCT workspace_id FROM law_watchlist WHERE law_id = ?", (law_id,))
        return [r["workspace_id"] for r in rows]

    def enqueue_law_review(self, law_id: str, reason: str) -> dict[str, Any]:
        qid = f"rev_{new_id()[:8]}"
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT INTO law_review_queue (id, law_id, reason, created_at) VALUES (?, ?, ?, ?)",
                (qid, law_id, reason, now),
            )
            self._conn.commit()
        return {"id": qid, "law_id": law_id, "reason": reason, "created_at": now}

    def list_law_review_queue(self, resolved: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        sql = """
        SELECT rq.*, l.canonical_title_en, l.canonical_title_bn, l.law_type, l.year, l.issuing_body, l.publish_state
        FROM law_review_queue rq
        JOIN laws l ON l.id = rq.law_id
        """
        if resolved:
            sql += " WHERE rq.resolution IS NOT NULL"
        else:
            sql += " WHERE rq.resolution IS NULL"
        sql += " ORDER BY rq.created_at DESC LIMIT ?"
        return self._fetchall(sql, (limit,))

    def resolve_law_review(self, queue_id: str, resolved_by: str, resolution: str) -> dict[str, Any] | None:
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "UPDATE law_review_queue SET resolved_by = ?, resolution = ?, resolved_at = ? WHERE id = ?",
                (resolved_by, resolution, now, queue_id),
            )
            self._conn.commit()
        return self._fetchone("SELECT * FROM law_review_queue WHERE id = ?", (queue_id,))

    def get_laws_coverage_stats(self) -> dict[str, Any]:
        sources = self.list_law_sources()
        total_laws_row = self._fetchone("SELECT COUNT(*) as c FROM laws WHERE publish_state = 'published'")
        total_laws = int(total_laws_row["c"]) if total_laws_row else 0
        pending_review_row = self._fetchone("SELECT COUNT(*) as c FROM laws WHERE publish_state = 'pending_review'")
        pending_review = int(pending_review_row["c"]) if pending_review_row else 0
        by_type = self._fetchall("SELECT law_type, COUNT(*) as count FROM laws WHERE publish_state = 'published' GROUP BY law_type")
        by_issuing = self._fetchall("SELECT issuing_body, COUNT(*) as count FROM laws WHERE publish_state = 'published' GROUP BY issuing_body")
        runs = self.list_law_ingest_runs(limit=10)
        failed_sources = [s for s in sources if s.get("last_status") in ("failed", "blocked")]

        return {
            "published_laws_count": total_laws,
            "pending_review_count": pending_review,
            "total_sources_count": len(sources),
            "enabled_sources_count": len([s for s in sources if s.get("enabled")]),
            "failed_sources_count": len(failed_sources),
            "by_law_type": {r["law_type"]: r["count"] for r in by_type},
            "by_issuing_body": {r["issuing_body"]: r["count"] for r in by_issuing},
            "recent_runs": runs,
            "sources": sources,
        }



    # -----------------------------------------------------------------------
    # Alert Center (schema_version = 6 & 7)
    # -----------------------------------------------------------------------

    def create_alert_event(
        self,
        workspace_id: str,
        event_type: str,
        severity: str,
        entity_type: str,
        entity_id: str,
        version_hash: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        eid = event_id or new_id()
        now = utcnow()
        payload_dict = payload or {}
        with self._lock:
            self._conn.execute(
                "INSERT INTO alert_events (id, workspace_id, event_type, severity, entity_type, entity_id, version_hash, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (eid, workspace_id, event_type, severity, entity_type, entity_id, version_hash, json.dumps(payload_dict), now),
            )
            self._conn.commit()
        return self.get_alert_event(eid)  # type: ignore[return-value]

    def get_alert_event(self, event_id: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT * FROM alert_events WHERE id = ?", (event_id,))
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("payload"), str):
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                d["payload"] = {}
        return d

    def create_alert(
        self,
        alert_event_id: str,
        workspace_id: str,
        recipient_user_id: str,
        status: str = "pending",
        held_until: str | None = None,
        ack_required: bool = False,
        escalation_level: int = 0,
        idempotency_key: str | None = None,
        alert_id: str | None = None,
    ) -> dict[str, Any]:
        aid = alert_id or new_id()
        ikey = idempotency_key or f"{alert_event_id}:{recipient_user_id}:{new_id()}"
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT INTO alerts (id, alert_event_id, workspace_id, recipient_user_id, status, held_until, ack_required, escalation_level, idempotency_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, alert_event_id, workspace_id, recipient_user_id, status, held_until, 1 if ack_required else 0, escalation_level, ikey, now),
            )
            self._conn.commit()
        return self.get_alert(aid)  # type: ignore[return-value]

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        sql = """
        SELECT a.*, e.event_type, e.severity, e.entity_type, e.entity_id, e.version_hash, e.payload as event_payload,
               u.email as recipient_email, u.full_name as recipient_name
        FROM alerts a
        JOIN alert_events e ON e.id = a.alert_event_id
        LEFT JOIN users u ON u.id = a.recipient_user_id
        WHERE a.id = ?
        """
        row = self._fetchone(sql, (alert_id,))
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("event_payload"), str):
            try:
                d["event_payload"] = json.loads(d["event_payload"])
            except Exception:
                d["event_payload"] = {}
        return d

    def get_alert_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT id FROM alerts WHERE idempotency_key = ?", (idempotency_key,))
        if row:
            return self.get_alert(row["id"])
        return None

    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        acked_via: str | None = None,
        escalation_level: int | None = None,
    ) -> None:
        now = utcnow()
        with self._lock:
            if status == "acknowledged":
                self._conn.execute(
                    "UPDATE alerts SET status = ?, acked_at = ?, acked_via = ? WHERE id = ?",
                    (status, now, acked_via or "in_app", alert_id),
                )
            elif escalation_level is not None:
                self._conn.execute(
                    "UPDATE alerts SET status = ?, escalation_level = ? WHERE id = ?",
                    (status, escalation_level, alert_id),
                )
            else:
                self._conn.execute(
                    "UPDATE alerts SET status = ? WHERE id = ?",
                    (status, alert_id),
                )
            self._conn.commit()

    def acknowledge_alert(self, alert_id: str, user_id: str, acked_via: str = "in_app") -> dict[str, Any] | None:
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "UPDATE alerts SET status = 'acknowledged', acked_at = ?, acked_via = ? WHERE id = ? AND (recipient_user_id = ? OR workspace_id IN (SELECT workspace_id FROM memberships WHERE user_id = ? AND role IN ('owner', 'admin')))",
                (now, acked_via, alert_id, user_id, user_id),
            )
            self._conn.commit()
        return self.get_alert(alert_id)

    def list_alerts(
        self,
        workspace_id: str,
        recipient_user_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT a.*, e.event_type, e.severity, e.entity_type, e.entity_id, e.version_hash, e.payload as event_payload,
               u.email as recipient_email, u.full_name as recipient_name
        FROM alerts a
        JOIN alert_events e ON e.id = a.alert_event_id
        LEFT JOIN users u ON u.id = a.recipient_user_id
        WHERE a.workspace_id = ?
        """
        params: list[Any] = [workspace_id]
        if recipient_user_id:
            sql += " AND a.recipient_user_id = ?"
            params.append(recipient_user_id)
        if status:
            sql += " AND a.status = ?"
            params.append(status)
        if severity:
            sql += " AND e.severity = ?"
            params.append(severity)
        sql += " ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._fetchall(sql, tuple(params))
        res = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("event_payload"), str):
                try:
                    d["event_payload"] = json.loads(d["event_payload"])
                except Exception:
                    d["event_payload"] = {}
            res.append(d)
        return res

    def get_unacknowledged_alerts(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
        SELECT a.*, e.event_type, e.severity, e.entity_type, e.entity_id, e.payload as event_payload
        FROM alerts a
        JOIN alert_events e ON e.id = a.alert_event_id
        WHERE a.ack_required = 1 AND a.status IN ('sent', 'partially_failed', 'escalated') AND a.acked_at IS NULL
        """
        params: list[Any] = []
        if workspace_id:
            sql += " AND a.workspace_id = ?"
            params.append(workspace_id)
        rows = self._fetchall(sql, tuple(params))
        res = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("event_payload"), str):
                try:
                    d["event_payload"] = json.loads(d["event_payload"])
                except Exception:
                    d["event_payload"] = {}
            res.append(d)
        return res

    def get_held_alerts_to_release(self, now_iso: str) -> list[dict[str, Any]]:
        sql = """
        SELECT a.*, e.event_type, e.severity, e.payload as event_payload
        FROM alerts a
        JOIN alert_events e ON e.id = a.alert_event_id
        WHERE a.status = 'held' AND a.held_until <= ?
        """
        rows = self._fetchall(sql, (now_iso,))
        res = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("event_payload"), str):
                try:
                    d["event_payload"] = json.loads(d["event_payload"])
                except Exception:
                    d["event_payload"] = {}
            res.append(d)
        return res

    def create_alert_delivery(
        self,
        alert_id: str,
        channel: str,
        provider: str,
        status: str = "queued",
        provider_message_id: str | None = None,
        error_code: str | None = None,
        segments: int = 1,
        cost_estimate: float = 0.0,
        attempt: int = 1,
        delivery_id: str | None = None,
    ) -> dict[str, Any]:
        did = delivery_id or new_id()
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT INTO alert_deliveries (id, alert_id, channel, provider, status, provider_message_id, error_code, segments, cost_estimate, attempt, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (did, alert_id, channel, provider, status, provider_message_id, error_code, segments, cost_estimate, attempt, now, now),
            )
            self._conn.commit()
        return self._fetchone("SELECT * FROM alert_deliveries WHERE id = ?", (did,))  # type: ignore[return-value]

    def update_alert_delivery(
        self,
        delivery_id: str,
        status: str,
        provider_message_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        now = utcnow()
        with self._lock:
            if provider_message_id:
                self._conn.execute(
                    "UPDATE alert_deliveries SET status = ?, provider_message_id = ?, error_code = ?, updated_at = ? WHERE id = ?",
                    (status, provider_message_id, error_code, now, delivery_id),
                )
            else:
                self._conn.execute(
                    "UPDATE alert_deliveries SET status = ?, error_code = ?, updated_at = ? WHERE id = ?",
                    (status, error_code, now, delivery_id),
                )
            self._conn.commit()

    def get_alert_deliveries(self, alert_id: str) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM alert_deliveries WHERE alert_id = ? ORDER BY created_at ASC", (alert_id,))

    def get_delivery_stats(self, workspace_id: str) -> dict[str, Any]:
        sql = """
        SELECT d.channel, d.status, COUNT(*) as count, SUM(d.cost_estimate) as total_cost, SUM(d.segments) as total_segments
        FROM alert_deliveries d
        JOIN alerts a ON a.id = d.alert_id
        WHERE a.workspace_id = ?
        GROUP BY d.channel, d.status
        """
        rows = self._fetchall(sql, (workspace_id,))
        by_channel: dict[str, Any] = {}
        for r in rows:
            ch = r["channel"]
            if ch not in by_channel:
                by_channel[ch] = {"sent": 0, "delivered": 0, "failed": 0, "cost": 0.0, "segments": 0}
            st = r["status"]
            if st in ("sent", "delivered", "failed", "rejected"):
                by_channel[ch][st] = by_channel[ch].get(st, 0) + int(r["count"])
            by_channel[ch]["cost"] += float(r["total_cost"] or 0.0)
            by_channel[ch]["segments"] += int(r["total_segments"] or 0)
        return by_channel

    # Compliance Owners
    def list_compliance_owners(self, workspace_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT co.*, pu.email as primary_email, pu.full_name as primary_name,
               bu.email as backup_email, bu.full_name as backup_name
        FROM compliance_owners co
        LEFT JOIN users pu ON pu.id = co.primary_user_id
        LEFT JOIN users bu ON bu.id = co.backup_user_id
        WHERE co.workspace_id = ?
        """
        return self._fetchall(sql, (workspace_id,))

    def get_compliance_owner_for_tag(self, workspace_id: str, domain_tag: str) -> dict[str, Any] | None:
        sql = """
        SELECT co.*, pu.email as primary_email, pu.full_name as primary_name,
               bu.email as backup_email, bu.full_name as backup_name
        FROM compliance_owners co
        LEFT JOIN users pu ON pu.id = co.primary_user_id
        LEFT JOIN users bu ON bu.id = co.backup_user_id
        WHERE co.workspace_id = ? AND co.domain_tag = ?
        """
        return self._fetchone(sql, (workspace_id, domain_tag))

    def set_compliance_owner(
        self,
        workspace_id: str,
        domain_tag: str,
        primary_user_id: str,
        backup_user_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._conn.execute(
                "INSERT INTO compliance_owners (workspace_id, domain_tag, primary_user_id, backup_user_id) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(workspace_id, domain_tag) DO UPDATE SET primary_user_id = excluded.primary_user_id, backup_user_id = excluded.backup_user_id",
                (workspace_id, domain_tag, primary_user_id, backup_user_id),
            )
            self._conn.commit()
        return self.get_compliance_owner_for_tag(workspace_id, domain_tag)  # type: ignore[return-value]

    def delete_compliance_owner(self, workspace_id: str, domain_tag: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM compliance_owners WHERE workspace_id = ? AND domain_tag = ?",
                (workspace_id, domain_tag),
            )
            self._conn.commit()
        return cur.rowcount > 0

    # User Channels & Verification
    def get_user_channels(self, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM user_channels WHERE user_id = ?", (user_id,))

    def get_user_channel(self, user_id: str, channel: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM user_channels WHERE user_id = ? AND channel = ?", (user_id, channel))

    def set_user_channel(
        self,
        user_id: str,
        channel: str,
        address: str,
        display_address: str | None = None,
        locale: str = "en",
    ) -> dict[str, Any]:
        with self._lock:
            self._conn.execute(
                "INSERT INTO user_channels (user_id, channel, address, display_address, locale) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, channel) DO UPDATE SET address = excluded.address, display_address = excluded.display_address, locale = excluded.locale, opted_out_at = NULL",
                (user_id, channel, address, display_address or address, locale),
            )
            self._conn.commit()
        return self.get_user_channel(user_id, channel)  # type: ignore[return-value]

    def verify_user_channel(self, user_id: str, channel: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE user_channels SET verified_at = ? WHERE user_id = ? AND channel = ?",
                (now, user_id, channel),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def opt_out_user_channel(self, user_id: str, channel: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE user_channels SET opted_out_at = ? WHERE user_id = ? AND channel = ?",
                (now, user_id, channel),
            )
            if cur.rowcount == 0:
                user = self._fetchone("SELECT email FROM users WHERE id = ?", (user_id,))
                addr = user["email"] if user and channel == "email" else ""
                self._conn.execute(
                    "INSERT INTO user_channels (user_id, channel, address, display_address, opted_out_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, channel, addr, addr, now),
                )
            self._conn.commit()
        return True

    def re_opt_in_user_channel(self, user_id: str, channel: str) -> bool:
        with self._lock:
            self._conn.execute(
                "UPDATE user_channels SET opted_out_at = NULL WHERE user_id = ? AND channel = ?",
                (user_id, channel),
            )
            self._conn.commit()
        return True

    def opt_in_whatsapp(self, user_id: str) -> bool:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE user_channels SET whatsapp_opt_in_at = ?, opted_out_at = NULL WHERE user_id = ? AND channel = 'whatsapp'",
                (now, user_id),
            )
            self._conn.commit()
        return cur.rowcount > 0

    # Alert Preferences
    def get_alert_preferences(self, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM alert_preferences WHERE user_id = ?", (user_id,))

    def set_alert_preference(self, user_id: str, event_type: str, channel: str, enabled: bool) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO alert_preferences (user_id, event_type, channel, enabled) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, event_type, channel) DO UPDATE SET enabled = excluded.enabled",
                (user_id, event_type, channel, 1 if enabled else 0),
            )
            self._conn.commit()

    def batch_set_alert_preferences(self, user_id: str, preferences: list[tuple[str, str, bool]]) -> None:
        with self._lock:
            for ev, ch, en in preferences:
                self._conn.execute(
                    "INSERT INTO alert_preferences (user_id, event_type, channel, enabled) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(user_id, event_type, channel) DO UPDATE SET enabled = excluded.enabled",
                    (user_id, ev, ch, 1 if en else 0),
                )
            self._conn.commit()

    # Workspace Alert Settings
    def get_workspace_alert_settings(self, workspace_id: str) -> dict[str, Any]:
        row = self._fetchone("SELECT * FROM workspace_alert_settings WHERE workspace_id = ?", (workspace_id,))
        if not row:
            # Seed default workspace settings
            now = utcnow()
            with self._lock:
                self._conn.execute(
                    "INSERT INTO workspace_alert_settings (workspace_id, quiet_hours_start, quiet_hours_end, timezone, weekend_days, escalation_critical_hours, escalation_high_hours, monthly_sms_cap, monthly_whatsapp_cap, digest_hour_bst, created_at, updated_at) "
                    "VALUES (?, '22:00', '08:00', 'Asia/Dhaka', '[4, 5]', 4, 24, 100, 100, 9, ?, ?)",
                    (workspace_id, now, now),
                )
                self._conn.commit()
            row = self._fetchone("SELECT * FROM workspace_alert_settings WHERE workspace_id = ?", (workspace_id,))
        d = dict(row)  # type: ignore[arg-type]
        if isinstance(d.get("weekend_days"), str):
            try:
                d["weekend_days"] = json.loads(d["weekend_days"])
            except Exception:
                d["weekend_days"] = [4, 5]
        return d

    def update_workspace_alert_settings(self, workspace_id: str, **kwargs: Any) -> dict[str, Any]:
        now = utcnow()
        allowed = {
            "quiet_hours_start", "quiet_hours_end", "timezone", "weekend_days",
            "escalation_critical_hours", "escalation_high_hours", "monthly_sms_cap",
            "monthly_whatsapp_cap", "digest_hour_bst"
        }
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                if k == "weekend_days" and isinstance(v, (list, tuple)):
                    params.append(json.dumps(v))
                else:
                    params.append(v)
        updates.append("updated_at = ?")
        params.append(now)
        params.append(workspace_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE workspace_alert_settings SET {', '.join(updates)} WHERE workspace_id = ?",
                tuple(params),
            )
            self._conn.commit()
        return self.get_workspace_alert_settings(workspace_id)

    # SMS OTPs
    def create_sms_otp(self, phone_number: str, user_id: str, code_hash: str, expires_at: str) -> dict[str, Any]:
        oid = new_id()
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT INTO sms_otps (id, phone_number, user_id, code_hash, attempts, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?, ?)",
                (oid, phone_number, user_id, code_hash, expires_at, now),
            )
            self._conn.commit()
        return self._fetchone("SELECT * FROM sms_otps WHERE id = ?", (oid,))  # type: ignore[return-value]

    def get_latest_sms_otp(self, phone_number: str, user_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM sms_otps WHERE phone_number = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
            (phone_number, user_id),
        )

    def increment_sms_otp_attempts(self, otp_id: str) -> int:
        with self._lock:
            self._conn.execute("UPDATE sms_otps SET attempts = attempts + 1 WHERE id = ?", (otp_id,))
            self._conn.commit()
            row = self._fetchone("SELECT attempts FROM sms_otps WHERE id = ?", (otp_id,))
            return int(row["attempts"]) if row else 0

    def delete_sms_otp(self, otp_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sms_otps WHERE id = ?", (otp_id,))
            self._conn.commit()

    # Short Links
    def create_short_link(self, code: str, original_url: str, expires_at: str | None = None) -> dict[str, Any]:
        now = utcnow()
        with self._lock:
            self._conn.execute(
                "INSERT INTO short_links (code, original_url, expires_at, created_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(code) DO UPDATE SET original_url = excluded.original_url, expires_at = excluded.expires_at",
                (code, original_url, expires_at, now),
            )
            self._conn.commit()
        return self._fetchone("SELECT * FROM short_links WHERE code = ?", (code,))  # type: ignore[return-value]

    def get_short_link(self, code: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM short_links WHERE code = ?", (code,))
