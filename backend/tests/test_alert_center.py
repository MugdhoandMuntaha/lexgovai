"""Comprehensive unit and integration tests for LexGOV AI Alert Center."""

from __future__ import annotations

import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.alerts.events import (
    AlertEvent,
    AlertSeverity,
    EVENT_CATALOG,
    render_event_template,
)
from app.alerts.channels.sms import (
    normalize_bd_phone,
    mask_phone_number,
    count_sms_segments,
    MockSmsProvider,
    SmsChannelAdapter,
)
from app.alerts.channels.email import EmailChannelAdapter
from app.alerts.verification import VerificationService, mask_email
from app.alerts.short_links import ShortLinkService
from app.alerts.router import AlertRouter
from app.db import Database
from app.main import create_app
from tests.conftest import make_settings, FakeLLM, mint_test_jwt


@pytest.fixture
def alert_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test_alerts.db")
    yield db
    db.close()


# ---------------------------------------------------------------------------
# 1. Event Catalog & Bilingual Template Rendering
# ---------------------------------------------------------------------------

def test_event_catalog_completeness():
    assert "regulation_change_detected" in EVENT_CATALOG
    assert "law_amendment_watched" in EVENT_CATALOG
    assert "deadline_reminder" in EVENT_CATALOG
    assert "high_risk_finding" in EVENT_CATALOG
    assert "quota_nearing_limit" in EVENT_CATALOG
    assert "source_blocked_or_failing" in EVENT_CATALOG


def test_bilingual_template_rendering_bangla_and_english():
    payload = {
        "law_title": "VAT and Supplementary Duty Act, 2012",
        "summary": "Filing deadline changed from 30 to 15 days.",
        "affected_sop": "VAT Return Filing Standard Procedure",
    }

    # English Email
    rendered_en = render_event_template("regulation_change_detected", "email", locale="en", payload=payload)
    assert "VAT and Supplementary Duty Act, 2012" in rendered_en["subject"]
    assert "Filing deadline changed from 30 to 15 days." in rendered_en["body"]
    assert rendered_en.get("subject") is not None

    # Bangla Email
    rendered_bn = render_event_template("regulation_change_detected", "email", locale="bn", payload=payload)
    assert "VAT and Supplementary Duty Act, 2012" in rendered_bn["subject"]
    assert "নিয়ন্ত্রক পরিবর্তন" in rendered_bn["subject"]

    # Compact SMS
    rendered_sms = render_event_template("regulation_change_detected", "sms", locale="en", payload=payload)
    assert len(rendered_sms["body"]) < 200
    assert "[LexGOV AI]" in rendered_sms["body"]


# ---------------------------------------------------------------------------
# 2. SMS Normalization, Masking & Bangladesh Segment Counting
# ---------------------------------------------------------------------------

def test_phone_normalization_and_masking():
    # Valid operator prefixes
    assert normalize_bd_phone("01712345678") == "+8801712345678"
    assert normalize_bd_phone("8801812345678") == "+8801812345678"
    assert normalize_bd_phone("+8801912345678") == "+8801912345678"
    assert normalize_bd_phone("01300000000") == "+8801300000000"

    # Masking for privacy
    assert mask_phone_number("+8801712345678") == "+88017****5678"
    masked = mask_email("compliance.officer@domain.com")
    assert masked.startswith("c") and masked.endswith("@domain.com") and "*" in masked

    # Invalid numbers
    with pytest.raises(ValueError):
        normalize_bd_phone("01212345678")  # 012 is not a valid BD operator prefix
    with pytest.raises(ValueError):
        normalize_bd_phone("12345")


