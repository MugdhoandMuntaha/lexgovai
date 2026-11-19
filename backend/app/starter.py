"""Starter guide rule engine, Gemini content generator, and starter SOP builder.

Designed for beginners without an existing SOP document.
Deterministic rule engine runs first, selecting policy categories and tiers.
Gemini (or a deterministic fallback) then drafts descriptions and include points.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import Settings
from .db import LEGACY_WORKSPACE_ID, new_id
from .documents import chunk_text
from .llm import LLMClient
from .pipeline import DISCLAIMER
from .schemas import (
    DocumentUploadResponse,
    FirstHelpChoice,
    PolicyTier,
    StarterAnswers,
    StarterGuideLLMOutput,
    StarterGuideResponse,
    StarterPolicyItem,
    StarterSOPRequest,
    StarterSOPResponse,
)
from .services import Services

logger = logging.getLogger(__name__)

# Sector to industry mapping for company profiles
SECTOR_MAP: dict[str, str] = {
    "retail": "Retail & Physical Trade",
    "ecommerce": "E-Commerce & Digital Retail",
    "software_it": "Software & Information Technology",
    "food_restaurant": "Food, Beverage & Hospitality",
    "manufacturing": "Manufacturing & Production",
    "professional_services": "Professional Services & Consulting",
    "financial_fintech": "Financial Services & FinTech",
    "other": "General Commercial Enterprise",
}

JURISDICTION_MAP: dict[str, str] = {
    "bangladesh": "Bangladesh",
    "international": "International",
    "other_country": "Other Country",
}

# ---------------------------------------------------------------------------
# Fallback static content per category
# ---------------------------------------------------------------------------

STATIC_COVERS: dict[str, str] = {
    "business_registration_compliance": (
        "Establishes baseline legal identity, required trade licenses, and fundamental statutory registrations."
    ),
    "tax_vat_recordkeeping": (
        "Governs transaction documentation, invoice retention, and basic tax accounting procedures."
    ),
    "employee_workplace": (
        "Defines staff employment agreements, compensation timelines, workplace safety, and conduct standards."
    ),
    "customer_data_privacy": (
        "Protects customer personal information, contact records, and communication preferences."
    ),
    "payment_financial_records": (
        "Regulates acceptance of digital payments, gateway reconciliation, and banking procedures."
    ),
    "cash_handling_records": (
        "Standardizes physical cash storage, daily register balancing, and bank deposit routines."
    ),
    "digital_security_access": (
        "Secures digital platforms, customer account access, passwords, and online business assets."
    ),
    "refunds_customer_complaints": (
        "Outlines return policies, refund criteria, customer warranty claims, and grievance resolution."
    ),
    "contracts_invoicing": (
        "Governs formal commercial agreements, statements of work, credit terms, and client invoicing."
    ),
}

STATIC_POINTS: dict[str, list[str]] = {
    "business_registration_compliance": [
        "Obtain valid trade license and company incorporation credentials from the appropriate authority",
        "Display statutory registrations and tax certificates at primary operational premises",
        "Maintain an official register of business owners, directors, and authorized statutory contacts",
        "Schedule annual calendar reviews for license, registration, and permit renewals",
    ],
    "tax_vat_recordkeeping": [
        "Issue sequentially numbered commercial invoices or bills for every customer sale",
        "Retain all vendor purchase receipts, import bills, and proofs of payment in order",
        "Maintain monthly bookkeeping ledgers reconciling gross income against operating expenditures",
        "Archive commercial transaction and tax documentation for statutory inspection periods",
    ],
    "employee_workplace": [
        "Issue written employment appointment letters explicitly stating duties, salary, and notice periods",
        "Designate fixed monthly salary payment timelines and maintain signed payment records",
        "Establish baseline workplace safety standards, maximum weekly working hours, and leave policies",
        "Provide a fair internal grievance and dispute resolution process for all personnel",
    ],
    "customer_data_privacy": [
        "Collect only the customer information strictly necessary for order fulfillment and communication",
        "Secure stored customer records, databases, and contact lists against unauthorized access",
        "Prohibit unauthorized sharing, distribution, or external sale of customer personal data",
        "Promptly honor customer requests to view, correct, or delete their personal contact records",
    ],
    "payment_financial_records": [
        "Perform daily reconciliation of digital sales, mobile wallets, and payment gateway settlements",
        "Safeguard business bank accounts with multi-factor authentication and dual authorization",
        "Formally designate authorized personnel permitted to execute transfers and vendor payouts",
        "Review monthly bank and merchant account statements against internal accounting ledgers",
    ],
    "cash_handling_records": [
        "Store cash in a locked cash drawer or safe with single-person designated custody",
        "Issue manual or printed register receipts for every cash payment received from customers",
        "Conduct end-of-day cash balancing against register receipts before closing operations",
        "Establish regular bank deposit routines to minimize cash retained overnight on premises",
    ],
    "digital_security_access": [
        "Enforce strong, unique passwords and multi-factor authentication across all business tools",
        "Restrict administrative access to production systems, servers, and customer databases",
        "Apply security updates to business website software, e-commerce plugins, and operating systems",
        "Maintain periodic encrypted backups of company data stored in a separate secure location",
    ],
    "refunds_customer_complaints": [
        "Publish clear, accessible terms governing returns, product exchanges, and eligibility timelines",
        "Establish defined turnaround times for acknowledging and investigating customer complaints",
        "Maintain a written log of customer issues, refund authorizations, and corrective actions taken",
        "Process approved refunds promptly through the customer's original payment method",
    ],
    "contracts_invoicing": [
        "Execute formal written contracts, statements of work, or purchase orders before starting work",
        "Define explicit payment terms, milestone schedules, and late payment escalation procedures",
        "Establish clear delivery verification and client written acceptance criteria",
        "Systematically track outstanding receivables and issue timely reminders for overdue invoices",
    ],
}

CATEGORY_METADATA: dict[str, dict[str, str]] = {
    "business_registration_compliance": {
        "title": "Business Registration & Basic Legal Obligations",
    },
    "tax_vat_recordkeeping": {
        "title": "Tax, VAT & Transaction Recordkeeping",
    },
    "employee_workplace": {
        "title": "Employee & Workplace Policies",
    },
    "customer_data_privacy": {
        "title": "Customer Data & Privacy Policy",
    },
    "payment_financial_records": {
        "title": "Payment Handling & Financial Recordkeeping",
    },
    "cash_handling_records": {
        "title": "Cash Handling & Recordkeeping",
    },
    "digital_security_access": {
        "title": "Digital Security & Access Control",
    },
    "refunds_customer_complaints": {
        "title": "Refunds, Returns & Customer Complaints Policy",
    },
    "contracts_invoicing": {
        "title": "Commercial Contracts & Invoicing Procedures",
    },
}

# ---------------------------------------------------------------------------
# (a) Rule Engine
# ---------------------------------------------------------------------------


def build_rule_categories(answers: StarterAnswers) -> list[dict[str, Any]]:
    """Evaluates rules deterministically to select categories, tiers, and reasons."""
    items: list[dict[str, Any]] = []

    # Foundational registrations
    is_early_stage = answers.stage in ("exploring_idea", "planning_launch")
    items.append({
        "id": "business_registration_compliance",
        "title": CATEGORY_METADATA["business_registration_compliance"]["title"],
        "tier": "start_now" if is_early_stage else "soon",
        "reason": (
            "Foundational legal requirement to establish legal status, business licensing, and operating authority."
        ),
    })

    # Tax & VAT recordkeeping
    is_active_stage = answers.stage in ("recently_started", "operating")
    items.append({
        "id": "tax_vat_recordkeeping",
        "title": CATEGORY_METADATA["tax_vat_recordkeeping"]["title"],
        "tier": "start_now" if is_active_stage else "soon",
        "reason": (
            "Because your business handles commercial transactions subject to statutory tax and VAT accounting rules."
        ),
    })

    # Rule: hiring != solo -> employee & workplace policies
    if answers.hiring != "solo":
        items.append({
            "id": "employee_workplace",
            "title": CATEGORY_METADATA["employee_workplace"]["title"],
            "tier": "start_now" if answers.hiring in ("small_team", "growing_team") else "soon",
            "reason": (
                "Because you plan to hire employees or manage an operational team with labor obligations."
            ),
        })

    # Rule: collects_data in (yes, unsure) -> customer data & privacy policy
    if answers.collects_data in ("yes", "unsure"):
        items.append({
            "id": "customer_data_privacy",
            "title": CATEGORY_METADATA["customer_data_privacy"]["title"],
            "tier": "start_now" if answers.collects_data == "yes" else "soon",
            "reason": "Because you collect or may store customer personal information and contact details.",
        })

    # Rule: payments in (digital, both) -> payment handling & financial recordkeeping
    if answers.payments in ("digital", "both"):
        items.append({
            "id": "payment_financial_records",
            "title": CATEGORY_METADATA["payment_financial_records"]["title"],
            "tier": "start_now",
            "reason": "Because you accept digital or online customer transactions requiring reconciliation.",
        })

    # Rule: payments == cash -> cash handling & record keeping
    if answers.payments == "cash":
        items.append({
            "id": "cash_handling_records",
            "title": CATEGORY_METADATA["cash_handling_records"]["title"],
            "tier": "start_now",
            "reason": "Because your business relies on physical cash transactions requiring daily custody and balancing.",
        })

    # Rule: delivery in (online, both) -> digital security & access control
    if answers.delivery in ("online", "both"):
        items.append({
            "id": "digital_security_access",
            "title": CATEGORY_METADATA["digital_security_access"]["title"],
            "tier": "soon",
            "reason": "Because you deliver products or services online, requiring digital asset and credential security.",
        })

    # Rule: customers in (b2c, both) -> refunds/returns & customer complaints
    if answers.customers in ("b2c", "both"):
        items.append({
            "id": "refunds_customer_complaints",
            "title": CATEGORY_METADATA["refunds_customer_complaints"]["title"],
            "tier": "soon" if answers.stage == "operating" else "later",
            "reason": "Because you sell directly to individual consumers (B2C) who require clear return and redress policies.",
        })

    # Rule: customers in (b2b, both) -> contracts & invoicing
    if answers.customers in ("b2b", "both"):
        items.append({
            "id": "contracts_invoicing",
            "title": CATEGORY_METADATA["contracts_invoicing"]["title"],
            "tier": "start_now" if answers.stage in ("recently_started", "operating") else "soon",
            "reason": "Because you transact with corporate clients (B2B) governed by formal commercial agreements and billing terms.",
        })

    # Reorder according to first_help WITHOUT dropping any categories
    items = reorder_by_first_help(items, answers.first_help)
    return items


def reorder_by_first_help(items: list[dict[str, Any]], first_help: FirstHelpChoice) -> list[dict[str, Any]]:
    """Prioritizes the category corresponding to first_help at the top without dropping any items."""
    target_id: str | None = None
    if first_help == "registration_basics":
        target_id = "business_registration_compliance"
    elif first_help == "employee_policies":
        target_id = "employee_workplace"
    elif first_help == "customer_data_policies":
        target_id = "customer_data_privacy"

    if not target_id:
        return items

    matched = [it for it in items if it["id"] == target_id]
    others = [it for it in items if it["id"] != target_id]

    if matched:
        # Boost matched item to start_now
        matched[0] = {**matched[0], "tier": "start_now"}
        return matched + others

    return items


# ---------------------------------------------------------------------------
# (b) Content Generation (Gemini with deterministic fallback)
# ---------------------------------------------------------------------------

STARTER_PROMPT_SYSTEM = (
    "You are an expert SME compliance and operations advisor. "
    "Provide clear, practical, good-practice policy outlines for emerging businesses. "
    "STRICT CONSTRAINTS:\n"
    "1. Do NOT invent legal specifics: no invented statute names, statutory section numbers, fine amounts, "
    "legal deadlines, or government fee figures.\n"
    "2. For international or other_country jurisdictions, give ONLY generic international good-practice advice.\n"
    "3. Write tailored, practical, actionable bullet points.\n"
    "4. Return content for EXACTLY the provided category IDs without adding, omitting, or renaming any."
)


def generate_static_guide(answers: StarterAnswers, rule_categories: list[dict[str, Any]]) -> StarterGuideResponse:
    """Deterministic fallback returning high-quality static guidance."""
    unsure_count = sum(
        1
        for val in (answers.stage, answers.customers, answers.delivery, answers.hiring, answers.collects_data, answers.payments)
        if val in ("undecided", "unsure", "exploring_idea")
    )

    summary_prefix = ""
    if unsure_count >= 3:
        summary_prefix = (
            "Because several aspects of your operational setup are still being decided, "
            "this roadmap focuses on flexible, foundational good practices that adapt as your business takes shape. "
        )

    sector_label = SECTOR_MAP.get(answers.sector, answers.sector)
    stage_label = answers.stage.replace("_", " ")

    if answers.jurisdiction == "bangladesh":
        summary = (
            f"{summary_prefix}Starter policy roadmap for your {sector_label.lower()} business ({stage_label}) operating in Bangladesh. "
            "Prioritize initial trade licensing and financial transaction records before scaling. Note: Specific tax and VAT filing "
            "obligations should be confirmed with the National Board of Revenue (NBR) or an accredited VAT practitioner."
        )
        notice = None
    else:
        summary = (
            f"{summary_prefix}General good-practice compliance guide for your {sector_label.lower()} business ({stage_label}). "
            "Focus on establishing clean financial ledgers, secure customer handling, and clear operational standards."
        )
        notice = (
            "Notice: Because your business operates internationally or outside Bangladesh, this guide reflects "
            "general good-practice compliance principles. Specific local statutory registrations, filing deadlines, "
            "labor rules, and tax laws were not assessed and must be verified directly with local authorities in your jurisdiction."
        )

    policies: list[StarterPolicyItem] = []
    for cat in rule_categories:
        cid = cat["id"]
        policies.append(
            StarterPolicyItem(
                id=cid,
                title=cat["title"],
                tier=cat["tier"],
                reason=cat["reason"],
                covers=STATIC_COVERS.get(cid, "Governs standard operational compliance."),
                include_points=STATIC_POINTS.get(
                    cid, ["Establish formal written operational standard", "Maintain accurate records for all activities"]
                ),
            )
        )

    return StarterGuideResponse(
        summary=summary,
        jurisdiction_notice=notice,
        policies=policies,
        disclaimer=DISCLAIMER,
        model="deterministic-fallback",
    )


def generate_starter_guide(
    svc: Services, answers: StarterAnswers, workspace_id: str = LEGACY_WORKSPACE_ID
) -> StarterGuideResponse:
    """Builds prioritized starter policy guide using rule engine first, then Gemini (or fallback)."""
    rule_categories = build_rule_categories(answers)
    guidance_level = svc.entitlements.level(workspace_id, "industry_guidance")

    # Check if LLM is available
    if svc.llm is None:
        guide = generate_static_guide(answers, rule_categories)
    else:
        try:
            categories_for_prompt = "\n".join(
                f"- Category ID: {c['id']} | Title: {c['title']} | Tier: {c['tier']} | Reason: {c['reason']}"
                for c in rule_categories
            )

            depth_instruction = {
                "general": "Provide broad, accessible starter guidance suitable for any general startup.",
                "basic": "Provide standard operational guidelines tailored to this business type.",
                "detailed": "Provide detailed, operational domain practices specific to this sector and workflow.",
                "advanced": "Provide comprehensive, advanced, and nuanced operational standards for this industry.",
            }.get(guidance_level, "Provide standard operational guidelines.")

            prompt = (
                f"Business Profile:\n"
                f"- Stage: {answers.stage}\n"
                f"- Sector: {SECTOR_MAP.get(answers.sector, answers.sector)}\n"
                f"- Jurisdiction: {JURISDICTION_MAP.get(answers.jurisdiction, answers.jurisdiction)}\n"
                f"- Customers: {answers.customers}\n"
                f"- Delivery: {answers.delivery}\n"
                f"- Hiring: {answers.hiring}\n"
                f"- Collects Customer Data: {answers.collects_data}\n"
                f"- Payments: {answers.payments}\n"
                f"- First Priority: {answers.first_help}\n\n"
                f"Guidance Depth Requirement: {depth_instruction}\n\n"
                f"Rule Engine Selected Categories (do NOT change this list or IDs):\n"
                f"{categories_for_prompt}\n\n"
                "Write:\n"
                "1. An executive summary (2-4 sentences) tailored to their sector and stage. "
                "If jurisdiction is bangladesh, note that statutory tax and registration requirements should be confirmed with the NBR or a qualified advisor. "
                "If international/other_country, keep it generic.\n"
                "2. For each category listed above, write a concise 'covers' statement (1-2 sentences) "
                "and 3 to 6 practical, non-invented 'include_points'. Ensure category_id matches exactly."
            )

            output: StarterGuideLLMOutput = svc.llm.generate_json(prompt, StarterGuideLLMOutput, STARTER_PROMPT_SYSTEM)

            # Map generated content back to rule engine categories
            content_by_id = {c.category_id: c for c in output.policies}

            policies: list[StarterPolicyItem] = []
            for cat in rule_categories:
                cid = cat["id"]
                llm_content = content_by_id.get(cid)
                if llm_content and llm_content.covers and len(llm_content.include_points) >= 2:
                    covers = llm_content.covers.strip()
                    points = [p.strip() for p in llm_content.include_points if p.strip()]
                else:
                    covers = STATIC_COVERS.get(cid, "Governs standard operational compliance.")
                    points = STATIC_POINTS.get(cid, ["Establish formal written standards", "Maintain accurate records"])

                policies.append(
                    StarterPolicyItem(
                        id=cid,
                        title=cat["title"],
                        tier=cat["tier"],
                        reason=cat["reason"],
                        covers=covers,
                        include_points=points,
                    )
                )

            notice = None
            if answers.jurisdiction != "bangladesh":
                notice = (
                    "Notice: Because your business operates internationally or outside Bangladesh, this guide reflects "
                    "general good-practice compliance principles. Specific local statutory registrations, filing deadlines, "
                    "labor rules, and tax laws were not assessed and must be verified directly with local authorities in your jurisdiction."
                )

            guide = StarterGuideResponse(
                summary=output.summary.strip(),
                jurisdiction_notice=notice,
                policies=policies,
                disclaimer=DISCLAIMER,
                model=svc.llm.model_name,
            )
        except Exception as exc:
            logger.warning("Starter guide LLM generation failed, using deterministic fallback: %s", exc)
            guide = generate_static_guide(answers, rule_categories)

    # Section 6: If workspace has personalized_checklist capability, save checklist items
    if svc.entitlements.has_at_least(workspace_id, "personalized_checklist", "on"):
        checklist_data = [
            {"title": p.title, "tier": p.tier, "reason": p.reason} for p in guide.policies
        ]
        # Store for default profile
        svc.db.save_checklist_items(workspace_id, "default_profile", checklist_data)

    return guide


# ---------------------------------------------------------------------------
# (c) Starter SOP Document Generator
# ---------------------------------------------------------------------------


def build_starter_sop_text(answers: StarterAnswers, company_name: str) -> str:
    """Generates an initial draft SOP text with section headings recognized by the chunker."""
    clean_name = company_name.strip() or "My Business"
    sector_name = SECTOR_MAP.get(answers.sector, "Commercial Enterprise")

    lines = [
        f"Standard Operating Procedure: Business Operations & Compliance (SOP-START-2025-v1)",
        f"Company: {clean_name}",
        f"Industry Sector: {sector_name}",
        f"Jurisdiction: Bangladesh",
        f"Watermark: Starter Template - Not Legal Advice",
        "",
        "Section 1: Overview and Purpose",
        f"This Standard Operating Procedure establishes baseline operational policies for {clean_name}. "
        "It governs internal administrative responsibilities, transaction records, customer data handling, and statutory filings. "
        "NOTICE: This document is a starter operational template and must be formally reviewed by qualified legal counsel.",
        "",
        "Section 2: Organizational Governance and Staffing",
    ]

    if answers.hiring == "solo":
        lines.append(
            f"The business founder and principal officer directly oversees all commercial operations, sales, and accounting records. "
            "No secondary staff are currently engaged. Any future employee appointments shall be documented via formal appointment letters."
        )
    else:
        lines.append(
            f"Operational duties at {clean_name} are divided among executive management and operational team members. "
            "All personnel are provided written employment appointment letters defining compensation, working hours, and duties. "
            "Monthly salary disbursements are reconciled and recorded on the designated monthly payment date."
        )

    lines.extend([
        "",
        "Section 3: Financial Records and Invoicing",
    ])

    if answers.payments in ("digital", "both"):
        lines.append(
            "All customer sales processed via digital payment channels or bank transfers are recorded sequentially in the accounting ledger. "
            "The accounts team performs regular reconciliation of digital merchant accounts against commercial bank statements."
        )
    if answers.payments in ("cash", "both"):
        lines.append(
            "Physical cash receipts are collected in a secured cash register and reconciled against daily sales invoices. "
            "Cash balances are deposited into the company bank account on a scheduled weekly basis to minimize on-premises custody."
        )

    lines.extend([
        "",
        "Section 4: Value Added Tax (VAT) and Statutory Compliance",
        "The finance and accounts department submits monthly VAT returns to the NBR within 30 calendar days following the tax month end. "
        "Any available finance team member is authorized to process filings via the NBR online portal. "
        "All official VAT challans, purchase ledgers, and sales registers are archived in company records for routine inspection.",
        "",
        "Section 5: Customer Relations and Data Protection",
    ])

    if answers.collects_data in ("yes", "unsure"):
        lines.append(
            f"{clean_name} maintains confidential customer records strictly for order fulfillment, billing, and customer communication. "
            "Customer personal records and contact details are stored securely and shall not be disclosed to unauthorized third parties. "
            "Customer inquiries and complaints are logged and resolved within standard operational turnaround times."
        )
    else:
        lines.append(
            f"{clean_name} processes customer transactions on a transactional basis without retaining persistent personal records. "
            "Basic sales records are preserved solely for bookkeeping and invoice verification."
        )

    lines.extend([
        "",
        "Section 6: Operational Security and Record Retention",
        "All commercial agreements, customer invoices, payment vouchers, and statutory tax filings are preserved "
        "for a minimum retention period of five years. Internal passwords and system credentials are reviewed and updated periodically.",
    ])

    return "\n".join(lines)


def create_starter_sop(
    svc: Services, req: StarterSOPRequest, workspace_id: str = LEGACY_WORKSPACE_ID
) -> DocumentUploadResponse:
    """Generates starter SOP text and reuses the existing ingestion pipeline."""
    if req.jurisdiction != "bangladesh":
        raise ValueError(
            "Starter SOP generation and benchmarking currently requires Bangladesh jurisdiction (to benchmark against the NBR VAT standard)."
        )

    clean_name = req.company_name.strip() or "My Business"
    industry = SECTOR_MAP.get(req.sector, "Commercial Enterprise")
    country = JURISDICTION_MAP.get(req.jurisdiction, "Bangladesh")

    # 1. Create company profile
    company = svc.db.create_company(
        company_name=clean_name,
        industry=industry,
        country=country,
        description=f"Starter company profile created via LexGOV AI Start Fresh wizard for {answers_stage_label(req.stage)}.",
        workspace_id=workspace_id,
    )

    # 2. Build starter SOP text
    text = build_starter_sop_text(req, clean_name)
    filename = f"{clean_name.replace(' ', '_')}_Starter_SOP.txt"

    # 3. Ingest using existing chunker, embeddings, and vector store
    llm_client = svc.require_llm()
    chunks = chunk_text(text)
    embeddings = llm_client.embed([f"{c.section}\n{c.text}" for c in chunks], "RETRIEVAL_DOCUMENT")
    doc_id = new_id()

    svc.store.add_document(doc_id, chunks, embeddings)
    svc.db.create_document(company["id"], filename, text, len(chunks), doc_id, workspace_id=workspace_id)

    # 4. If personalized_checklist is enabled, persist checklist items
    if svc.entitlements.has_at_least(workspace_id, "personalized_checklist", "on"):
        rule_categories = build_rule_categories(req)
        items = [{"title": c["title"], "tier": c["tier"], "reason": c["reason"]} for c in rule_categories]
        svc.db.save_checklist_items(workspace_id, company["id"], items)

    return DocumentUploadResponse(
        document_id=doc_id,
        company_profile_id=company["id"],
        filename=filename,
        chunk_count=len(chunks),
        sections=list(dict.fromkeys(c.section for c in chunks)),
    )


def answers_stage_label(stage: str) -> str:
    return {
        "exploring_idea": "Idea Stage",
        "planning_launch": "Planning Launch",
        "recently_started": "Recently Started",
        "operating": "Operating Business",
    }.get(stage, stage)
