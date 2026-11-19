"""Enterprise-grade PDF generator for Starter SOPs and Compliance Roadmaps.

Produces formal, beautifully styled corporate PDFs with running headers,
two-pass page numbering (Page X of Y), metadata grids, structured articles,
policy schedules, sign-off blocks, and statutory notices using ReportLab.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import StarterAnswers, StarterGuideResponse, StarterPolicyItem
from .starter import (
    JURISDICTION_MAP,
    SECTOR_MAP,
    answers_stage_label,
    build_rule_categories,
    build_starter_sop_text,
    generate_static_guide,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that accumulates total page count and stamps formal headers/footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        page_w, page_h = letter

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#0F172A"))
            self.drawString(54, page_h - 36, "LexGOV AI")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(102, page_h - 36, "|   Standard Operating Procedure: Governance & Statutory Compliance")
            self.drawRightString(page_w - 54, page_h - 36, "REF: SOP-START-2025-V1")

            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.75)
            self.line(54, page_h - 42, page_w - 54, page_h - 42)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(54, 46, page_w - 54, 46)

        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#047857"))
        self.drawString(54, 34, "CONFIDENTIAL")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(120, 34, "— For Internal Organizational Governance & Regulatory Audit Only")

        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(page_w - 54, 34, page_str)

        self.restoreState()


def generate_starter_sop_pdf(
    answers: StarterAnswers,
    company_name: str,
    guide: StarterGuideResponse | None = None,
) -> bytes:
    """Generates a formal, executive-ready PDF document for the Starter SOP."""
    buffer = io.BytesIO()

    # 54 pt = 0.75 in margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    clean_name = company_name.strip() or "My Business Ltd."
    sector_name = SECTOR_MAP.get(answers.sector, "Commercial Enterprise")
    stage_label = answers_stage_label(answers.stage)
    jurisdiction_label = JURISDICTION_MAP.get(answers.jurisdiction, "Bangladesh")
    now_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    if guide is None:
        rule_categories = build_rule_categories(answers)
        guide = generate_static_guide(answers, rule_categories)

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#047857"),
        spaceAfter=14,
    )

    badge_style = ParagraphStyle(
        "DocBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#065F46"),
        alignment=TA_LEFT,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#334155"),
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3,
    )

    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748B"),
    )

    meta_val = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )

    story: list[Any] = []

    # -----------------------------------------------------------------------
    # Document Header & Title Banner
    # -----------------------------------------------------------------------
    story.append(Paragraph("LEXGOV AI &bull; REGULATORY COMPLIANCE SYSTEM", badge_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("STANDARD OPERATING PROCEDURE", title_style))
    story.append(
        Paragraph("Corporate Governance, Statutory Recordkeeping & Baseline Operating Standards", subtitle_style)
    )

    # -----------------------------------------------------------------------
    # Metadata Grid Table
    # -----------------------------------------------------------------------
    meta_data = [
        [
            Paragraph("COMPANY LEGAL NAME", meta_label),
            Paragraph(clean_name, meta_val),
            Paragraph("DOCUMENT REF", meta_label),
            Paragraph("SOP-START-2025-V1", meta_val),
        ],
        [
            Paragraph("INDUSTRY SECTOR", meta_label),
            Paragraph(sector_name, meta_val),
            Paragraph("OPERATING STAGE", meta_label),
            Paragraph(stage_label, meta_val),
        ],
        [
            Paragraph("JURISDICTION", meta_label),
            Paragraph(jurisdiction_label, meta_val),
            Paragraph("EFFECTIVE DATE", meta_label),
            Paragraph(now_date, meta_val),
        ],
        [
            Paragraph("BENCHMARK LAW", meta_label),
            Paragraph("NBR VAT Act 2012 / SRO 4.2", meta_val),
            Paragraph("SECURITY LEVEL", meta_label),
            Paragraph("Confidential &bull; Internal", meta_val),
        ],
    ]

    col_widths = [110, 150, 100, 144]
    meta_table = Table(meta_data, colWidths=col_widths)
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # -----------------------------------------------------------------------
    # Section 1: Executive Summary & Administrative Mandate
    # -----------------------------------------------------------------------
    story.append(Paragraph("1. Executive Summary & Administrative Mandate", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=8))

    summary_text = guide.summary if guide and guide.summary else (
        f"This Standard Operating Procedure establishes baseline corporate governance, operational responsibilities, "
        f"and statutory compliance standards for {clean_name}. Tailored for the {sector_name} sector in {jurisdiction_label}, "
        f"it codifies mandatory administrative controls across personnel, taxation, commercial documentation, and record retention."
    )
    story.append(Paragraph(summary_text, body_style))

    if guide and guide.jurisdiction_notice:
        notice_data = [[
            Paragraph("<b>JURISDICTION NOTICE:</b> " + guide.jurisdiction_notice, ParagraphStyle(
                "NoticeText",
                parent=body_style,
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#92400E"),
            ))
        ]]
        notice_table = Table(notice_data, colWidths=[504])
        notice_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#FDE68A")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(Spacer(1, 4))
        story.append(notice_table)
        story.append(Spacer(1, 6))

    # -----------------------------------------------------------------------
    # Section 2: Core Operating Articles
    # -----------------------------------------------------------------------
    story.append(Paragraph("2. Standard Operating Procedures & Internal Controls", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=8))

    # Article 2.1 Governance
    story.append(Paragraph("Article 2.1 — Organizational Governance, Administration & Staffing", h2_style))
    if answers.hiring == "solo":
        gov_text = (
            f"The principal founder and managing executive of {clean_name} retains direct custodial oversight over all commercial "
            "contracts, financial disbursements, and statutory regulatory filings. No secondary staff are currently engaged. "
            "Prior to onboarding any future personnel or contract workers, the organization shall formally draft written "
            "appointment letters stipulating remuneration, duties, confidentiality clauses, and working hours in strict "
            "adherence to the Bangladesh Labor Act."
        )
    else:
        gov_text = (
            f"Operational governance at {clean_name} is distributed among designated executive managers and supervisory staff. "
            "All hired personnel must be issued written employment appointment letters explicitly outlining job description, "
            "gross remuneration, statutory deductions, standard working hours, and termination notice periods. "
            "Monthly salary disbursements shall be executed via scheduled electronic transfers or audited payroll registers "
            "no later than the designated statutory salary cut-off date each calendar month."
        )
    story.append(Paragraph(gov_text, body_style))

    # Article 2.2 Financial Documentation & Invoicing
    story.append(Paragraph("Article 2.2 — Commercial Transactions, Invoicing & Cash Custody", h2_style))
    fin_lines: list[str] = [
        f"All commercial sales and service engagements contracted by {clean_name} shall be supported by sequentially "
        "numbered commercial invoices containing clear itemization, buyer identification, and applicable tax notations."
    ]
    if answers.payments in ("digital", "both"):
        fin_lines.append(
            "For payments received via digital banking, merchant cards, or Mobile Financial Services (MFS such as bKash/Nagad), "
            "the finance officer shall reconcile payment gateway settlement batches against commercial bank statements daily. "
            "Discrepancies exceeding 24 hours must be formally logged and escalated for administrative review."
        )
    if answers.payments in ("cash", "both"):
        fin_lines.append(
            "Physical cash receipts must be promptly recorded in the daily cash register ledger and secured in locked safe custody. "
            "Physical cash accumulation must be deposited into the commercial banking account at minimum once every business week "
            "to minimize on-premises risk exposure and satisfy cash ceiling regulations."
        )
    story.append(Paragraph(" ".join(fin_lines), body_style))

    # Article 2.3 Tax & VAT Compliance
    story.append(Paragraph("Article 2.3 — National Board of Revenue (NBR) VAT & Statutory Filings", h2_style))
    vat_text = (
        f"In compliance with statutory requirements, {clean_name} maintains current registration with the National Board "
        "of Revenue (NBR), displaying its Business Identification Number (BIN) and Tax Identification Number (TIN) on all "
        "official communications and tax invoices. Monthly Value Added Tax (VAT) returns (Mushak-9.1) shall be finalized "
        "and submitted through the NBR VAT online portal within statutory deadlines. All relevant purchase ledgers (Mushak-6.1), "
        "sales ledgers (Mushak-6.2), treasury challans, and withholding tax certificates (Mushak-6.3) must be maintained "
        "in orderly chronological archives readily accessible for statutory inspection."
    )
    story.append(Paragraph(vat_text, body_style))

    # Article 2.4 Customer Privacy
    story.append(Paragraph("Article 2.4 — Customer Data Confidentiality & Grievance Resolution", h2_style))
    if answers.collects_data in ("yes", "unsure"):
        privacy_text = (
            f"{clean_name} collects customer contact and transaction details exclusively for legitimate order execution, "
            "tax documentation, and warranty services. Personal identifying information (PII) must be stored in encrypted "
            "or access-restricted systems and shall not be rented, sold, or shared with unauthorized third parties. "
            "Customer inquiries or service complaints shall be registered in an internal tracking log and resolved within "
            "two business days under fair trading guidelines."
        )
    else:
        privacy_text = (
            f"{clean_name} conducts customer interactions on an immediate transactional basis without retaining persistent "
            "personal profiles. Commercial transaction records are archived strictly for accounting reconciliation and tax auditing."
        )
    story.append(Paragraph(privacy_text, body_style))

    # Article 2.5 Records Retention
    story.append(Paragraph("Article 2.5 — Record Retention, Cyber Hygiene & Audit Readiness", h2_style))
    sec_text = (
        "All corporate books of accounts, statutory tax returns, bank statements, lease agreements, and employee records "
        "must be preserved for a statutory minimum duration of 5 (five) calendar years from the date of origination. "
        "Access credentials for accounting platforms, email suites, and government portals must utilize strong multi-character "
        "passwords and undergo mandatory quarterly rotation. This SOP document shall be reviewed annually by executive leadership."
    )
    story.append(Paragraph(sec_text, body_style))
    story.append(Spacer(1, 10))

    # -----------------------------------------------------------------------
    # Section 3: Prioritized Compliance Policy Roadmap (Schedule A)
    # -----------------------------------------------------------------------
    story.append(Paragraph("3. Schedule A — Prioritized Statutory Compliance Roadmap", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=8))
    story.append(
        Paragraph(
            "The following policy mandates and implementation controls were dynamically derived by the LexGOV AI rule engine "
            f"specifically for {clean_name}'s operational footprint. They define mandatory action items across operational phases.",
            body_style,
        )
    )

    tier_labels: dict[str, tuple[str, str, str]] = {
        "start_now": ("TIER 1 &bull; IMMEDIATE FOUNDATIONS (START NOW)", "#BE123C", "#FFF1F2"),
        "soon": ("TIER 2 &bull; NEAR-TERM OPERATIONAL SETUP (SOON)", "#B45309", "#FFFBEB"),
        "later": ("TIER 3 &bull; GROWTH & SCALING GOVERNANCE (LATER)", "#334155", "#F8FAFC"),
    }

    if guide and guide.policies:
        for tier_key in ("start_now", "soon", "later"):
            tier_policies = [p for p in guide.policies if p.tier == tier_key]
            if not tier_policies:
                continue

            tier_title, text_color, bg_color = tier_labels.get(
                tier_key, ("PRIORITY ACTION", "#0F172A", "#F8FAFC")
            )

            story.append(Spacer(1, 6))
            tier_badge = Paragraph(
                f"<b>{tier_title}</b>",
                ParagraphStyle(
                    f"Tier_{tier_key}",
                    parent=styles["Normal"],
                    fontName="Helvetica-Bold",
                    fontSize=8.5,
                    leading=11,
                    textColor=colors.HexColor(text_color),
                ),
            )
            t_box = Table([[tier_badge]], colWidths=[504])
            t_box.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_color)),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(text_color)),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(t_box)
            story.append(Spacer(1, 6))

            for pol in tier_policies:
                pol_elements: list[Any] = []
                pol_title_text = f"<b>{pol.title}</b> &nbsp;<font size=7 color='#64748B'>[REF #{pol.id}]</font>"
                pol_elements.append(Paragraph(pol_title_text, h2_style))
                pol_elements.append(
                    Paragraph(f"<b>Mandate:</b> {pol.reason}", ParagraphStyle("Reason", parent=body_style, fontSize=8.5, textColor=colors.HexColor("#047857")))
                )
                pol_elements.append(
                    Paragraph(f"<b>Scope:</b> {pol.covers}", ParagraphStyle("Covers", parent=body_style, fontSize=8.5))
                )
                pol_elements.append(Paragraph("<b>Recommended Implementation Controls:</b>", meta_label))
                for pt in pol.include_points:
                    pol_elements.append(Paragraph(f"&bull;&nbsp; {pt}", bullet_style))
                pol_elements.append(Spacer(1, 6))

                story.append(KeepTogether(pol_elements))

    story.append(Spacer(1, 10))

    # -----------------------------------------------------------------------
    # Section 4: Sign-Off & Administrative Endorsement Block
    # -----------------------------------------------------------------------
    endorse_elements: list[Any] = []
    endorse_elements.append(Paragraph("4. Administrative Endorsement & Sign-Off", h1_style))
    endorse_elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=10))
    endorse_elements.append(
        Paragraph(
            "By signature below, the designated operational lead and executive authority confirm that this Standard "
            f"Operating Procedure has been reviewed, adopted as organizational policy for {clean_name}, and distributed "
            "to relevant internal personnel for immediate compliance.",
            body_style,
        )
    )
    endorse_elements.append(Spacer(1, 12))

    sign_data = [
        [
            Paragraph("<b>PREPARED & SUBMITTED BY:</b>", meta_label),
            Paragraph("<b>APPROVED & ADOPTED BY:</b>", meta_label),
        ],
        [
            Paragraph("<br/><br/>________________________________________<br/><b>Operational Lead / Compliance Officer</b><br/>Name:<br/>Date:", body_style),
            Paragraph("<br/><br/>________________________________________<br/><b>Managing Director / Governing Authority</b><br/>Name:<br/>Date:", body_style),
        ],
    ]
    sign_table = Table(sign_data, colWidths=[250, 254])
    sign_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    endorse_elements.append(sign_table)
    story.append(KeepTogether(endorse_elements))

    story.append(Spacer(1, 12))

    # -----------------------------------------------------------------------
    # Section 5: Statutory Disclaimer Callout
    # -----------------------------------------------------------------------
    disclaimer_text = (
        "<b>LEGAL DISCLAIMER:</b> This Standard Operating Procedure is an automated compliance template generated by "
        "LexGOV AI based upon inputs provided during the Start Fresh guided questionnaire. It is intended for administrative "
        "structuring and benchmark alignment against NBR VAT and statutory standards. It does not constitute formal legal "
        "advice, attorney representation, or an official certification from the National Board of Revenue. Organizations must "
        "consult qualified Bangladeshi legal counsel and certified tax practitioners to verify local filing obligations."
    )
    disc_table = Table([[Paragraph(disclaimer_text, ParagraphStyle("Disc", parent=body_style, fontSize=7.5, leading=10.5, textColor=colors.HexColor("#64748B")))]], colWidths=[504])
    disc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(disc_table)

    # Build the document with our two-pass NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_document_pdf(doc: dict[str, Any], company_name: str = "Company") -> bytes:
    """Renders any stored SOP document text into an executive-ready, structured PDF."""
    buffer = io.BytesIO()
    doc_template = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    clean_name = company_name.strip() or "Company"
    filename = doc.get("filename", "Standard Operating Procedure")
    created_at = doc.get("created_at", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(created_at)
        formatted_date = dt.strftime("%B %d, %Y")
    except Exception:
        formatted_date = created_at[:10]

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#047857"),
        spaceAfter=14,
    )
    badge_style = ParagraphStyle(
        "DocBadge2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#065F46"),
    )
    h1_style = ParagraphStyle(
        "SectionH1_2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "BodyDark2",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    meta_label = ParagraphStyle(
        "MetaLabel2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748B"),
    )
    meta_val = ParagraphStyle(
        "MetaValue2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )

    story: list[Any] = []
    story.append(Paragraph("LEXGOV AI &bull; REGULATORY COMPLIANCE SYSTEM", badge_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("STANDARD OPERATING PROCEDURE", title_style))
    story.append(Paragraph("Official Corporate Governance & Regulatory Baseline Policy", subtitle_style))

    meta_data = [
        [
            Paragraph("COMPANY NAME", meta_label),
            Paragraph(clean_name, meta_val),
            Paragraph("DOCUMENT ID", meta_label),
            Paragraph(str(doc.get("id", "DOC-001")), meta_val),
        ],
        [
            Paragraph("FILE NAME", meta_label),
            Paragraph(filename, meta_val),
            Paragraph("INDEXED CHUNKS", meta_label),
            Paragraph(f"{doc.get('chunk_count', 1)} Chunks", meta_val),
        ],
        [
            Paragraph("EFFECTIVE DATE", meta_label),
            Paragraph(formatted_date, meta_val),
            Paragraph("CLASSIFICATION", meta_label),
            Paragraph("Confidential &bull; Internal", meta_val),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[110, 150, 100, 144])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # Parse document text into sections
    text = doc.get("text", "")
    lines = text.split("\n")
    current_section = "1. Operational Overview"
    current_paragraphs: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Ignore raw header lines that match metadata
        if (
            stripped.startswith("Standard Operating Procedure:")
            or stripped.startswith("Company:")
            or stripped.startswith("Industry Sector:")
            or stripped.startswith("Jurisdiction:")
            or stripped.startswith("Watermark:")
        ):
            continue
        if stripped.lower().startswith("section ") or stripped.lower().startswith("article "):
            if current_paragraphs:
                story.append(Paragraph(current_section, h1_style))
                story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=6))
                for p in current_paragraphs:
                    story.append(Paragraph(p, body_style))
                story.append(Spacer(1, 6))
                current_paragraphs = []
            current_section = stripped
        else:
            current_paragraphs.append(stripped)

    if current_paragraphs:
        story.append(Paragraph(current_section, h1_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=6))
        for p in current_paragraphs:
            story.append(Paragraph(p, body_style))

    story.append(Spacer(1, 14))

    # Sign-off block
    sign_data = [
        [
            Paragraph("<b>PREPARED & SUBMITTED BY:</b>", meta_label),
            Paragraph("<b>APPROVED & ADOPTED BY:</b>", meta_label),
        ],
        [
            Paragraph("<br/><br/>________________________________________<br/><b>Operational Lead / Compliance Officer</b><br/>Name:<br/>Date:", body_style),
            Paragraph("<br/><br/>________________________________________<br/><b>Managing Director / Governing Authority</b><br/>Name:<br/>Date:", body_style),
        ],
    ]
    sign_table = Table(sign_data, colWidths=[250, 254])
    sign_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(KeepTogether([
        Paragraph("Administrative Endorsement & Sign-Off", h1_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=8),
        sign_table,
    ]))

    doc_template.build(story, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

