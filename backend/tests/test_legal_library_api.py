from __future__ import annotations

import io
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.db import Database


def _seed_test_laws(db: Database) -> dict[str, str]:
    """Helper to seed laws for API testing."""
    # Law 1: Published VAT Act
    law1 = db.create_law(
        canonical_title_en="Value Added Tax and Supplementary Duty Act, 2012",
        canonical_title_bn="মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২",
        act_number="Act No. 47",
        year=2012,
        law_type="act",
        issuing_body="National Board of Revenue",
        language_available="en,bn",
        status="in_force",
        status_confidence=0.98,
        domain_tags=["tax_vat", "corporate"],
        summary_ai="Consolidates the statutory law relating to VAT and supplementary duty in Bangladesh.",
        summary_verified=True,
        publish_state="published",
    )
    v1_1 = db.create_law_version(
        law_id=law1["id"],
        version_hash="hash_act_2012_v1",
        source_url="http://bdlaws.minlaw.gov.bd/act-1093.html",
        extraction_method="digital_text",
        is_current=False,
    )
    db.create_law_sections_bulk(
        law_version_id=v1_1["id"],
        law_id=law1["id"],
        sections_data=[
            {
                "level": "section",
                "number_label": "Section 15",
                "heading": "Imposition of Value Added Tax",
                "text": "Value Added Tax shall be imposed and payable on taxable supply at the rate of 15 percent.",
                "order_index": 1,
            }
        ],
    )
    v1_2 = db.create_law_version(
        law_id=law1["id"],
        version_hash="hash_act_2012_v2",
        source_url="http://bdlaws.minlaw.gov.bd/act-1093.html",
        extraction_method="digital_text",
        is_current=True,
    )
    db.create_law_sections_bulk(
        law_version_id=v1_2["id"],
        law_id=law1["id"],
        sections_data=[
            {
                "level": "section",
                "number_label": "Section 15",
                "heading": "Imposition of Value Added Tax",
                "text": "Value Added Tax shall be imposed and payable on taxable supply at standard and reduced rates.",
                "order_index": 1,
            },
            {
                "level": "section",
                "number_label": "Section 16",
                "heading": "Designated VAT Officer",
                "text": "Registered entities must formally designate a certified VAT compliance officer.",
                "order_index": 2,
            },
        ],
    )

    # Law 2: Published Banking Circular
    law2 = db.create_law(
        canonical_title_en="Bangladesh Bank Prudential Regulations for Foreign Exchange",
        year=2021,
        law_type="circular",
        issuing_body="Bangladesh Bank",
        language_available="en",
        status="in_force",
        status_confidence=0.95,
        domain_tags=["banking_finance", "foreign_exchange"],
        summary_ai="Guidelines on mandatory reserves and cross-border currency repatriations.",
        summary_verified=True,
        publish_state="published",
    )
    v2_1 = db.create_law_version(
        law_id=law2["id"],
        version_hash="hash_bb_circ_2021",
        source_url="https://www.bb.org.bd/mediaroom/circulars/circ.pdf",
        extraction_method="digital_text",
        is_current=True,
    )
    db.create_law_sections_bulk(
        law_version_id=v2_1["id"],
        law_id=law2["id"],
        sections_data=[
            {
                "level": "section",
                "number_label": "Circular 4",
                "heading": "Repatriation Limit",
                "text": "Exporters must repatriate export proceeds within 120 calendar days.",
                "order_index": 1,
            }
        ],
    )

    # Law 3: Pending Review Law (queued in review queue)
    law3 = db.create_law(
        canonical_title_en="Draft Labor Welfare Ordinance",
        year=2025,
        law_type="ordinance",
        issuing_body="Ministry of Labour and Employment",
        language_available="en",
        status="unknown",
        domain_tags=["labor"],
        summary_ai="Preliminary amendments to factory safety guidelines.",
        summary_verified=False,
        publish_state="pending_review",
    )
    v3_1 = db.create_law_version(
        law_id=law3["id"],
        version_hash="hash_draft_labor_2025",
        extraction_method="ocr_tesseract",
        ocr_quality=0.72,
        is_current=True,
    )
    db.enqueue_law_review(
        law_id=law3["id"],
        reason="OCR confidence below threshold (0.72 < 0.85); Critic verification pending.",
    )

    # Add relation: Law 1 refers to Law 2
    db.create_law_relation(
        from_law_id=law1["id"],
        to_law_id=law2["id"],
        relation="refers_to",
    )

    return {
        "vat_law_id": law1["id"],
        "bb_law_id": law2["id"],
        "pending_law_id": law3["id"],
        "vat_v1_id": v1_1["id"],
        "vat_v2_id": v1_2["id"],
    }


