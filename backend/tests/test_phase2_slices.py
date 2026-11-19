"""Tests for Phase 2 Feature Slices: S0 (Admin & Foundations) and S1 (News & Notifications)."""

import json
import pytest
from starlette.testclient import TestClient

from app.db import Database, new_id
from app.main import create_app
from app.plans import CAPABILITIES, PLANS
from tests.conftest import FakeLLM


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "development")
    db_path = tmp_path / "compliance.db"
    app = create_app(llm=FakeLLM())
    client = TestClient(app, base_url="http://testserver")
    return client, Database(db_path)


def _signup(client: TestClient, email: str, password: str = "SecurePassword123!", name: str = "Test User"):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "full_name": name, "company_name": f"{name}'s Co"},
    )


def test_request_id_middleware(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "x-request-id" in res.headers
    assert len(res.headers["x-request-id"]) > 0


def test_platform_admin_access_control(client_and_db):
    client, db = client_and_db
    # Signup regular user
    res = _signup(client, "regular@user.com")
    assert res.status_code == 200
    assert res.json()["user"]["is_platform_admin"] is False

    # Try accessing admin endpoint -> 403
    admin_res = client.get("/api/admin/queue")
    assert admin_res.status_code == 403
    assert "Platform administrator" in admin_res.json()["detail"]

    # Grant admin privileges to this user
    user = db.get_user_by_email("regular@user.com")
    db.set_platform_admin(user["id"], is_admin=True)

    # Now accessing admin endpoint -> 200
    admin_res2 = client.get("/api/admin/queue")
    assert admin_res2.status_code == 200
    data = admin_res2.json()
    assert "pending_count" in data
    assert "running_count" in data
    assert "dead_letter_count" in data


def test_admin_publish_regulation_enqueues_fan_out(client_and_db):
    client, db = client_and_db
    res = _signup(client, "superadmin@corp.com")
    user = db.get_user_by_email("superadmin@corp.com")
    db.set_platform_admin(user["id"], is_admin=True)

    # Regulation seeded in V3 migration: 'nbr-vat-sro-4.2'
    reg_id = "nbr-vat-sro-4.2"
    v = db.create_regulation_version(
        regulation_id=reg_id,
        version_label="v2026-test",
        text="All registered businesses must file electronically by the 15th.",
        status="pending_review",
    )

    # Regulatory change linking to this version
    db.create_regulatory_change(
        regulation_id=reg_id,
        from_version_id="sample-before-v1",
        to_version_id=v["id"],
        summary="Mandatory electronic VAT submission within 15 days.",
        change_type="amendment",
        obligations=["File return electronically by 15th"],
    )

    # Publish via admin endpoint
    pub_res = client.post(f"/api/admin/regulations/versions/{v['id']}/publish")
    assert pub_res.status_code == 200
    assert pub_res.json()["version"]["status"] == "published"

    # Verify worker job was enqueued
    job = db.acquire_job_lease(lease_seconds=30)
    assert job is not None
    assert job["type"] == "fan_out_alerts"
    assert job["payload"]["regulation_id"] == reg_id


def test_s1_news_feed_and_filtering(client_and_db):
    client, db = client_and_db
    _signup(client, "reader@corp.com")

    # Create news items
    db.create_news_item(
        title="NBR Electronic VAT Gazette",
        content="All registered logistics firms must file by the 15th.",
        sector="Logistics & Freight",
        jurisdiction="Bangladesh",
        source_url="https://nbr.gov.bd/gazette/1",
    )
    db.create_news_item(
        title="Cross-border E-Commerce Remittance Notice",
        content="New settlement guidelines under Circular 14.",
        sector="E-commerce",
        jurisdiction="Bangladesh",
        source_url="https://bb.org.bd/fe14",
    )

    # List all
    res = client.get("/api/news")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 2

    # Filter by sector
    res_logistics = client.get("/api/news?sector=Logistics+%26+Freight")
    assert res_logistics.status_code == 200
    assert len(res_logistics.json()["items"]) == 1
    assert "Logistics" in res_logistics.json()["items"][0]["sector"]

    # Filter by keyword tag
    res_tag = client.get("/api/news?tag=remittance")
    assert res_tag.status_code == 200
    assert len(res_tag.json()["items"]) == 1
    assert "Cross-border" in res_tag.json()["items"][0]["title"]


def test_s1_notifications_read_and_unread_counts(client_and_db):
    client, db = client_and_db
    res1 = _signup(client, "user1@corp.com")
    u1 = db.get_user_by_email("user1@corp.com")
    ws1 = res1.json()["workspace"]["id"]

    # Create 2 notifications for user1
    n1 = db.create_notification(
        workspace_id=ws1,
        user_id=u1["id"],
        title="Important Regulatory Update",
        body="Review your SOP.",
        link="/news",
    )
    n2 = db.create_notification(
        workspace_id=ws1,
        user_id=u1["id"],
        title="Filing Deadline Approaching",
        body="Filing is due in 3 days.",
        link="/account",
    )

    # Check unread count
    list_res = client.get("/api/notifications")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["unread_count"] == 2
    assert len(data["notifications"]) == 2

    # Mark one read
    read_res = client.patch(f"/api/notifications/{n1['id']}/read")
    assert read_res.status_code == 200

    list_res2 = client.get("/api/notifications")
    assert list_res2.json()["unread_count"] == 1

    # Mark all read
    all_read_res = client.post("/api/notifications/mark-all-read")
    assert all_read_res.status_code == 200
    assert all_read_res.json()["count"] == 1

    list_res3 = client.get("/api/notifications")
    assert list_res3.json()["unread_count"] == 0


def test_s1_notifications_idor_isolation(client_and_db):
    client, db = client_and_db
    # User 1
    res1 = _signup(client, "alpha@company.com")
    u1 = db.get_user_by_email("alpha@company.com")
    ws1 = res1.json()["workspace"]["id"]
    n1 = db.create_notification(
        workspace_id=ws1, user_id=u1["id"], title="Confidential Notice", body="Only for Alpha.", link="/news"
    )

    # User 2 in different workspace
    client.post("/api/auth/logout")
    _signup(client, "beta@company.com")

    # User 2 list notifications -> should be empty
    beta_list = client.get("/api/notifications")
    assert beta_list.status_code == 200
    assert beta_list.json()["unread_count"] == 0
    assert len(beta_list.json()["notifications"]) == 0

    # User 2 tries to mark user 1's notification read -> 404
    bad_read = client.patch(f"/api/notifications/{n1['id']}/read")
    assert bad_read.status_code == 404


def test_s2_monitoring_free_plan_gated(client_and_db):
    client, db = client_and_db
    _signup(client, "free_subscriber@corp.com")

    # Try to subscribe on Free plan -> 403
    res = client.post("/api/monitoring/subscriptions", json={"regulation_id": "nbr-vat-sro-4.2"})
    assert res.status_code == 403
    data = res.json()
    assert data["code"] == "FEATURE_NOT_IN_PLAN"
    assert data["capability"] == "personalized_alerts"


def test_s2_monitoring_quota_enforcement_and_unsub(client_and_db):
    client, db = client_and_db
    # Signup starter user (quota: 1 monitored source)
    res = _signup(client, "starter_subscriber@corp.com")
    u = db.get_user_by_email("starter_subscriber@corp.com")
    ws = res.json()["workspace"]

    # Upgrade to Starter plan
    from app.subscriptions import SubscriptionService
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws["id"], "starter")

    # Create 2 regulations in db
    reg2 = db.create_regulation(
        title="Customs Harmonization Notice",
        country="Bangladesh",
        sector="Trade",
    )

    # Subscribe 1 -> succeeds
    sub1_res = client.post("/api/monitoring/subscriptions", json={"regulation_id": "nbr-vat-sro-4.2"})
    assert sub1_res.status_code == 200
    assert sub1_res.json()["regulation_id"] == "nbr-vat-sro-4.2"

    # Subscribe 2 -> exceeds limit of 1 -> 429
    sub2_res = client.post("/api/monitoring/subscriptions", json={"regulation_id": reg2["id"]})
    assert sub2_res.status_code == 429
    assert sub2_res.json()["code"] == "QUOTA_EXCEEDED"
    assert sub2_res.json()["metric"] == "monitored_sources"

    # Unsubscribe 1 -> succeeds
    unsub_res = client.delete("/api/monitoring/subscriptions/nbr-vat-sro-4.2")
    assert unsub_res.status_code == 200

    # Now subscribe 2 -> succeeds because quota was freed
    sub2_again = client.post("/api/monitoring/subscriptions", json={"regulation_id": reg2["id"]})
    assert sub2_again.status_code == 200


