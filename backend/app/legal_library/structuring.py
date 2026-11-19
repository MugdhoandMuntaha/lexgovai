"""StructuringAgent: Splits legal texts into chapters/sections/subsections while preserving original numbering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from app.ports import LLMClient


class StructuredSectionItem(BaseModel):
    level: Literal["chapter", "part", "section", "subsection", "schedule"] = "section"
    number_label: str = Field(description="Original numbering label, e.g. 'Chapter 1', 'Section 4', 'Clause 4.2', 'Schedule A'")
    heading: str | None = Field(default=None, description="Heading title if specified, e.g. 'Short title and commencement'")
    text: str = Field(description="Verbatim text of the section/clause without alteration")


class StructuringOutput(BaseModel):
    canonical_title_en: str = Field(description="Official canonical title in English")
    canonical_title_bn: str | None = Field(default=None, description="Official title in Bengali if mentioned")
    act_number: str | None = Field(default=None, description="Official act/order number, e.g. 'Act No. 47 of 2012' or 'S.R.O. No. 144-Law/2025/112-VAT'")
    year: int | None = Field(default=None, description="Promulgation or statutory enactment year")
    law_type: Literal["act", "ordinance", "sro", "rule", "circular", "order", "gazette_notice"] = Field(
        default="act", description="Statutory instrument type"
    )
    issuing_body: str = Field(default="Government of Bangladesh", description="Legislative or statutory issuing authority")
    language_detected: str = Field(default="en", description="'en', 'bn', or 'en,bn'")
    sections: list[StructuredSectionItem] = Field(default_factory=list, description="Ordered list of structured legal sections")


@dataclass(frozen=True)
class StructuringResult:
    data: StructuringOutput
    is_verified: bool
    verification_notes: str | None = None


def heuristic_split_sections(text: str) -> list[StructuredSectionItem]:
    """Deterministic regex heuristic fallback splitter for statutory legal texts."""
    lines = text.split("\n")
    sections: list[StructuredSectionItem] = []
    current_label = "Preamble"
    current_heading = "Preliminary"
    current_lines: list[str] = []

    pattern = re.compile(
        r"^(chapter\s+[IVXLCDM\d]+|part\s+[IVXLCDM\d]+|section\s+\d+|clause\s+\d+(\.\d+)*|\d+(\.\d+)*[.)])\s*(.*)$",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = pattern.match(stripped)
        if m:
            if current_lines:
                sections.append(
                    StructuredSectionItem(
                        level="section",
                        number_label=current_label,
                        heading=current_heading,
                        text="\n".join(current_lines).strip(),
                    )
                )
                current_lines = []
            current_label = m.group(1).strip()
            rest = m.group(4).strip() if m.group(4) else None
            current_heading = rest
            if rest:
                current_lines.append(rest)
        else:
            current_lines.append(stripped)

    if current_lines:
        sections.append(
            StructuredSectionItem(
                level="section",
                number_label=current_label,
                heading=current_heading,
                text="\n".join(current_lines).strip(),
            )
        )

    if not sections:
        sections.append(
            StructuredSectionItem(
                level="section",
                number_label="Section 1",
                heading="General Provisions",
                text=text.strip(),
            )
        )

    return sections


class StructuringAgent:
    """Agent that extracts structured metadata and section hierarchies from raw legal texts."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    def structure(self, raw_text: str, filename_hint: str = "") -> StructuringResult:
        if not raw_text.strip():
            empty_out = StructuringOutput(
                canonical_title_en="Empty Document",
                law_type="act",
                issuing_body="Unknown",
                sections=[],
            )
            return StructuringResult(data=empty_out, is_verified=False, verification_notes="Source text is empty.")

        struct_output: StructuringOutput | None = None

        if self.llm:
            prompt = (
                "You are an expert legal drafter and statutory archivist in Bangladesh. "
                "Structure the following authoritative legal document into chapters, sections, clauses, and schedules.\n"
                "RULES:\n"
                "1. PRESERVE ORIGINAL NUMBERING exactly (e.g. 'Section 15', 'Clause 4.2', 'Schedule A').\n"
                "2. Transcribe the text of each section VERBATIM without omission, summarization, or hallucination.\n"
                "3. Extract title in English and Bengali if present, the official act or SRO number, year, and issuing authority.\n\n"
                f"DOCUMENT TEXT:\n{raw_text[:60000]}"
            )
            try:
                struct_output = self.llm.generate_json(
                    prompt=prompt,
                    schema=StructuringOutput,
                    system="You are an expert legal drafter and statutory archivist in Bangladesh.",
                )
            except Exception:
                struct_output = None

        if not struct_output or not struct_output.sections:
            # Fallback heuristic structuring
            sections = heuristic_split_sections(raw_text)
            title = filename_hint.replace(".txt", "").replace(".pdf", "").replace("_", " ").title() or "Statutory Document"
            struct_output = StructuringOutput(
                canonical_title_en=title,
                law_type="act" if "act" in title.lower() else "sro" if "sro" in title.lower() else "order",
                issuing_body="Government of Bangladesh",
                sections=sections,
            )

        # Deterministic RapidFuzz & Length Verification
        total_extracted_text = " ".join(s.text for s in struct_output.sections)
        raw_clean = " ".join(raw_text.split())
        extracted_clean = " ".join(total_extracted_text.split())

        len_ratio = len(extracted_clean) / max(len(raw_clean), 1)
        sim_score = fuzz.partial_ratio(extracted_clean[:10000], raw_clean[:10000])

        is_verified = (0.70 <= len_ratio <= 1.35) and (sim_score >= 70)
        notes = None
        if not is_verified:
            notes = (
                f"Structuring verification flagged: length ratio={len_ratio:.2f} (expected 0.70-1.35), "
                f"alignment similarity={sim_score:.1f}% (expected >= 70%). Check for omitted or hallucinated clauses."
            )

        return StructuringResult(
            data=struct_output,
            is_verified=is_verified,
            verification_notes=notes,
        )