def test_list_laws_and_filters(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)

    # 1. Default list: should return only published laws (2 laws), not pending_review
    res = client.get("/api/laws")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 2
    returned_ids = [l["id"] for l in data["laws"]]
    assert seeded["vat_law_id"] in returned_ids
    assert seeded["bb_law_id"] in returned_ids
    assert seeded["pending_law_id"] not in returned_ids

    # 2. Filter by law_type=act
    res_act = client.get("/api/laws?law_type=act")
    assert res_act.status_code == 200
    acts = res_act.json()["laws"]
    assert len(acts) == 1
    assert acts[0]["id"] == seeded["vat_law_id"]

    # 3. Filter by domain_tag=banking_finance
    res_bank = client.get("/api/laws?domain_tag=banking_finance")
    assert res_bank.status_code == 200
    banks = res_bank.json()["laws"]
    assert len(banks) == 1
    assert banks[0]["id"] == seeded["bb_law_id"]

    # 4. Search text filter
    res_search = client.get("/api/laws?q=Prudential")
    assert res_search.status_code == 200
    assert len(res_search.json()["laws"]) == 1


def test_laws_coverage_stats(client):
    db: Database = client.app.state.services.db
    _seed_test_laws(db)

    res = client.get("/api/laws/coverage")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["published_laws_count"] == 2
    assert data["pending_review_count"] == 1
    assert data["total_sources_count"] >= 6  # Seed sources in db
    assert "act" in data["by_law_type"]
    assert "circular" in data["by_law_type"]
    assert "National Board of Revenue" in data["by_issuing_body"]


def test_laws_hybrid_search(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)

    # Search for section 15
    res = client.get("/api/laws/search?q=Section 15")
    assert res.status_code == 200, res.text
    data = res.json()
    hits = data["hits"]
    assert len(hits) >= 1
    top_hit = hits[0]
    assert top_hit["number_label"] == "Section 15"
    assert top_hit["law_id"] == seeded["vat_law_id"]
    assert top_hit["match_source"] in ("fts", "vector", "hybrid")


def test_laws_recommended(client):
    db: Database = client.app.state.services.db
    _seed_test_laws(db)

    res = client.get("/api/laws/recommended")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "recommended" in data
    assert len(data["recommended"]) > 0
    assert "law" in data["recommended"][0]
    assert "reason" in data["recommended"][0]


def test_laws_watchlist_flow(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)
    law_id = seeded["vat_law_id"]

    # Initially empty watchlist
    res0 = client.get("/api/laws/watchlist")
    assert res0.status_code == 200
    assert len(res0.json()["watchlist"]) == 0

    # Add to watchlist
    res_watch = client.post(f"/api/laws/{law_id}/watch")
    assert res_watch.status_code == 200
    assert res_watch.json()["is_watched"] is True

    # Check watchlist
    res1 = client.get("/api/laws/watchlist")
    assert res1.status_code == 200
    watched_ids = [l["law_id"] for l in res1.json()["watchlist"]]
    assert law_id in watched_ids

    # Unwatch
    res_unwatch = client.delete(f"/api/laws/{law_id}/watch")
    assert res_unwatch.status_code == 200
    assert res_unwatch.json()["is_watched"] is False

    # Check watchlist empty again
    res2 = client.get("/api/laws/watchlist")
    assert res2.status_code == 200
    assert len(res2.json()["watchlist"]) == 0


def test_law_details_sections_and_diff(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)
    law_id = seeded["vat_law_id"]

    # 1. Law detail
    res_detail = client.get(f"/api/laws/{law_id}")
    assert res_detail.status_code == 200, res_detail.text
    detail = res_detail.json()
    assert detail["law"]["id"] == law_id
    assert detail["law"]["canonical_title_en"] == "Value Added Tax and Supplementary Duty Act, 2012"
    assert detail["current_version"]["id"] == seeded["vat_v2_id"]
    assert len(detail["versions"]) == 2
    assert len(detail["relations"]) == 1
    assert detail["relations"][0]["relation"] == "refers_to"

    # 2. Law sections
    res_sec = client.get(f"/api/laws/{law_id}/sections")
    assert res_sec.status_code == 200
    sections = res_sec.json()["sections"]
    assert len(sections) == 2
    labels = [s["number_label"] for s in sections]
    assert "Section 15" in labels
    assert "Section 16" in labels

    # 3. Law version diff
    res_diff = client.get(
        f"/api/laws/{law_id}/diff?from_version_id={seeded['vat_v1_id']}&to_version_id={seeded['vat_v2_id']}"
    )
    assert res_diff.status_code == 200, res_diff.text
    diffs = res_diff.json()["diffs"]
    assert len(diffs) == 2
    # Section 15 was modified, Section 16 was added
    diff_map = {d["number_label"]: d for d in diffs}
    assert diff_map["Section 15"]["change_type"] == "modified"
    assert diff_map["Section 16"]["change_type"] == "added"


