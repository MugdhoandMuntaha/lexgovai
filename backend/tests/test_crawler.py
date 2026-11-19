"""Tests for Part A: Dynamic Source Crawler, SSRF Interception, Link Discovery, and Plan Gating."""

from __future__ import annotations

import pytest
from app.adapters import SSRFValidationError, validate_url_ssrf
from app.crawler import (
    FakeCrawler,
    is_blocked_page,
    is_likely_regulatory_link,
)
from app.worker import Worker
from tests.conftest import FakeLLM, make_settings, mint_test_jwt
from fastapi.testclient import TestClient
from app.main import create_app


def test_regulatory_candidate_filtering_en_and_bn():
    """Confirms candidate link discovery detects gazette, SRO, circular keywords in EN/BN and PDFs."""
    # PDF link
    assert is_likely_regulatory_link("https://nbr.gov.bd/files/circular_2026.pdf")
    # English keywords
    assert is_likely_regulatory_link("https://nbr.gov.bd/notices/sro-144-vat-2026")
    assert is_likely_regulatory_link("https://nbr.gov.bd/pages/statutory-regulatory-order")
    assert is_likely_regulatory_link("https://nbr.gov.bd/pages/amendment-act-2026")
    assert is_likely_regulatory_link("https://nbr.gov.bd/pages/mushak-chalan")
    # Bengali keywords
    assert is_likely_regulatory_link("https://nbr.gov.bd/notices", anchor_text="জাতীয় রাজস্ব বোর্ড মূসক পরিপত্র")
    assert is_likely_regulatory_link("https://nbr.gov.bd/notices", anchor_text="গেজেট প্রজ্ঞাপন নং ১২")
    assert is_likely_regulatory_link("https://nbr.gov.bd/notices", anchor_text="নতুন আয়কর আইন ২০২৬")
    # Irrelevant general links
    assert not is_likely_regulatory_link("https://nbr.gov.bd/about-us", anchor_text="About the Chairman")
    assert not is_likely_regulatory_link("https://nbr.gov.bd/contact", anchor_text="Office Directory")


def test_blocked_and_challenge_detection():
    """Detects HTTP error statuses and Cloudflare/CAPTCHA challenge indicators."""
    assert is_blocked_page("Welcome", status_code=403)
    assert is_blocked_page("Too Many Requests", status_code=429)
    assert is_blocked_page("Attention Required! | Cloudflare Security Check")
    assert is_blocked_page("Please verify you are human to proceed")
    assert is_blocked_page("cf-turnstile challenge container")
    assert not is_blocked_page("Official Bangladesh Gazette Notice 2026", status_code=200)


def test_ssrf_guard_blocks_private_and_metadata_addresses():
    """Ensures SSRF guard blocks loopback, private RFC1918, and AWS/GCP 169.254.169.254 metadata."""
    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://127.0.0.1:8000/secret")
    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://localhost:3000/admin")
    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://10.0.0.5/internal")
    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://192.168.1.1/router")


def test_crawler_depth_and_page_caps():
    """Verifies that crawler stops crawling when depth or max_pages limit is reached."""
    mock_pages = {
        "https://portal.gov.bd/": {
            "text": "Home Portal",
            "links": ["https://portal.gov.bd/sro-1", "https://portal.gov.bd/sro-2"],
        },
        "https://portal.gov.bd/sro-1": {
            "text": "SRO 1 Details",
            "links": ["https://portal.gov.bd/sro-1-deep"],
        },
        "https://portal.gov.bd/sro-2": {
            "text": "SRO 2 Details",
            "links": ["https://portal.gov.bd/sro-2-deep"],
        },
        "https://portal.gov.bd/sro-1-deep": {
            "text": "SRO 1 Deep Details",
            "links": [],
        },
        "https://portal.gov.bd/sro-2-deep": {
            "text": "SRO 2 Deep Details",
            "links": [],
        },
    }

    # Test depth cap = 1
    crawler = FakeCrawler(mock_pages)
    results = crawler.crawl_source("https://portal.gov.bd/", max_depth=1, max_pages=10)
    visited_urls = [r["url"] for r in results]
    assert "https://portal.gov.bd/" in visited_urls
    assert "https://portal.gov.bd/sro-1" in visited_urls
    assert "https://portal.gov.bd/sro-2" in visited_urls
    assert "https://portal.gov.bd/sro-1-deep" not in visited_urls

    # Test max pages cap = 2
    crawler_capped = FakeCrawler(mock_pages)
    results_capped = crawler_capped.crawl_source("https://portal.gov.bd/", max_depth=5, max_pages=2)
    assert len(results_capped) == 2


def test_crawler_ssrf_block_on_redirect_or_discovered_link():
    """Crawler blocks any link or redirect attempting to access private or loopback networks."""
    mock_pages = {
        "https://portal.gov.bd/": {
            "text": "Home Portal",
            "links": ["http://127.0.0.1:8000/internal-admin", "http://169.254.169.254/meta-data"],
        },
    }
    crawler = FakeCrawler(mock_pages)
    results = crawler.crawl_source("https://portal.gov.bd/", max_depth=1, max_pages=5)
    
    # Internal URLs should either be blocked or recorded with error
    blocked = [r for r in results if r["status"] == "blocked"]
    assert len(blocked) >= 1
    assert any("SSRF blocked" in (b.get("error") or "") for b in blocked)


