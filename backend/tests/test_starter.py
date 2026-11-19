from __future__ import annotations

import pytest


def test_starter_rule_engine_filtering_and_reordering(client):
    # 1. solo + no data + cash -> no employee or customer data policy; cash present
    res1 = client.post(
        "/api/starter-guide",
        json={
            "stage": "exploring_idea",
            "sector": "retail",
            "jurisdiction": "bangladesh",
            "customers": "b2c",
            "delivery": "physical",
            "hiring": "solo",
            "collects_data": "no",
            "payments": "cash",
            "first_help": "which_policies",
        },
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    policy_ids1 = [p["id"] for p in data1["policies"]]
    assert "employee_workplace" not in policy_ids1
    assert "customer_data_privacy" not in policy_ids1
    assert "cash_handling_records" in policy_ids1
    assert "payment_financial_records" not in policy_ids1

    # 2. small_team + yes data + digital -> both employee and data policies present
    res2 = client.post(
        "/api/starter-guide",
        json={
            "stage": "recently_started",
            "sector": "software_it",
            "jurisdiction": "bangladesh",
            "customers": "b2b",
            "delivery": "online",
            "hiring": "small_team",
            "collects_data": "yes",
            "payments": "digital",
            "first_help": "general_guide",
        },
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    policy_ids2 = [p["id"] for p in data2["policies"]]
    assert "employee_workplace" in policy_ids2
    assert "customer_data_privacy" in policy_ids2
    assert "payment_financial_records" in policy_ids2
    assert "cash_handling_records" not in policy_ids2

    # 3. first_help reorders but NEVER drops categories
    res3_reordered = client.post(
        "/api/starter-guide",
        json={
            "stage": "recently_started",
            "sector": "software_it",
            "jurisdiction": "bangladesh",
            "customers": "b2b",
            "delivery": "online",
            "hiring": "small_team",
            "collects_data": "yes",
            "payments": "digital",
            "first_help": "customer_data_policies",
        },
    )
    assert res3_reordered.status_code == 200
    data3 = res3_reordered.json()
    policy_ids3 = [p["id"] for p in data3["policies"]]
    assert policy_ids3[0] == "customer_data_privacy"
    # Same categories present
    assert set(policy_ids2) == set(policy_ids3)


def test_starter_guide_rejects_invalid_enums(client):
    res = client.post(
        "/api/starter-guide",
        json={
            "stage": "not_a_valid_stage",
            "sector": "retail",
            "jurisdiction": "bangladesh",
            "customers": "b2c",
            "delivery": "physical",
            "hiring": "solo",
            "collects_data": "no",
            "payments": "cash",
            "first_help": "which_policies",
        },
    )
    assert res.status_code == 422


def test_starter_guide_non_bangladesh_jurisdiction(client):
    res = client.post(
        "/api/starter-guide",
        json={
            "stage": "planning_launch",
            "sector": "ecommerce",
            "jurisdiction": "international",
            "customers": "both",
            "delivery": "both",
            "hiring": "growing_team",
            "collects_data": "yes",
            "payments": "digital",
            "first_help": "which_policies",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["jurisdiction_notice"] is not None
    assert "international" in data["jurisdiction_notice"].lower() or "outside bangladesh" in data["jurisdiction_notice"].lower()

    # Starter SOP endpoint must reject non-Bangladesh jurisdictions with 400
    sop_res = client.post(
        "/api/starter-guide/sop",
        json={
            "company_name": "Global Trade Co",
            "stage": "planning_launch",
            "sector": "ecommerce",
            "jurisdiction": "international",
            "customers": "both",
            "delivery": "both",
            "hiring": "growing_team",
            "collects_data": "yes",
            "payments": "digital",
            "first_help": "which_policies",
        },
    )
    assert sop_res.status_code == 400
    assert "Bangladesh jurisdiction" in sop_res.json()["detail"]


def test_starter_guide_fallback_when_llm_missing(client_without_llm):
    # When LLM is not configured, starter-guide must still return 200 with deterministic fallback
    res = client_without_llm.post(
        "/api/starter-guide",
        json={
            "stage": "operating",
            "sector": "food_restaurant",
            "jurisdiction": "bangladesh",
            "customers": "b2c",
            "delivery": "physical",
            "hiring": "small_team",
            "collects_data": "unsure",
            "payments": "both",
            "first_help": "employee_policies",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "deterministic-fallback"
    assert len(data["policies"]) >= 4
    # All policies have valid covers and include points
    for p in data["policies"]:
        assert len(p["covers"]) > 10
        assert len(p["include_points"]) >= 3


def test_starter_sop_endpoint_indexes_and_integrates_with_analysis(client):
    sop_res = client.post(
        "/api/starter-guide/sop",
        json={
            "company_name": "Dhaka Cloud Kitchens",
            "stage": "operating",
            "sector": "food_restaurant",
            "jurisdiction": "bangladesh",
            "customers": "b2c",
            "delivery": "both",
            "hiring": "small_team",
            "collects_data": "yes",
            "payments": "both",
            "first_help": "which_policies",
        },
    )
    assert sop_res.status_code == 200, sop_res.text
    doc = sop_res.json()
    assert doc["document_id"]
    assert doc["company_profile_id"]
    assert doc["chunk_count"] >= 5
    assert any("Overview and Purpose" in s for s in doc["sections"])
    assert any("VAT" in s for s in doc["sections"])

    # Now verify this indexed starter SOP document runs through the normal 5-agent pipeline!
    plan_res = client.post(
        "/api/analyze",
        json={
            "company_profile_id": doc["company_profile_id"],
            "document_id": doc["document_id"],
        },
    )
    assert plan_res.status_code == 200, plan_res.text
    plan = plan_res.json()
    assert plan["id"]
    assert plan["company"] == "Dhaka Cloud Kitchens"
    assert len(plan["findings"]) > 0