def test_s2_worker_fan_out_and_auto_analysis(client_and_db):
    client, db = client_and_db
    # Create Growth subscriber
    res = _signup(client, "growth_team@corp.com")
    ws_id = res.json()["workspace"]["id"]
    from app.subscriptions import SubscriptionService
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws_id, "growth")

    # Subscribe to nbr-vat-sro-4.2
    db.subscribe_monitor(ws_id, "nbr-vat-sro-4.2")

    # Upload sample SOP document
    comp_res = client.post("/api/company-profile", json={"company_name": "Growth Logistics Ltd.", "industry": "Logistics", "country": "Bangladesh"})
    comp_id = comp_res.json()["id"]
    doc_res = client.post("/api/documents/sample", json={"company_profile_id": comp_id})
    assert doc_res.status_code == 200

    # Create change record
    chg = db.create_regulatory_change(
        regulation_id="nbr-vat-sro-4.2",
        from_version_id="sample-before-v1",
        to_version_id="sample-after-v2",
        summary="Mandatory 15-day e-VAT filing window.",
        change_type="amendment",
        obligations=["File return in 15 days"],
    )

    from app.worker import Worker
    from app.adapters import ConsoleNotifier, FakeClock
    worker = Worker(db=db, clock=FakeClock(), notifier=ConsoleNotifier())

    # Execute fan_out_alerts
    worker.handle_fan_out_alerts({"change_id": chg["id"], "regulation_id": "nbr-vat-sro-4.2"})

    # Check notification was created
    u = db.get_user_by_email("growth_team@corp.com")
    notifs = db.list_notifications(ws_id, u["id"])
    assert len(notifs) >= 1
    assert "Regulatory Alert" in notifs[0]["title"]

    # Check outbox email was enqueued
    outbox_items = db.fetch_pending_outbox()
    assert any(item["channel"] == "email" for item in outbox_items)

    # Check auto_analysis job was enqueued
    job = db.acquire_job_lease()
    assert job is not None
    assert job["type"] == "auto_analysis"


