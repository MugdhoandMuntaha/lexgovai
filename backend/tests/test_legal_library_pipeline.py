"""Tests for Step 2: Extraction, structuring, classification, verification, and end-to-end ingestion pipeline."""

from __future__ import annotations

import pytest
from pathlib import Path
from app.db import Database
from app.legal_library.pipeline import LegalIngestionPipeline
from app.legal_library.verifier import VerifierAgent
from app.legal_library.structuring import StructuringAgent, heuristic_split_sections
from app.ocr import FakeOcr


SAMPLE_LAW_TEXT = """
THE INCOME TAX ACT, 2023
Act No. 12 of 2023

An Act to consolidate and amend the law relating to income-tax and super-tax.

CHAPTER 1
PRELIMINARY

Section 1. Short title, extent and commencement.
(1) This Act may be called the Income Tax Act, 2023.
(2) It extends to the whole of Bangladesh.
(3) It shall come into force on the first day of July, 2023.

Section 2. Definitions.
In this Act, unless there is anything repugnant in the subject or context:
(1) "assessee" means any person by whom any tax or other sum of money is payable under this Act.
(2) "assessment" includes reassessment and provisional assessment.

CHAPTER 2
ADMINISTRATION

Section 16. Income Tax Authorities.
(1) There shall be the following classes of income tax authorities for the purposes of this Act:
(a) The National Board of Revenue;
(b) Chief Commissioners of Taxes;
(c) Commissioners of Taxes.
"""


def test_heuristic_split_sections():
    sections = heuristic_split_sections(SAMPLE_LAW_TEXT)
    assert len(sections) >= 3
    labels = [s.number_label for s in sections]
    assert any("CHAPTER 1" in l.upper() or "SECTION 1" in l.upper() for l in labels)


def test_verifier_agent_matches_grounded_summary():
    verifier = VerifierAgent()
    grounded_summary = (
        "The Income Tax Act 2023 consolidates the law relating to income-tax. "
        "It establishes income tax authorities under the National Board of Revenue."
    )
    res = verifier.verify_summary(grounded_summary, SAMPLE_LAW_TEXT)
    assert res.is_verified is True
    assert res.average_score >= 70.0


def test_verifier_agent_flags_unsupported_hallucinations():
    verifier = VerifierAgent(min_sentence_score=65.0, min_average_score=72.0)
    hallucinated_summary = (
        "The Income Tax Act 2023 establishes authority under the National Board of Revenue. "
        "All cryptocurrency miners in Dhaka must register with the Bangladesh Space Research Organization within 3 days."
    )
    res = verifier.verify_summary(hallucinated_summary, SAMPLE_LAW_TEXT)
    assert res.is_verified is False
    assert "cryptocurrency" in (res.notes or "")


def test_end_to_end_ingestion_pipeline_published(tmp_path: Path):
    db_file = tmp_path / "pipeline_test.db"
    db = Database(db_file)
    pipeline = LegalIngestionPipeline(db=db, vectorstore=None, llm=None, ocr_engine=None)

    result = pipeline.ingest_document(
        filename="income_tax_act_2023.txt",
        content=SAMPLE_LAW_TEXT.encode("utf-8"),
        source_url="https://minlaw.gov.bd/income_tax_act_2023.txt",
    )

    assert result.is_new is True
    assert result.is_unchanged is False
    assert result.law_id.startswith("law_")
    assert result.version_id.startswith("ver_")

    law = db.get_law(result.law_id)
    assert law is not None
    assert "income_tax" in law["domain_tags"]
    assert law["publish_state"] == "published"
    assert law["summary_verified"] == 1

    # Verify sections in DB and FTS
    sections = db.list_law_sections(result.version_id)
    assert len(sections) >= 3

    hits = db.search_law_sections_fts("National Board of Revenue")
    assert len(hits) >= 1

    # Ingesting exact same content again should skip (is_unchanged=True)
    second_result = pipeline.ingest_document(
        filename="income_tax_act_2023.txt",
        content=SAMPLE_LAW_TEXT.encode("utf-8"),
        existing_law_id=result.law_id,
    )
    assert second_result.is_unchanged is True
    assert second_result.is_changed is False

    db.close()


def test_pipeline_changed_hash_creates_version_and_alerts_watchers(tmp_path: Path):
    db_file = tmp_path / "change_test.db"
    db = Database(db_file)
    pipeline = LegalIngestionPipeline(db=db, vectorstore=None, llm=None, ocr_engine=None)

    # First version
    v1_result = pipeline.ingest_document(
        filename="income_tax_act_2023.txt",
        content=SAMPLE_LAW_TEXT.encode("utf-8"),
    )

    # Add watcher
    ws = db.create_workspace("Test Watching Org")
    ws_id = ws["id"]
    user = db.create_user("watcher@example.com", "hash", "salt", "Watcher User")
    user_id = user["id"]
    db.create_membership(user_id, ws_id, role="owner")
    db.add_to_law_watchlist(ws_id, user_id, v1_result.law_id)

    # Amended version text
    amended_text = SAMPLE_LAW_TEXT + "\n\nCHAPTER 3\nSection 25. Mandatory E-Filing for Corporate Taxpayers."
    v2_result = pipeline.ingest_document(
        filename="income_tax_act_2023.txt",
        content=amended_text.encode("utf-8"),
        existing_law_id=v1_result.law_id,
    )

    assert v2_result.is_changed is True
    assert v2_result.version_id != v1_result.version_id

    # Verify notification created for watcher
    notifs = db.list_notifications(ws_id, user_id)
    assert len(notifs) >= 1
    assert "Watched Law Amended" in notifs[0]["title"] or "Statutory Amendment" in notifs[0]["title"]

    db.close()
