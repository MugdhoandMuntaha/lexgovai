from __future__ import annotations

import json
from pathlib import Path

from app.documents import chunk_text

from .conftest import FABRICATED_QUOTE

SAMPLE = (Path(__file__).resolve().parent.parent / "data" / "samples" / "apex_logistics_sop.txt").read_text("utf-8")


def _company(client) -> str:
    res = client.post(
        "/api/company-profile",
        json={"company_name": "Apex Logistics Bangladesh Ltd.", "industry": "Logistics", "country": "Bangladesh"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _parse_sse(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]


def test_chunker_splits_sop_into_sections():
    sections = [c.section for c in chunk_text(SAMPLE)]
    assert sections[0] == "Preamble"
    assert "Section 6.1: VAT Submission Timelines & Responsibilities" in sections
    assert "Section 7: Late Filing and Escalation" in sections


def test_health_and_regulation_text_work_without_llm(client_without_llm):
    health = client_without_llm.get("/api/health").json()
    assert health == {"status": "ok"}

    me = client_without_llm.get("/api/me").json()
    assert me["llm_configured"] is False

    reg = client_without_llm.get("/api/regulations/current").json()
    assert "fifteen (15)" in reg["after_text"]
    ops = {d["op"] for d in reg["diff"]}
    assert {"equal", "removed", "added"} <= ops
    assert len(reg["version_hash"]) == 16


def test_llm_endpoints_return_503_without_key(client_without_llm):
    assert client_without_llm.post("/api/regulations/detect-change").status_code == 503
    company_id = _company(client_without_llm)
    res = client_without_llm.post("/api/documents/sample", json={"company_profile_id": company_id})
    assert res.status_code == 503
    assert "GEMINI_API_KEY" in res.json()["detail"]


def test_watcher_is_cached_per_version(client, fake_llm):
    first = client.post("/api/regulations/detect-change").json()
    second = client.post("/api/regulations/detect-change").json()
    assert first == second
    assert first["change_type"] == "amendment"
    assert fake_llm.calls["WatcherLLMOutput"] == 1


def test_upload_rejects_unsupported_files_and_unknown_company(client):
    company_id = _company(client)
    bad_type = client.post(
        "/api/documents/upload",
        data={"company_profile_id": company_id},
        files={"file": ("sop.docx", b"hello", "application/octet-stream")},
    )
    assert bad_type.status_code == 422
    unknown = client.post(
        "/api/documents/upload",
        data={"company_profile_id": "nope"},
        files={"file": ("sop.txt", b"hello", "text/plain")},
    )
    assert unknown.status_code == 404


def test_full_pipeline_streams_real_progress_and_verifies_citations(client):
    company_id = _company(client)
    upload = client.post(
        "/api/documents/upload",
        data={"company_profile_id": company_id},
        files={"file": ("Apex_SOP.txt", SAMPLE.encode(), "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    doc = upload.json()
    assert doc["chunk_count"] >= 6

    res = client.post("/api/analyze/stream", json={"company_profile_id": company_id, "document_id": doc["document_id"]})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(res.text)

    progress = [(e["type"], e["agent"]) for e in events if e["type"].startswith("agent_")]
    assert progress == [(kind, n) for n in range(1, 6) for kind in ("agent_started", "agent_completed")]
    assert all("duration_ms" in e for e in events if e["type"] == "agent_completed")

    done = events[-1]
    assert done["type"] == "completed"
    plan = done["plan"]
    assert plan["impact_score"] == 100 and plan["urgency"] == "critical"
    assert plan["policy_draft"] == ["Section 6.1: Returns are filed within 15 calendar days by the VAT Filing Officer."]

    outdated, gap, fake = plan["findings"]
    assert outdated["issue_type"] == "outdated_reference" and outdated["severity"] == "high"
    assert not outdated["flagged_for_review"] and outdated["confidence"] >= 0.95
    assert outdated["citation"]["source"] == "Apex_SOP.txt"
    assert outdated["citation"]["section"] == "Section 6.1: VAT Submission Timelines & Responsibilities"
    assert outdated["citation"]["text_snippet"] in " ".join(SAMPLE.split())

    assert not gap["flagged_for_review"]
    assert gap["citation"]["source"].startswith("National Board of Revenue")
    assert gap["citation"]["section"] == "2. Mandatory Designated Officer"

    assert fake["flagged_for_review"] and fake["confidence"] < 0.75
    assert fake["severity"] == "medium"
    assert fake["citation"]["text_snippet"] == FABRICATED_QUOTE

    # Persisted plan + markdown report
    fetched = client.get(f"/api/action-plans/{plan['id']}").json()
    assert fetched == plan
    report = client.get(f"/api/action-plans/{plan['id']}/report")
    assert report.status_code == 200
    assert "attachment" in report.headers["content-disposition"]
    assert "NEEDS HUMAN REVIEW" in report.text and "- [ ] Add a day-10 reminder" in report.text


def test_sync_analyze_and_not_found(client):
    company_id = _company(client)
    doc = client.post("/api/documents/sample", json={"company_profile_id": company_id}).json()
    plan = client.post("/api/analyze", json={"company_profile_id": company_id, "document_id": doc["document_id"]})
    assert plan.status_code == 200 and len(plan.json()["findings"]) == 3

    other_company = _company(client)
    wrong = client.post("/api/analyze", json={"company_profile_id": other_company, "document_id": doc["document_id"]})
    assert wrong.status_code == 404
    assert client.get("/api/action-plans/missing").status_code == 404


def test_multi_regulation_catalog_and_details(client):
    # Catalog listing
    res = client.get("/api/regulations")
    assert res.status_code == 200
    catalog = res.json()
    reg_ids = [r["id"] for r in catalog]
    assert "nbr-vat-sro-4.2" in reg_ids
    assert "bangladesh-labor-act-2023" in reg_ids
    assert "income-tax-act-2023" in reg_ids

    # Detail endpoint for specific regulation
    labor = client.get("/api/regulations/bangladesh-labor-act-2023")
    assert labor.status_code == 200
    labor_data = labor.json()
    assert labor_data["regulation"]["title"] == "Bangladesh Labor Act (Amendment 2023)"
    assert len(labor_data["versions"]) >= 2
    assert "120 consecutive days" in labor_data["pair"]["after_text"]
    assert len(labor_data["pair"]["version_hash"]) == 16

    # Non-existent regulation returns 404
    assert client.get("/api/regulations/non-existent-statute").status_code == 404

    # Detect change for specific regulation
    change = client.post("/api/regulations/bangladesh-labor-act-2023/detect-change")
    assert change.status_code == 200
    change_data = change.json()
    assert change_data["change_type"] == "amendment"
    assert len(change_data["obligations"]) >= 1


