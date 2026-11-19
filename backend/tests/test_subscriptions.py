"""Subscription, entitlement gating, usage metering, IDOR, retention, and migration tests."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.db import Database, LEGACY_WORKSPACE_ID, SCHEMA_V1, SCHEMA_V2
from app.entitlements import EntitlementService
from app.plans import PLANS, PlanId
from app.usage import QuotaExceededError, UsageService

# Golden spec table for CI drift prevention
GOLDEN_CATALOG: dict[str, dict[str, Any]] = {
    "free": {
        "price_bdt": 0,
        "audit_history_days": 0,
        "personalization": "General, questionnaire-based",
        "capabilities": {
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "general",
            "personalized_checklist": "off",
            "ai_assistant": "limited",
            "regulatory_news": "on",
            "personalized_alerts": "off",
            "automated_monitoring": "off",
            "impact_analysis": "off",
            "risk_scoring": "off",
            "sop_upload": "off",
            "sop_comparison": "off",
            "gap_identification": "off",
            "action_plans": "off",
            "policy_drafts": "off",
            "technical_recommendations": "off",
            "citations": "on",
            "deadline_reminders": "off",
            "report_download": "off",
            "team_collaboration": "off",
            "api_integrations": "off",
            "priority_support": "off",
        },
        "limits": {
            "general_ai_questions": 5,
            "detailed_analyses": 0,
            "sop_documents": 0,
            "monitored_sources": 0,
            "business_profiles": 1,
            "team_members": 1,
        },
    },
    "starter": {
        "price_bdt": 999,
        "audit_history_days": 30,
        "personalization": "Basic company-specific",
        "capabilities": {
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "basic",
            "personalized_checklist": "on",
            "ai_assistant": "on",
            "regulatory_news": "on",
            "personalized_alerts": "basic",
            "automated_monitoring": "off",
            "impact_analysis": "basic",
            "risk_scoring": "basic",
            "sop_upload": "on",
            "sop_comparison": "limited",
            "gap_identification": "basic",
            "action_plans": "limited",
            "policy_drafts": "basic",
            "technical_recommendations": "off",
            "citations": "on",
            "deadline_reminders": "basic",
            "report_download": "basic",
            "team_collaboration": "off",
            "api_integrations": "off",
            "priority_support": "off",
        },
        "limits": {
            "general_ai_questions": 30,
            "detailed_analyses": 10,
            "sop_documents": 5,
            "monitored_sources": 1,
            "business_profiles": 1,
            "team_members": 1,
        },
    },
    "growth": {
        "price_bdt": 2999,
        "audit_history_days": 365,
        "personalization": "Document-based",
        "capabilities": {
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "detailed",
            "personalized_checklist": "on",
            "ai_assistant": "on",
            "regulatory_news": "on",
            "personalized_alerts": "on",
            "automated_monitoring": "on",
            "impact_analysis": "detailed",
            "risk_scoring": "on",
            "sop_upload": "on",
            "sop_comparison": "on",
            "gap_identification": "on",
            "action_plans": "on",
            "policy_drafts": "on",
            "technical_recommendations": "basic",
            "citations": "on",
            "deadline_reminders": "on",
            "report_download": "on",
            "team_collaboration": "on",
            "api_integrations": "off",
            "priority_support": "off",
        },
        "limits": {
            "general_ai_questions": 100,
            "detailed_analyses": 50,
            "sop_documents": 25,
            "monitored_sources": 2,
            "business_profiles": 1,
            "team_members": 3,
        },
    },
    "professional": {
        "price_bdt": 7999,
        "audit_history_days": 1095,
        "personalization": "Continuous and advanced",
        "capabilities": {
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "advanced",
            "personalized_checklist": "on",
            "ai_assistant": "on",
            "regulatory_news": "on",
            "personalized_alerts": "on",
            "automated_monitoring": "on",
            "impact_analysis": "advanced",
            "risk_scoring": "advanced",
            "sop_upload": "on",
            "sop_comparison": "on",
            "gap_identification": "advanced",
            "action_plans": "on",
            "policy_drafts": "advanced",
            "technical_recommendations": "advanced",
            "citations": "on",
            "deadline_reminders": "on",
            "report_download": "advanced",
            "team_collaboration": "on",
            "api_integrations": "limited",
            "priority_support": "on",
        },
        "limits": {
            "general_ai_questions": 300,
            "detailed_analyses": 200,
            "sop_documents": 100,
            "monitored_sources": 5,
            "business_profiles": 2,
            "team_members": 10,
        },
    },
}


def test_catalog_golden_drift():
    """Asserts app.plans.PLANS matches exact golden table to detect unintended drift."""
    for plan_id, golden in GOLDEN_CATALOG.items():
        assert plan_id in PLANS, f"Missing plan: {plan_id}"
        actual = PLANS[plan_id]
        assert actual.price_bdt_monthly == golden["price_bdt"], f"Price mismatch for {plan_id}"
        assert actual.audit_history_days == golden["audit_history_days"], f"Retention mismatch for {plan_id}"
        assert actual.personalization_label == golden["personalization"], f"Personalization mismatch for {plan_id}"

        for cap_key, expected_level in golden["capabilities"].items():
            assert (
                actual.capabilities.get(cap_key) == expected_level
            ), f"Capability mismatch for {plan_id}.{cap_key}: expected {expected_level}, got {actual.capabilities.get(cap_key)}"

        for metric_key, expected_limit in golden["limits"].items():
            assert (
                actual.limits.get(metric_key) == expected_limit
            ), f"Limit mismatch for {plan_id}.{metric_key}: expected {expected_limit}, got {actual.limits.get(metric_key)}"


def _signup_user(client: TestClient, email: str, plan: str = "free") -> dict[str, Any]:
    res = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "SecurePassword123!", "company_name": f"{email} Co"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    ws_id = data["workspace"]["id"]
    if plan != "free":
        client.app.state.services.subscriptions.change_plan(ws_id, plan)
    return data


@pytest.mark.parametrize("plan_id,allowed", [
    ("free", False),
    ("starter", True),
    ("growth", True),
    ("professional", True),
])
def test_capability_matrix_enforcement(client: TestClient, plan_id: str, allowed: bool):
    """Verifies that endpoints gated by sop_upload and report_download enforce plan matrix."""
    user = _signup_user(client, f"{plan_id}@test.com", plan=plan_id)
    ws_id = user["workspace"]["id"]

    # 1. Test company profile creation (allowed for all tiers)
    cp_res = client.post("/api/company-profile", json={"company_name": "Matrix Co", "industry": "retail", "country": "bangladesh"})
    assert cp_res.status_code == 200
    company_id = cp_res.json()["id"]

    # 2. Test SOP Upload
    sop_text = "Section 1: Operating procedure for deliveries."
    up_res = client.post(
        "/api/documents/upload",
        data={"company_profile_id": company_id},
        files={"file": ("sop.txt", sop_text.encode(), "text/plain")},
    )
    if allowed:
        assert up_res.status_code == 200, up_res.text
        doc_id = up_res.json()["document_id"]

        # Test Analysis execution
        an_res = client.post("/api/analyze", json={"company_profile_id": company_id, "document_id": doc_id})
        assert an_res.status_code == 200
        plan_id_created = an_res.json()["id"]

        # Test Report Download
        rep_res = client.get(f"/api/action-plans/{plan_id_created}/report")
        assert rep_res.status_code == 200
        assert "# Compliance Action Plan" in rep_res.text
    else:
        assert up_res.status_code == 403
        err = up_res.json()
        assert err["code"] == "FEATURE_NOT_IN_PLAN"
        assert err["capability"] == "sop_upload"
        assert err["required_plan"] == "starter"


def test_quota_exhaustion_returns_429(client: TestClient):
    """Verifies that exhausting detailed_analyses quota returns 429 with upgrade metadata."""
    user = _signup_user(client, "quota_user@test.com", plan="starter")
    ws_id = user["workspace"]["id"]
    db = client.app.state.services.db
    usage_svc = client.app.state.services.usage

    cp = client.post("/api/company-profile", json={"company_name": "Quota Co", "industry": "retail", "country": "bangladesh"}).json()
    up = client.post(
        "/api/documents/upload",
        data={"company_profile_id": cp["id"]},
        files={"file": ("sop.txt", b"Section 6.1: VAT Submission Timelines within 30 days.", "text/plain")},
    ).json()

    # Starter plan detailed_analyses limit is 10.
    # Simulate 10 used analyses in the current window.
    window_start, _ = usage_svc.resolve_window(ws_id)
    db.increment_usage_counter(ws_id, "detailed_analyses", window_start, amount=10)

    # 11th request must fail with 429
    res = client.post("/api/analyze", json={"company_profile_id": cp["id"], "document_id": up["document_id"]})
    assert res.status_code == 429, res.text
    body = res.json()
    assert body["code"] == "QUOTA_EXCEEDED"
    assert body["metric"] == "detailed_analyses"
    assert body["limit"] == 10
    assert body["used"] == 10
    assert body["upgrade_to"] == "growth"

    # Counter should still be 10, not incremented
    used = db.get_usage_counter(ws_id, "detailed_analyses", window_start)
    assert used == 10


def test_concurrency_quota_safety(tmp_path: Path):
    """Verifies that concurrent reservations cannot double-spend quota under race conditions."""
    from app.config import Settings
    from app.main import create_app
    from tests.conftest import FakeLLM, make_settings

    app = create_app(make_settings(tmp_path), llm=FakeLLM())
    db = app.state.services.db
    entitlements = app.state.services.entitlements
    usage_svc = UsageService(db, entitlements)
    sub_svc = app.state.services.subscriptions

    ws = db.create_workspace("Concurrent Workspace")
    sub_svc.provision_free_subscription(ws["id"])
    sub_svc.change_plan(ws["id"], "starter")  # detailed_analyses limit = 10

    window_start, _ = usage_svc.resolve_window(ws["id"])
    # Pre-fill to 9
    db.increment_usage_counter(ws["id"], "detailed_analyses", window_start, amount=9)

    results: list[bool] = []
    errors: list[Exception] = []

    def attempt_reserve(idx: int):
        try:
            usage_svc.reserve(
                workspace_id=ws["id"],
                metric="detailed_analyses",
                idempotency_key=f"concurrent_key_{idx}",
                amount=1,
            )
            results.append(True)
        except QuotaExceededError as e:
            errors.append(e)

    # Launch 6 concurrent threads competing for 1 remaining slot
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(attempt_reserve, i) for i in range(6)]
        concurrent.futures.wait(futures)

    # Exactly 1 must have succeeded, 5 must have failed with QuotaExceededError
    assert len(results) == 1
    assert len(errors) == 5
    total_used = db.get_usage_counter(ws["id"], "detailed_analyses", window_start)
    assert total_used == 10  # Never allowed to reach 11+


def test_idor_cross_workspace_isolation(client: TestClient, tmp_path: Path):
    """Verifies User A cannot read, analyze, or download reports for User B's resources."""
    user_a = _signup_user(client, "user_a@test.com", plan="starter")
    cp_a = client.post("/api/company-profile", json={"company_name": "Company A", "industry": "retail", "country": "bangladesh"}).json()
    up_a = client.post(
        "/api/documents/upload",
        data={"company_profile_id": cp_a["id"]},
        files={"file": ("sop_a.txt", b"Section 6.1: VAT returns 30 days.", "text/plain")},
    ).json()
    plan_a = client.post("/api/analyze", json={"company_profile_id": cp_a["id"], "document_id": up_a["document_id"]}).json()

    # User B logs in
    client.post("/api/auth/logout")
    user_b = _signup_user(client, "user_b@test.com", plan="growth")

    # User B attempts to access User A's action plan
    get_res = client.get(f"/api/action-plans/{plan_a['id']}")
    assert get_res.status_code == 404

    # User B attempts to download User A's markdown report
    rep_res = client.get(f"/api/action-plans/{plan_a['id']}/report")
    assert rep_res.status_code == 404

    # User B attempts to run an analysis referencing User A's document
    cp_b = client.post("/api/company-profile", json={"company_name": "Company B", "industry": "retail", "country": "bangladesh"}).json()
    an_res = client.post("/api/analyze", json={"company_profile_id": cp_b["id"], "document_id": up_a["document_id"]})
    assert an_res.status_code == 404