def test_s3_deadlines_crud_and_gating(client_and_db):
    client, db = client_and_db
    # Signup user and upgrade to Starter (deadline_reminders: basic)
    res = _signup(client, "deadline_user@corp.com")
    ws_id = res.json()["workspace"]["id"]
    from app.subscriptions import SubscriptionService
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws_id, "starter")

    # Create manual deadline
    dl_res = client.post(
        "/api/deadlines",
        json={"title": "Q4 VAT Submission", "due_date": "2026-12-15"},
    )
    assert dl_res.status_code == 200
    dl_id = dl_res.json()["id"]

    # List deadlines
    list_res = client.get("/api/deadlines")
    assert list_res.status_code == 200
    assert len(list_res.json()["deadlines"]) == 1

    # Update deadline
    up_res = client.patch(f"/api/deadlines/{dl_id}", json={"due_date": "2026-12-20"})
    assert up_res.status_code == 200
    assert up_res.json()["due_date"] == "2026-12-20"

    # Delete deadline
    del_res = client.delete(f"/api/deadlines/{dl_id}")
    assert del_res.status_code == 200

    # Ensure list is empty
    list_res2 = client.get("/api/deadlines")
    assert len(list_res2.json()["deadlines"]) == 0


def test_s3_deadline_extractor_verified_vs_unverified():
    from app.deadlines import extract_and_verify_deadlines
    from tests.conftest import FakeLLM

    llm = FakeLLM()
    # Official regulation containing "within 15 calendar days"
    reg_text = "All registered businesses must file Mushak-9.1 within 15 calendar days after the tax period."
    deadlines = extract_and_verify_deadlines(llm, reg_text, "NBR VAT SRO")
    assert len(deadlines) == 1
    assert deadlines[0]["status"] == "pending_confirmation"
    assert deadlines[0]["flagged_for_review"] is False

    # Unverified quote test
    unrelated_text = "This document only discusses general employment conditions and office safety."
    deadlines2 = extract_and_verify_deadlines(llm, unrelated_text, "Office Safety")
    assert len(deadlines2) == 1
    assert deadlines2[0]["status"] == "needs_review"
    assert deadlines2[0]["flagged_for_review"] is True