def test_law_ask_endpoint(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)
    law_id = seeded["vat_law_id"]

    res = client.post(
        "/api/laws/ask",
        json={"question": "What is Section 15 about?", "law_id": law_id},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "answer" in data
    assert len(data["answer"]) > 10
    assert "citations" in data
    assert len(data["citations"]) > 0
    assert data["citations"][0]["section_number"] == "Section 15"


def test_law_analyze_against_sop(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)
    law_id = seeded["vat_law_id"]

    # Create company profile & upload sample doc
    c_res = client.post(
        "/api/company-profile",
        json={"company_name": "Test Logistics Ltd.", "industry": "Logistics", "country": "Bangladesh"},
    )
    assert c_res.status_code == 200
    comp_id = c_res.json()["id"]

    d_res = client.post("/api/documents/sample", json={"company_profile_id": comp_id})
    assert d_res.status_code == 200
    doc_id = d_res.json()["document_id"]

    # Trigger analyze against the statutory law
    res = client.post(
        f"/api/laws/{law_id}/analyze",
        json={"company_profile_id": comp_id, "document_id": doc_id},
    )
    assert res.status_code == 200, res.text
    plan = res.json()
    assert "id" in plan
    assert "findings" in plan
    assert len(plan["findings"]) > 0


def test_admin_review_queue_and_actions(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)
    pending_id = seeded["pending_law_id"]

    # Non-admin user gets 403 on admin endpoints
    res_403 = client.get("/api/admin/laws/review-queue")
    assert res_403.status_code == 403

    # Grant platform admin to client's user
    me = client.get("/api/me").json()
    user_id = me["user"]["id"]
    db.set_platform_admin(user_id, True)

    # Now admin can read review queue
    res_q = client.get("/api/admin/laws/review-queue")
    assert res_q.status_code == 200
    queue = res_q.json()["queue"]
    assert len(queue) == 1
    assert queue[0]["law_id"] == pending_id

    # Admin approves law
    res_appr = client.post(f"/api/admin/laws/{pending_id}/approve")
    assert res_appr.status_code == 200
    assert res_appr.json()["law"]["publish_state"] == "published"

    # Queue should now be empty
    queue_after = client.get("/api/admin/laws/review-queue").json()["queue"]
    assert len(queue_after) == 0

    # Law is now visible in public list
    laws = client.get("/api/laws").json()["laws"]
    assert pending_id in [l["id"] for l in laws]


def test_admin_sources_toggle_and_upload(client):
    db: Database = client.app.state.services.db
    _seed_test_laws(db)

    # Grant platform admin
    me = client.get("/api/me").json()
    db.set_platform_admin(me["user"]["id"], True)

    # 1. List sources
    res_sources = client.get("/api/admin/laws/sources")
    assert res_sources.status_code == 200
    sources = res_sources.json()["sources"]
    assert len(sources) > 0
    first_src = sources[0]

    # 2. Toggle source enabled
    res_toggle = client.patch(
        f"/api/admin/laws/sources/{first_src['id']}",
        json={"enabled": True},
    )
    assert res_toggle.status_code == 200
    assert bool(res_toggle.json()["source"]["enabled"]) is True

    # 3. Manual document upload
    sample_law_text = (
        "THE INCOME TAX ACT, 2023\n\n"
        "Section 1. Short Title\nThis Act may be called the Income Tax Act, 2023.\n\n"
        "Section 10. Charge of Tax\nIncome tax shall be charged at the specified rates on total income."
    )
    file_bytes = io.BytesIO(sample_law_text.encode("utf-8"))

    upload_res = client.post(
        "/api/admin/laws/upload",
        data={
            "canonical_title_en": "Income Tax Act, 2023",
            "issuing_body": "National Board of Revenue",
            "law_type": "act",
            "year": "2023",
        },
        files={"file": ("income_tax_2023.txt", file_bytes, "text/plain")},
    )
    assert upload_res.status_code == 200, upload_res.text
    up_data = upload_res.json()
    assert up_data["ok"] is True
    assert "law_id" in up_data
    assert up_data["publish_state"] in ("published", "pending_review")


def test_plan_capability_gating(client):
    db: Database = client.app.state.services.db
    seeded = _seed_test_laws(db)
    law_id = seeded["vat_law_id"]

    me = client.get("/api/me").json()
    ws_id = me["workspace"]["id"]

    # Downgrade to 'free' plan: has 'basic' capability for legal_library
    # Basic allows listing and reading details, but forbids watch, diff, ask, analyze!
    client.app.state.services.subscriptions.change_plan(ws_id, "free")

    # 1. Reading details still works (basic capability)
    res_read = client.get(f"/api/laws/{law_id}")
    assert res_read.status_code == 200

    # 2. Watch requires 'standard' -> 403 Forbidden
    res_watch = client.post(f"/api/laws/{law_id}/watch")
    assert res_watch.status_code == 403
    assert "upgrade" in res_watch.json().get("detail", "").lower() or "plan" in res_watch.json().get("detail", "").lower()

    # 3. Diff requires 'standard' -> 403 Forbidden
    res_diff = client.get(
        f"/api/laws/{law_id}/diff?from_version_id={seeded['vat_v1_id']}&to_version_id={seeded['vat_v2_id']}"
    )
    assert res_diff.status_code == 403

    # 4. Ask requires 'full' -> 403 Forbidden
    res_ask = client.post("/api/laws/ask", json={"question": "What is section 15?", "law_id": law_id})
    assert res_ask.status_code == 403