def test_retention_and_purge(client: TestClient):
    """Verifies retention window hides expired plans and purge-expired deletes them."""
    user = _signup_user(client, "retention@test.com", plan="starter")
    ws_id = user["workspace"]["id"]
    db = client.app.state.services.db

    # Create an old action plan dated 45 days ago (starter retention is 30 days)
    old_time = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(timespec="seconds")
    old_plan = {
        "id": "old_plan_123",
        "company": "Retention Co",
        "regulation": "NBR VAT",
        "change_summary": "Summary",
        "impact_score": 50,
        "urgency": "medium",
        "findings": [],
        "policy_draft": [],
        "technical_fixes": [],
        "disclaimer": "test",
        "document_name": "sop.txt",
        "regulation_version_hash": "hash",
        "model": "fake",
        "created_at": old_time,
    }
    db.save_action_plan(old_plan, "cp_test", "doc_test", workspace_id=ws_id)
    # Manually backdate the created_at in the database row
    with db._lock:
        db._conn.execute("UPDATE action_plans SET created_at = ? WHERE id = ?", (old_time, "old_plan_123"))
        db._conn.commit()

    # User attempts to fetch expired plan
    res = client.get(f"/api/action-plans/{old_plan['id']}")
    assert res.status_code == 404

    # Run CLI purge
    from app.cli import purge_expired_cmd
    entitlements = client.app.state.services.entitlements
    purge_expired_cmd(db, entitlements)

    # Verify plan is physically purged from DB
    row = db._fetchone("SELECT * FROM action_plans WHERE id = ?", ("old_plan_123",))
    assert row is None