def test_worker_crawl_detects_hash_change_and_creates_version(tmp_path):
    """Worker crawling a source detects content change and creates a pending_review version with notification."""
    settings = make_settings(tmp_path)
    app = create_app(settings)
    db = app.state.services.db

    # Create workspace, user, and subscription with professional plan (portal_crawler: on)
    ws = db.create_workspace("Crawl Test Workspace")
    user = db.create_user("crawler_admin@example.com", "hash", "salt", "Crawler Admin")
    db.create_membership(user["id"], ws["id"], role="owner")
    app.state.services.subscriptions.change_plan(ws["id"], "professional")

    # Create regulation and source
    reg = db.create_regulation("NBR VAT SRO 2026", "Bangladesh", "VAT")
    src = db.create_regulation_source(
        regulation_id=reg["id"],
        name="NBR VAT Portal",
        kind="dynamic_crawler",
        url="https://portal.gov.bd/vat-sro",
        enabled=True,
    )

    mock_pages = {
        "https://portal.gov.bd/vat-sro": {
            "text": "Official Statutory Regulatory Order 2026: Section 4 amended to 15 days.",
            "links": [],
        }
    }
    crawler = FakeCrawler(mock_pages)
    worker = Worker(db=db, settings=settings, crawler=crawler)

    # First crawl sets the content hash and creates pending_review version
    worker.handle_crawl_sources({"source_id": src["id"], "workspace_id": ws["id"]})

    # Verify updated source check
    updated_src = db.get_regulation_source(src["id"])
    assert updated_src["last_hash"] is not None

    # Verify pending review version was created
    versions = db.list_regulation_versions(reg["id"])
    pending = [v for v in versions if v["status"] == "pending_review"]
    assert len(pending) == 1
    assert "Section 4 amended" in pending[0]["text"]

    # Verify in-app notification was sent to workspace
    notifs = db.list_notifications(ws["id"], "system")
    assert len(notifs) >= 1
    assert "New Regulatory Amendment Detected" in notifs[0]["title"]


def test_worker_crawl_gates_by_portal_crawler_plan_capability(tmp_path):
    """Worker skips portal crawling when workspace lacks 'portal_crawler' capability (e.g. Free plan)."""
    settings = make_settings(tmp_path)
    app = create_app(settings)
    db = app.state.services.db

    # Create workspace with free plan (portal_crawler: off)
    ws = db.create_workspace("Free Crawl Workspace")
    user = db.create_user("free_crawl@example.com", "hash", "salt", "Free Crawl User")
    db.create_membership(user["id"], ws["id"], role="owner")
    app.state.services.subscriptions.ensure_free_subscription(ws["id"])

    reg = db.create_regulation("Customs Law", "Bangladesh", "Customs")
    src = db.create_regulation_source(
        regulation_id=reg["id"],
        name="Customs Portal",
        kind="dynamic_crawler",
        url="https://customs.gov.bd/orders",
        enabled=True,
    )

    mock_pages = {
        "https://customs.gov.bd/orders": {
            "text": "Customs Amendment 2026",
            "links": [],
        }
    }
    crawler = FakeCrawler(mock_pages)
    worker = Worker(db=db, settings=settings, crawler=crawler)

    # Crawl with free workspace ID
    worker.handle_crawl_sources({"source_id": src["id"], "workspace_id": ws["id"]})

    # Crawler should NOT have been invoked
    assert len(crawler.crawl_calls) == 0

    # No pending_review versions created
    versions = db.list_regulation_versions(reg["id"])
    assert len(versions) == 0


def test_api_trigger_crawl_enforces_plan_capability(tmp_path):
    """Confirms POST /api/monitoring/sources/{id}/crawl returns 403 FEATURE_NOT_IN_PLAN on Free plan and 200 on Professional plan."""
    settings = make_settings(tmp_path)
    app = create_app(settings)
    db = app.state.services.db

    reg = db.create_regulation("Environmental Law", "Bangladesh", "Environment")
    src = db.create_regulation_source(
        regulation_id=reg["id"],
        name="DOE Portal",
        kind="dynamic_crawler",
        url="https://doe.gov.bd/circulars",
        enabled=True,
    )

    with TestClient(app) as c:
        # 1. Sign up with free plan
        token_free = mint_test_jwt(sub="free-user-crawl", email="free_crawl_user@example.com")
        res_free = c.post(
            f"/api/monitoring/sources/{src['id']}/crawl",
            headers={"Authorization": f"Bearer {token_free}"},
        )
        assert res_free.status_code == 403
        data_free = res_free.json()
        assert data_free["code"] == "FEATURE_NOT_IN_PLAN"
        assert data_free["capability"] == "portal_crawler"

        # 2. Upgrade workspace to Professional plan (has portal_crawler: on)
        user = db.get_user_by_email("free_crawl_user@example.com")
        ws = db.get_user_workspace(user["id"])
        app.state.services.subscriptions.change_plan(ws["id"], "professional")

        # Retry with the same user token
        res_pro = c.post(
            f"/api/monitoring/sources/{src['id']}/crawl",
            headers={"Authorization": f"Bearer {token_free}"},
        )
        assert res_pro.status_code == 200
        data_pro = res_pro.json()
        assert data_pro["ok"] is True
        assert "Portal crawl enqueued" in data_pro["message"]