def test_s4_assistant_ask_free_vs_paid_threads(client_and_db):
    client, db = client_and_db
    # Free user
    res_free = _signup(client, "free_asker@corp.com")
    u_free = db.get_user_by_email("free_asker@corp.com")
    ws_free_id = res_free.json()["workspace"]["id"]

    # Ask question on Free plan
    ask_res = client.post(
        "/api/assistant/ask",
        json={"question": "What is the mandatory filing deadline under NBR VAT Clause 4.2?"},
    )
    assert ask_res.status_code == 200
    # Parse SSE events
    events = [json.loads(line[len("data: "):]) for line in ask_res.text.splitlines() if line.startswith("data: ")]
    completed = next(e for e in events if e["type"] == "completed")
    assert "within 15 calendar days" in completed["answer"]
    assert len(completed["citations"]) >= 1

    # Check Free threads: retention is 0 days, not persisted
    threads = db.list_assistant_threads(ws_free_id, u_free["id"])
    assert len(threads) == 0

    # Starter user (threads persisted)
    client.post("/api/auth/logout")
    res_starter = _signup(client, "starter_asker@corp.com")
    u_starter = db.get_user_by_email("starter_asker@corp.com")
    ws_starter_id = res_starter.json()["workspace"]["id"]

    from app.subscriptions import SubscriptionService
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws_starter_id, "starter")

    ask_res2 = client.post(
        "/api/assistant/ask",
        json={"question": "What is the deadline for filing Mushak-9.1?"},
    )
    assert ask_res2.status_code == 200

    # Check Starter threads persisted
    threads_starter = db.list_assistant_threads(ws_starter_id, u_starter["id"])
    assert len(threads_starter) == 1
    msgs = db.list_assistant_messages(threads_starter[0]["id"])
    assert len(msgs) == 2  # user + assistant


def test_s4_assistant_scope_guard_redirects_off_topic(client_and_db):
    client, db = client_and_db
    _signup(client, "offtopic_user@corp.com")

    # Ask off-topic inquiry (poem)
    ask_res = client.post(
        "/api/assistant/ask",
        json={"question": "Write me a romantic poem about sunsets."},
    )
    assert ask_res.status_code == 200
    events = [json.loads(line[len("data: "):]) for line in ask_res.text.splitlines() if line.startswith("data: ")]
    completed = next(e for e in events if e["type"] == "completed")
    assert completed["in_scope"] is False
    assert "cannot assist with non-business" in completed["answer"]