def test_migration_v1_to_v2(tmp_path: Path):
    """Verifies that a database initialized with V1 schema upgrades to V2 cleanly."""
    db_file = tmp_path / "v1_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA_V1)
    # Insert legacy company profile and document
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO company_profiles (id, company_name, industry, country, created_at) VALUES (?, ?, ?, ?, ?)",
        ("legacy_cp_1", "Legacy Corp", "retail", "bangladesh", now),
    )
    conn.execute(
        "INSERT INTO documents (id, company_profile_id, filename, text, chunk_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("legacy_doc_1", "legacy_cp_1", "legacy.txt", "content", 1, now),
    )
    conn.commit()
    conn.close()

    # Initialize new Database instance on top of V1 DB
    db = Database(db_file)

    # Check version is now upgraded to latest
    assert db.get_schema_version() == 7

    # Check that legacy records now have workspace_id set to LEGACY_WORKSPACE_ID
    cp = db.get_company("legacy_cp_1")
    assert cp is not None
    assert cp["workspace_id"] == LEGACY_WORKSPACE_ID

    doc = db.get_document("legacy_doc_1")
    assert doc is not None
    assert doc["workspace_id"] == LEGACY_WORKSPACE_ID

    # Legacy workspace has subscription
    sub = db.get_subscription(LEGACY_WORKSPACE_ID)
    assert sub is not None
    assert sub["plan_id"] == "professional"
    db.close()