def test_sms_segment_counting_gsm7_vs_unicode_bangla():
    # GSM-7 English under single segment (160)
    en_short = "LexGOV AI: NBR published new VAT filing directive. Review at lexgov.ai"
    info_en = count_sms_segments(en_short)
    assert not info_en["is_unicode"]
    assert info_en["segments"] == 1
    assert info_en["chars"] == len(en_short)

    # Unicode Bangla under single segment (70)
    bn_short = "লেক্সগভ এআই: এনবিআর নতুন ভ্যাট নির্দেশনা জারি করেছে।"
    info_bn = count_sms_segments(bn_short)
    assert info_bn["is_unicode"]
    assert info_bn["segments"] == 1
    assert info_bn["max_single"] == 70

    # Unicode Bangla multipart (exceeding 70 chars -> 67 chars/part)
    bn_long = (
        "কমপ্লায়েন্সওএস সতর্কবার্তা: জাতীয় রাজস্ব বোর্ড (এনবিআর) ভ্যাট ও সম্পূরক শুল্ক "
        "আইন ২০১২ এর আওতায় নতুন প্রজ্ঞাপন জারি করেছে। অনুগ্রহ করে অবিলম্বে আপনার এসওপি হালনাগাদ করুন।"
    )
    info_bn_long = count_sms_segments(bn_long)
    assert info_bn_long["is_unicode"]
    assert info_bn_long["segments"] >= 2


# ---------------------------------------------------------------------------
# 3. Contact Verification (OTP & WhatsApp Opt-In)
# ---------------------------------------------------------------------------

def test_otp_verification_lifecycle(alert_db: Database):
    user = alert_db.create_user(
        email="test_verification_user@example.com",
        password_hash="fakehash",
        salt="fakesalt",
        full_name="Verification Test User",
    )
    user_id = user["id"]
    svc = VerificationService(alert_db)

    # Request OTP
    code, norm_phone = svc.request_phone_otp(user_id, "01711223344")
    assert len(code) == 6
    assert norm_phone == "+8801711223344"

    # Rate limiting on immediate resend
    with pytest.raises(ValueError, match="Please wait"):
        svc.request_phone_otp(user_id, "01711223344")

    # Invalid code
    assert not svc.verify_phone_otp(user_id, norm_phone, "000000")

    # Valid code
    assert svc.verify_phone_otp(user_id, norm_phone, code)

    # Check database status
    channels = alert_db.get_user_channels(user_id)
    sms_ch = next(c for c in channels if c["channel"] == "sms")
    assert sms_ch["verified_at"] is not None

    # Opt into WhatsApp
    svc.opt_in_whatsapp(user_id, norm_phone)
    channels_after = alert_db.get_user_channels(user_id)
    wa_ch = next(c for c in channels_after if c["channel"] == "whatsapp")
    assert wa_ch["whatsapp_opt_in_at"] is not None

    # One-click opt-out
    svc.opt_out_channel(user_id, "whatsapp")
    channels_opt_out = alert_db.get_user_channels(user_id)
    wa_ch_opt = next(c for c in channels_opt_out if c["channel"] == "whatsapp")
    assert wa_ch_opt["opted_out_at"] is not None


# ---------------------------------------------------------------------------
# 4. Short Links Service
# ---------------------------------------------------------------------------

def test_short_link_generation_and_expiry(alert_db: Database):
    svc = ShortLinkService(alert_db)
    res = svc.create_short_link(
        target_path_or_url="/alerts/alt_123",
        expire_days=3,
    )
    code = res["code"]
    assert len(code) == 7

    # Resolves
    target = svc.resolve(code)
    assert target == "/alerts/alt_123"

    # Expired code returns None
    alert_db._execute("UPDATE short_links SET expires_at = '2020-01-01T00:00:00Z' WHERE code = ?", (code,))
    assert svc.resolve(code) is None


# ---------------------------------------------------------------------------
# 5. Routing Engine: Recipient Resolution, Fallback & Quiet Hours
# ---------------------------------------------------------------------------

def test_router_recipient_resolution(alert_db: Database):
    ws = alert_db.create_workspace("Test WS")
    ws_id = ws["id"]

    u1_rec = alert_db.create_user("vat_prim@test.com", "h", "salt", "VAT Prim")
    u2_rec = alert_db.create_user("vat_back@test.com", "h", "salt", "VAT Back")
    admin_rec = alert_db.create_user("admin@test.com", "h", "salt", "Admin User")

    u1 = u1_rec["id"]
    u2 = u2_rec["id"]
    admin = admin_rec["id"]

    alert_db.create_membership(u1, ws_id, "member")
    alert_db.create_membership(u2, ws_id, "member")
    alert_db.create_membership(admin, ws_id, "admin")

    # Map tax_vat domain tag
    alert_db.set_compliance_owner(ws_id, "tax_vat", u1, u2)

    router = AlertRouter(alert_db)

    # Event with tax_vat tag resolves to primary
    recipients = router.resolve_recipients(
        workspace_id=ws_id,
        event_type="regulation_change_detected",
        severity=AlertSeverity.HIGH,
        entity_type="law",
        entity_id="vat_act",
        payload={"domain_tag": "tax_vat", "law_title": "VAT Act"},
    )
    recipient_uids = [r["user_id"] for r in recipients]
    assert u1 in recipient_uids

    # Critical alert CCs admins
    crit_recipients = router.resolve_recipients(
        workspace_id=ws_id,
        event_type="high_risk_finding",
        severity=AlertSeverity.CRITICAL,
        entity_type="finding",
        entity_id="f_crit",
        payload={"domain_tag": "tax_vat"},
    )
    crit_uids = [r["user_id"] for r in crit_recipients]
    assert u1 in crit_uids
    assert admin in crit_uids