def test_s5_team_collaboration_invites_rbac_and_seat_freeze(client_and_db):
    client, db = client_and_db
    from app.subscriptions import SubscriptionService

    # 1. Signup Free user (1 seat limit)
    res_free = _signup(client, "owner_free@corp.com")
    ws_free_id = res_free.json()["workspace"]["id"]
    u_free = db.get_user_by_email("owner_free@corp.com")

    # Free plan cannot invite (gated by team_collaboration)
    inv_res = client.post("/api/team/invites", json={"email": "colleague@corp.com", "role": "member"})
    assert inv_res.status_code in (402, 403)

    # 2. Upgrade to Growth (3 seats)
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws_free_id, "growth")

    # Invite 1 (admin)
    inv1_res = client.post("/api/team/invites", json={"email": "alice@corp.com", "role": "admin"})
    assert inv1_res.status_code == 200
    token1 = inv1_res.json()["token"]

    # Invite 2 (member)
    inv2_res = client.post("/api/team/invites", json={"email": "bob@corp.com", "role": "member"})
    assert inv2_res.status_code == 200
    token2 = inv2_res.json()["token"]

    # Total seats now: 1 member + 2 pending invites = 3. 4th should fail with QuotaExceeded
    inv3_res = client.post("/api/team/invites", json={"email": "charlie@corp.com", "role": "member"})
    assert inv3_res.status_code in (402, 403, 429)

    # Revoke Bob's invite to free up seat
    rev_res = client.delete(f"/api/team/invites/{inv2_res.json()['id']}")
    assert rev_res.status_code == 200

    # Now charlie can be invited
    inv3_res2 = client.post("/api/team/invites", json={"email": "charlie@corp.com", "role": "member"})
    assert inv3_res2.status_code == 200

    # 3. Alice signs up and accepts invite
    client.post("/api/auth/logout")
    res_alice = _signup(client, "alice@corp.com")
    accept_res = client.post("/api/team/invites/accept", json={"token": token1})
    assert accept_res.status_code == 200
    assert accept_res.json()["role"] == "admin"

    # Alice can post comments
    cmt_res = client.post(
        "/api/comments",
        json={"resource_type": "finding", "resource_id": "f_123", "content": "Verified against Bangladesh Gazette."},
    )
    assert cmt_res.status_code == 200
    assert cmt_res.json()["content"] == "Verified against Bangladesh Gazette."

    # Alice (admin) cannot checkout / change billing plan (owner only)
    checkout_res = client.post(
        "/api/billing/checkout",
        json={"plan_id": "professional", "return_url": "http://localhost/return"},
    )
    assert checkout_res.status_code == 403

    # 4. Downgrade workspace to Free (1 seat). Alice is seat #2, so she becomes frozen!
    sub_svc.change_plan(ws_free_id, "free")

    # Verify members endpoint lists Alice as frozen
    mems_res = client.get("/api/team/members")
    assert mems_res.status_code == 200
    members = mems_res.json()["members"]
    alice_mem = next(m for m in members if m["email"] == "alice@corp.com")
    assert alice_mem["is_frozen"] is True
    assert alice_mem["effective_role"] == "viewer"

    # Alice trying to post comment now fails with 403 (frozen)
    frozen_cmt = client.post(
        "/api/comments",
        json={"resource_type": "finding", "resource_id": "f_123", "content": "Another comment"},
    )
    assert frozen_cmt.status_code == 403
    assert "restricted to read-only" in frozen_cmt.json()["detail"]


def test_s5_finding_reviews_and_adjusted_impact_score(client_and_db):
    client, db = client_and_db
    res = _signup(client, "reviewer@corp.com")
    ws_id = res.json()["workspace"]["id"]
    u = db.get_user_by_email("reviewer@corp.com")

    # Create dummy action plan with 2 findings (high severity, impact_score = 80)
    plan_id = "plan_test_review"
    plan_data = {
        "id": plan_id,
        "regulation": "VAT SRO 2026",
        "impact_score": 80,
        "created_at": "2026-11-08T00:00:00",
        "findings": [
            {"id": "finding_1", "severity": "high", "issue": "Missing VAT register", "citation": "SRO 4.2"},
            {"id": "finding_2", "severity": "high", "issue": "Missing withholding certificate", "citation": "SRO 5.1"},
        ],
    }
    db.save_action_plan(plan_data, "comp_1", "doc_1", workspace_id=ws_id)

    # 1. Reject finding_1
    rev1 = client.post(
        "/api/finding-reviews",
        json={
            "plan_id": plan_id,
            "finding_id": "finding_1",
            "status": "rejected",
            "note": "Applicable only to manufacturers, not our service model.",
        },
    )
    assert rev1.status_code == 200
    # 1 of 2 equal-weight findings rejected -> 50% ratio -> adjusted score 40
    assert rev1.json()["adjusted_impact_score"] == 40

    # 2. Reject finding_2 as well
    rev2 = client.post(
        "/api/finding-reviews",
        json={
            "plan_id": plan_id,
            "finding_id": "finding_2",
            "status": "rejected",
        },
    )
    assert rev2.status_code == 200
    assert rev2.json()["adjusted_impact_score"] == 0

    # 3. Approve finding_1
    rev3 = client.post(
        "/api/finding-reviews",
        json={
            "plan_id": plan_id,
            "finding_id": "finding_1",
            "status": "approved",
        },
    )
    assert rev3.status_code == 200
    assert rev3.json()["adjusted_impact_score"] == 40

    # 4. Query reviews
    get_rev = client.get(f"/api/finding-reviews?plan_id={plan_id}")
    assert get_rev.status_code == 200
    assert get_rev.json()["original_impact_score"] == 80
    assert get_rev.json()["adjusted_impact_score"] == 40
    assert len(get_rev.json()["reviews"]) == 2


