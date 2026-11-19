"""Unit and integration tests for Legal Library data models, migrations, and FTS5 search."""

from __future__ import annotations

import pytest
from pathlib import Path
from app.db import Database


def test_legal_library_crud_and_fts_search(tmp_path: Path):
    db_file = tmp_path / "legal_lib_test.db"
    db = Database(db_file)
    assert db.get_schema_version() == 7

    # 1. Create a law source
    source = db.create_law_source(
        name="NBR Customs & VAT",
        base_url="https://nbr.gov.bd",
        source_type="sro_and_circulars",
        enabled=True,
        crawl_config={"max_depth": 2, "max_pages": 10},
        rate_limit=1.0,
    )
    assert source["id"].startswith("src_")
    assert source["name"] == "NBR Customs & VAT"
    assert source["enabled"] == 1
    assert source["crawl_config"]["max_depth"] == 2

    # Update source
    updated_src = db.update_law_source(source["id"], enabled=False, last_status="completed")
    assert updated_src["enabled"] == 0
    assert updated_src["last_status"] == "completed"

    # 2. Create a law
    law = db.create_law(
        canonical_title_en="Value Added Tax and Supplementary Duty Act, 2012",
        canonical_title_bn="মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২",
        act_number="Act No. 47 of 2012",
        year=2012,
        law_type="act",
        issuing_body="National Board of Revenue",
        language_available="en,bn",
        status="in_force",
        domain_tags=["tax_vat", "indirect_tax"],
        publish_state="published",
    )
    assert law["id"].startswith("law_")
    assert law["year"] == 2012
    assert "tax_vat" in law["domain_tags"]

    # 3. Create a version
    version = db.create_law_version(
        law_id=law["id"],
        version_hash="sha256_mock_hash_12345",
        source_url="https://nbr.gov.bd/laws/vat_act_2012.pdf",
        extraction_method="text",
        is_current=True,
    )
    assert version["law_id"] == law["id"]
    assert version["is_current"] == 1

    # 4. Bulk insert sections (which updates both law_sections and law_sections_fts)
    sections_data = [
        {
            "level": "chapter",
            "number_label": "Chapter 1",
            "heading": "Preliminary",
            "text": "Short title, extent, commencement and application.",
            "order_index": 0,
        },
        {
            "level": "section",
            "number_label": "Section 1",
            "heading": "Short Title and Commencement",
            "text": "This Act may be called the Value Added Tax and Supplementary Duty Act, 2012. It shall come into force at once.",
            "order_index": 1,
        },
        {
            "level": "section",
            "number_label": "Section 15",
            "heading": "Imposition of Value Added Tax",
            "text": "Subject to the provisions of this Act, value added tax shall be imposed at the rate of fifteen percent on all taxable supplies.",
            "order_index": 2,
        },
    ]
    created_sections = db.create_law_sections_bulk(version["id"], law["id"], sections_data)
    assert len(created_sections) == 3

    # 5. Test FTS5 search
    # Exact keyword search
    hits = db.search_law_sections_fts("taxable supplies")
    assert len(hits) >= 1
    assert any("Section 15" in h["number_label"] for h in hits)

    # Search with law_id filter
    filtered_hits = db.search_law_sections_fts("preliminary", law_id=law["id"])
    assert len(filtered_hits) >= 1
    assert filtered_hits[0]["number_label"] == "Chapter 1"

    # Search for nonexistent term
    miss_hits = db.search_law_sections_fts("completelyunrelatedterm12345")
    assert len(miss_hits) == 0

    # 6. Test Watchlist
    ws_id = "test_workspace_legal"
    user_id = "test_user_legal"
    db.add_to_law_watchlist(ws_id, user_id, law["id"])
    assert db.is_law_watched(ws_id, user_id, law["id"]) is True

    watchlist = db.list_law_watchlist(ws_id, user_id)
    assert len(watchlist) == 1
    assert watchlist[0]["law_id"] == law["id"]

    db.remove_from_law_watchlist(ws_id, user_id, law["id"])
    assert db.is_law_watched(ws_id, user_id, law["id"]) is False

    # 7. Test Review Queue
    review_item = db.enqueue_law_review(law["id"], reason="Structuring length mismatch: verification flagged.")
    assert review_item["reason"].startswith("Structuring length mismatch")

    queue = db.list_law_review_queue(resolved=False)
    assert len(queue) >= 1
    assert queue[0]["law_id"] == law["id"]

    resolved = db.resolve_law_review(review_item["id"], resolved_by="admin_user", resolution="approved")
    assert resolved["resolution"] == "approved"
    assert resolved["resolved_by"] == "admin_user"

    # 8. Test Coverage Stats
    stats = db.get_laws_coverage_stats()
    assert stats["published_laws_count"] >= 1
    assert "act" in stats["by_law_type"]

    db.close()

