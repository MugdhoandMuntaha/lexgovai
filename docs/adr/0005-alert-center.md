# ADR 0005: LexGOV AI Alert Center — Multi-Channel Bangladesh-Ready Notification & Escalation Architecture

**Status:** Accepted  
**Date:** 2026-11-13  
**Context:** Multi-Channel Notification Router, Bangladesh Bulk-SMS Gateways (SSL Wireless, Generic HTTP), Meta WhatsApp Business Cloud API, Quiet Hours / BST Calendar, Compliance Owners Routing, Automated Escalation, Schema Version 7.

---

## 1. Context & Business Need

LexGOV AI monitors government portals (NBR, BGPress, Bangladesh Bank, Ministry of Law) and performs SOP compliance analyses. When a critical regulatory change or high-risk finding is detected, alerting the right stakeholder in a Bangladeshi SME through their preferred channel is critical.

A single email or generic in-app notification is insufficient for Bangladeshi enterprises:
1. **Multi-Channel Imperative:** In Bangladesh, email deliverability and attention rates vary significantly. SMS and WhatsApp are the predominant channels for time-sensitive corporate communication.
2. **Domain-Specific Responsibility:** Different compliance domains (VAT/tax, customs, labor safety, company filings, banking) are managed by different officers or external consultants. Alerts must route to the designated domain owner with an automated backup escalation chain.
3. **Local Operational Realities:** Bangladesh Standard Time (BST, UTC+6), Friday/Saturday weekends, and national public holidays require quiet-hours suppression for routine updates, while life-safety and critical regulatory gaps require quiet-hours overrides.
4. **Telco Standards & Cost Control:** BTRC and mobile operator constraints (GSM-7 160 chars vs Unicode Bangla 70 chars, concatenated limits 153/67, masking vs non-masking sender IDs) require precise segment counting and monthly workspace caps.

---

## 2. Architecture & Design Principles

### 2.1 Unified Protocol & Outbox Pattern
The notification subsystem extends the existing Outbox pattern and implements the `ChannelAdapter` protocol:

```python
class ChannelAdapter(Protocol):
    def send(self, alert_id: str, recipient_address: str, subject: str, body: str, **kwargs) -> dict[str, Any]: ...
    def parse_delivery_webhook(self, request_body: bytes, headers: dict[str, str]) -> dict[str, Any]: ...
    def health_check(self) -> dict[str, Any]: ...
    def estimate_cost(self, text: str, recipient_address: str) -> float: ...
```

Outbound channels:
- **In-App:** Persisted to `notifications` with unread badges and action links.
- **Email:** Standard SMTP adapter (SES, Brevo, Resend) with responsive UTF-8 Bangla-safe HTML and plaintext templates.
- **SMS:** Provider-agnostic adapter with concrete implementations for SSL Wireless, Generic HTTP, and a Mock provider for local/CI environments.
- **WhatsApp:** Meta WhatsApp Business Cloud API adapter using pre-approved bilingual templates.
- **Optional (Feature-Flagged):** Telegram Bot, Slack incoming webhooks, Browser Web Push (VAPID).

### 2.2 Routing & Recipient Resolution
Alert routing follows a deterministic pipeline:
1. **Domain Tag Matching:** Maps 11 key compliance domains (`tax_vat`, `income_tax`, `customs`, `labor`, `company_law`, `banking`, `securities`, `environment`, `trade`, `data_privacy`, `general`) to a Primary and Backup user defined in the `compliance_owners` table.
2. **Watchers & Target Fallback:** For watched laws, subscribers are alerted. If no domain owner is assigned, alerts fall back to workspace Owners and Admins.
3. **Critical CC Rule:** All `critical` severity alerts automatically CC workspace Owners and Admins regardless of individual user preference.
4. **Channel Selection:** Computes $\text{Channels} = \text{Event Defaults} \cap \text{User Preferences} \cap \text{Plan Entitlements} \cap \text{Verified Contacts}$.

### 2.3 Bangladesh Telco & Regulatory Rules
- **Operator Prefix Normalization:** Numbers normalized to `+8801XXXXXXXXX` (valid prefixes: `013`, `014`, `015`, `016`, `017`, `018`, `019`).
- **Segment Encoding:**
  - **GSM-7 (Standard English):** Single segment $\le 160$ chars; multipart $\le 153$ chars/segment.
  - **Unicode (বাংলা / UTF-16):** Single segment $\le 70$ chars; multipart $\le 67$ chars/segment.