def test_s6_api_integrations_v1_and_rate_limiting(client_and_db):
    client, db = client_and_db
    from app.subscriptions import SubscriptionService

    # 1. Free plan cannot create API keys
    res_free = _signup(client, "free_api@corp.com")
    ws_free_id = res_free.json()["workspace"]["id"]
    key_fail = client.post("/api/settings/api-keys", json={"name": "Test Key"})
    assert key_fail.status_code in (402, 403)

    # 2. Upgrade to Professional (api_integrations = on)
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws_free_id, "professional")

    # Create API key with reports:read scope
    key_res = client.post(
        "/api/settings/api-keys",
        json={"name": "ERP Integration", "scopes": ["reports:read", "checklist:read"]},
    )
    assert key_res.status_code == 200
    raw_key = key_res.json()["secret_key"]
    assert raw_key.startswith("cos_live_")

    # Max 3 active keys enforcement
    client.post("/api/settings/api-keys", json={"name": "Key 2", "scopes": ["reports:read"]})
    client.post("/api/settings/api-keys", json={"name": "Key 3", "scopes": ["reports:read"]})
    key_4_fail = client.post("/api/settings/api-keys", json={"name": "Key 4", "scopes": ["reports:read"]})
    assert key_4_fail.status_code == 400
    assert "Maximum of 3 active API keys" in key_4_fail.json()["detail"]

    # 3. Test /api/v1 endpoints with Bearer key
    # Anonymous /api/v1 call -> 401
    anon_v1 = client.get("/api/v1/reports")
    assert anon_v1.status_code == 401

    # Valid Bearer call -> 200
    auth_headers = {"Authorization": f"Bearer {raw_key}"}
    v1_reports = client.get("/api/v1/reports", headers=auth_headers)
    assert v1_reports.status_code == 200
    assert "reports" in v1_reports.json()

    # Scope check: key has 'reports:read' and 'checklist:read', lacks 'findings:read'
    v1_findings = client.get("/api/v1/findings", headers=auth_headers)
    assert v1_findings.status_code == 403
    assert "findings:read" in v1_findings.json()["detail"]

    # Checklist works
    v1_chk = client.get("/api/v1/checklist", headers=auth_headers)
    assert v1_chk.status_code == 200

    # Rate limiting: fire 60 calls -> 61st receives 429
    for _ in range(57):
        res = client.get("/api/v1/checklist", headers=auth_headers)
        assert res.status_code == 200

    # 61st call exceeds limit (we already did 2 calls earlier)
    rate_exceeded = client.get("/api/v1/checklist", headers=auth_headers)
    assert rate_exceeded.status_code == 429
    assert "Retry-After" in rate_exceeded.headers


def test_s7_priority_support_ticketing(client_and_db):
    client, db = client_and_db
    from app.subscriptions import SubscriptionService

    # 1. Free plan ticket -> Standard (48h)
    res_free = _signup(client, "free_support@corp.com")
    ws_free_id = res_free.json()["workspace"]["id"]

    t_free = client.post(
        "/api/support/tickets",
        json={"subject": "Inquiry about Mushak 9.1", "message": "How do we report monthly withholding?"},
    )
    assert t_free.status_code == 200
    assert t_free.json()["priority"] == "standard"
    assert "48 hours" in t_free.json()["sla"]

    # 2. Growth plan ticket -> Priority (12h)
    sub_svc = SubscriptionService(db)
    sub_svc.change_plan(ws_free_id, "growth")

    t_growth = client.post(
        "/api/support/tickets",
        json={"subject": "VAT deduction clarification", "message": "Need verification of SRO 4.2 applicability."},
    )
    assert t_growth.status_code == 200
    assert t_growth.json()["priority"] == "priority"
    assert "12 hours" in t_growth.json()["sla"]

    # 3. Professional plan ticket -> Urgent (4h)
    sub_svc.change_plan(ws_free_id, "professional")

    t_pro = client.post(
        "/api/support/tickets",
        json={"subject": "System audit integration issue", "message": "URGENT: API sync timeout on ERP webhook."},
    )
    assert t_pro.status_code == 200
    assert t_pro.json()["priority"] == "urgent"
    assert "4 hours" in t_pro.json()["sla"]

    # Verify user can view their tickets
    user_tickets = client.get("/api/support/tickets")
    assert user_tickets.status_code == 200
    assert len(user_tickets.json()) == 3