def test_migration_v2_to_v3_seeds_regulations_and_preserves_data(tmp_path: Path):
    """Verifies that V2 database upgrades to V3 without data loss and seeds sample regulation."""
    db_file = tmp_path / "v2_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA_V1)
    conn.executescript(SCHEMA_V2)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    conn.execute("INSERT INTO schema_version VALUES (2, ?)", (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    conn.close()

    db = Database(db_file)
    assert db.get_schema_version() == 7

    # Verify sample regulation and versions were seeded
    reg = db.get_regulation("nbr-vat-sro-4.2")
    assert reg is not None
    assert reg["title"] == "NBR VAT SRO Clause 4.2"

    versions = db.list_regulation_versions("nbr-vat-sro-4.2")
    assert len(versions) >= 2
    assert any(v["is_sample"] == 1 for v in versions)

    # Verify sample news seeded
    news = db.list_news_items()
    assert len(news) >= 1

    db.close()


def test_migration_v3_to_v4_adds_supabase_and_ocr_columns(tmp_path: Path):
    """Verifies that V3 database upgrades to V4 additively without data loss."""
    db_file = tmp_path / "v3_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA_V1)
    conn.executescript(SCHEMA_V2)
    from app.db import SCHEMA_V3
    conn.executescript(SCHEMA_V3)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    conn.execute("INSERT INTO schema_version VALUES (3, ?)", (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    conn.close()

    db = Database(db_file)
    assert db.get_schema_version() == 7

    # Verify additive columns exist
    with db._lock:
        user_cols = [c[1] for c in db._conn.execute("PRAGMA table_info(users)").fetchall()]
        assert "supabase_user_id" in user_cols

        doc_cols = [c[1] for c in db._conn.execute("PRAGMA table_info(documents)").fetchall()]
        assert "extraction_method" in doc_cols
        assert "ocr_confidence" in doc_cols
        assert "ocr_notes" in doc_cols

    db.close()


def test_migration_v4_to_v5_adds_legal_library_tables_and_fts(tmp_path: Path):
    """Verifies that V4 database upgrades to V5 adding legal library tables and FTS5 index."""
    db_file = tmp_path / "v4_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA_V1)
    conn.executescript(SCHEMA_V2)
    from app.db import SCHEMA_V3
    conn.executescript(SCHEMA_V3)
    conn.execute("ALTER TABLE users ADD COLUMN supabase_user_id TEXT")
    conn.execute("ALTER TABLE documents ADD COLUMN extraction_method TEXT DEFAULT 'text'")
    conn.execute("ALTER TABLE documents ADD COLUMN ocr_confidence REAL")
    conn.execute("ALTER TABLE documents ADD COLUMN ocr_notes TEXT")
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    conn.execute("INSERT INTO schema_version VALUES (4, ?)", (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    conn.close()

    db = Database(db_file)
    assert db.get_schema_version() == 7

    # Verify new tables exist
    with db._lock:
        tables = [r[0] for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()]
        assert "law_sources" in tables
        assert "laws" in tables
        assert "law_versions" in tables
        assert "law_sections" in tables
        assert "law_relations" in tables
        assert "law_ingest_runs" in tables
        assert "law_watchlist" in tables
        assert "law_review_queue" in tables
        assert "law_sections_fts" in tables

    db.close()


def test_migration_v6_to_v7_adds_alert_center_tables(tmp_path: Path):
    """Verifies that database upgrades to V7 additively creating Alert Center tables."""
    db_file = tmp_path / "v7_test.db"
    db = Database(db_file)
    assert db.get_schema_version() == 7

    with db._lock:
        tables = [r[0] for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "alert_events" in tables
        assert "alerts" in tables
        assert "alert_deliveries" in tables
        assert "compliance_owners" in tables
        assert "user_channels" in tables
        assert "alert_preferences" in tables
        assert "workspace_alert_settings" in tables
        assert "sms_otps" in tables
        assert "short_links" in tables
    db.close()