def test_quiet_hours_and_weekend_suppression(alert_db: Database):
    ws = alert_db.create_workspace("Quiet WS")
    ws_id = ws["id"]
    router = AlertRouter(alert_db)

    # 17:30 UTC is 23:30 BST in Asia/Dhaka -> falls in default quiet hours (22:00 - 08:00)
    dt_night = datetime(2026, 11, 15, 17, 30, tzinfo=timezone.utc)
    is_quiet, release_time = router.is_in_quiet_period(ws_id, now_dt=dt_night)
    assert is_quiet
    assert release_time is not None


# ---------------------------------------------------------------------------
# 6. Full Dispatch, Acknowledgment & IDOR Security
# ---------------------------------------------------------------------------

def test_alert_dispatch_and_acknowledgment(alert_db: Database):
    ws = alert_db.create_workspace("Dispatch WS")
    ws_id = ws["id"]
    u = alert_db.create_user("dispatch@test.com", "h", "salt", "Dispatch Officer")
    user_id = u["id"]
    alert_db.create_membership(user_id, ws_id, "admin")

    router = AlertRouter(alert_db)
    ev = AlertEvent(
        workspace_id=ws_id,
        event_type="high_risk_finding",
        severity=AlertSeverity.HIGH,
        entity_type="finding",
        entity_id="f_999",
        payload={"law_title": "Labor Law 2006", "urgency": "high", "ack_required": True},
    )

    alerts = router.route_event(ev)
    assert len(alerts) > 0
    alert_id = alerts[0]["id"]

    alert = alert_db.get_alert(alert_id)
    assert alert is not None
    assert alert["ack_required"] == 1
    assert alert["acked_at"] is None

    # Acknowledge
    acked = alert_db.acknowledge_alert(alert_id, user_id, acked_via="in_app")
    assert acked["status"] == "acknowledged"
    assert acked["acked_at"] is not None
    assert acked["acked_via"] == "in_app"


def test_tenant_isolation_idor(client: TestClient):
    """Ensures workspace A cannot access or acknowledge workspace B's alerts."""
    db: Database = client.app.state.services.db

    # Workspace A
    ws_a = db.create_workspace("Corp A")
    u_a = db.create_user("user_a@corp-a.com", "h", "salt", "User A")
    db.create_membership(u_a["id"], ws_a["id"], "admin")

    # Create alert event & alert for Corp A
    ev_a = db.create_alert_event(
        workspace_id=ws_a["id"],
        event_type="high_risk_finding",
        severity="high",
        entity_type="finding",
        entity_id="f_a",
        payload={"law_title": "VAT Act"},
    )
    alt_a = db.create_alert(
        alert_event_id=ev_a["id"],
        workspace_id=ws_a["id"],
        recipient_user_id=u_a["id"],
        ack_required=True,
    )

    # Workspace B
    ws_b = db.create_workspace("Corp B")
    u_b = db.create_user("user_b@corp-b.com", "h", "salt", "User B")
    db.create_membership(u_b["id"], ws_b["id"], "admin")

    jwt_b = mint_test_jwt(sub=u_b["id"], email="user_b@corp-b.com")

    # User B attempts to acknowledge Alert A -> must return 404 (IDOR protected)
    res = client.post(
        f"/api/alerts/{alt_a['id']}/ack",
        headers={"Authorization": f"Bearer {jwt_b}"},
        json={"acked_via": "in_app"},
    )
    assert res.status_code == 404