- **Pricing:** Non-masking baseline ~৳0.35/segment; Masking (LexGOV AI sender ID) ~৳0.55/segment.
- **BTRC Compliance:** Non-marketing transactional compliance notices only. OTP verification required before activation.

### 2.4 Quiet Hours & BST Calendar
- Configured per workspace in Bangladesh Standard Time (BST, UTC+6).
- Default quiet window: 22:00 to 08:00 BST.
- Default weekends: Friday (day 4) and Saturday (day 5).
- Bangladesh public holidays loaded from `backend/data/bd_holidays.json`.
- Held non-critical alerts are queued and released at 09:00 BST on the next business day.
- `critical` alerts override quiet hours and weekends.

### 2.5 Acknowledgment & Automated Escalation Loop
- High and critical alerts require explicit acknowledgment.
- Configurable escalation windows (default: 4 business hours for critical, 24 hours for high).
- If unacknowledged within the window, the worker background job `alert.escalate` automatically triggers the Backup Compliance Officer via SMS + Email. If still unacknowledged, it escalates to the Workspace Owner.
- Escalation terminates immediately once any authorized officer acknowledges the alert.

---

## 3. Data Model (Schema Version 7)

```sql
CREATE TABLE alert_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    version_hash TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE alerts (
    id TEXT PRIMARY KEY,
    alert_event_id TEXT NOT NULL REFERENCES alert_events(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    recipient_user_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    held_until TEXT,
    ack_required INTEGER NOT NULL DEFAULT 0,
    acked_at TEXT,
    acked_via TEXT,
    escalation_level INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE alert_deliveries (
    id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alerts(id),
    channel TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    provider_message_id TEXT,
    error_code TEXT,
    segments INTEGER DEFAULT 1,
    cost_estimate REAL DEFAULT 0.0,
    attempt INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE compliance_owners (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    domain_tag TEXT NOT NULL,
    primary_user_id TEXT NOT NULL REFERENCES users(id),
    backup_user_id TEXT REFERENCES users(id),
    PRIMARY KEY (workspace_id, domain_tag)
);

CREATE TABLE user_channels (
    user_id TEXT NOT NULL REFERENCES users(id),
    channel TEXT NOT NULL,
    address TEXT NOT NULL,
    display_address TEXT NOT NULL,
    verified_at TEXT,
    whatsapp_opt_in_at TEXT,
    opted_out_at TEXT,
    locale TEXT NOT NULL DEFAULT 'en',
    PRIMARY KEY (user_id, channel)
);

CREATE TABLE alert_preferences (
    user_id TEXT NOT NULL REFERENCES users(id),
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, event_type, channel)
);

CREATE TABLE workspace_alert_settings (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id),
    quiet_hours_start TEXT NOT NULL DEFAULT '22:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '08:00',
    timezone TEXT NOT NULL DEFAULT 'Asia/Dhaka',
    weekend_days TEXT NOT NULL DEFAULT '[4, 5]',
    escalation_critical_hours INTEGER NOT NULL DEFAULT 4,
    escalation_high_hours INTEGER NOT NULL DEFAULT 24,
    monthly_sms_cap INTEGER NOT NULL DEFAULT 100,
    monthly_whatsapp_cap INTEGER NOT NULL DEFAULT 100,
    digest_hour_bst INTEGER NOT NULL DEFAULT 9,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE channel_verification_codes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    channel TEXT NOT NULL,
    destination TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE short_links (
    code TEXT PRIMARY KEY,
    original_url TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL
);
```

---

## 4. Security & Data Privacy

1. **Strict Tenant Isolation:** All alert listings, deliveries, preferences, and compliance owner mappings filter strictly on `workspace_id`. IDOR test suite verifies zero cross-workspace data leakage.
2. **PII Masking:** Raw phone numbers and email addresses are masked in logs and user listings (`+88017****5678`, `c***r@domain.com`).
3. **Webhook Verification:** Inbound delivery webhooks (`/api/webhooks/alerts/*`) authenticate via HMAC-SHA256 signatures or shared secrets.
4. **Rate Limiting on OTPs:** SMS OTP verification limits resends to once every 60 seconds with a maximum of 3 verification attempts per 10-minute code.
