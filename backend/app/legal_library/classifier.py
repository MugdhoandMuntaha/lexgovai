"""ClassifierAgent: Assigns domain tags, status guesses, AI summaries, and explicit statutory relations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.ports import LLMClient

CONTROLLED_DOMAINS = (
    "tax_vat",
    "income_tax",
    "customs",
    "labor",
    "company_law",
    "banking",
    "securities",
    "environment",
    "trade",
    "data_privacy",
    "foreign_exchange",
    "general_corporate",
)


class ExtractedRelationItem(BaseModel):
    target_law_title: str = Field(description="Name or citation of the related law, act, or SRO")
    relation: Literal["amends", "repeals", "supersedes", "refers_to", "implements"] = Field(
        description="Nature of the statutory relationship"
    )


class ClassificationOutput(BaseModel):
    domain_tags: list[str] = Field(
        default_factory=list,
        description=f"1 to 4 tags selected from controlled vocabulary: {list(CONTROLLED_DOMAINS)}",
    )
    status: Literal["in_force", "amended", "repealed", "unknown"] = Field(
        default="in_force", description="Current legal force status inferred from statutory wording"
    )
    status_confidence: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Mathematical confidence in the status classification"
    )
    summary_ai: str = Field(
        description="Concise 2 to 4 sentence executive compliance summary of the law's main obligations and scope."
    )
    relations: list[ExtractedRelationItem] = Field(
        default_factory=list,
        description="Explicit legislative relations cited in the text (e.g. this SRO amends SRO 144)",
    )


@dataclass(frozen=True)
class ClassificationResult:
    domain_tags: list[str]
    status: str
    status_confidence: float
    summary_ai: str
    relations: list[ExtractedRelationItem]
    is_ai_generated: bool = True


def heuristic_classify(title: str, text: str) -> ClassificationResult:
    """Deterministic keyword-based classification fallback."""
    combined = f"{title.lower()} {text[:10000].lower()}"
    tags: list[str] = []

    if any(k in combined for k in ("vat", "value added tax", "মূসক", "sro")):
        tags.append("tax_vat")
    if any(k in combined for k in ("income tax", "আয়কর", "taxation")):
        tags.append("income_tax")
    if any(k in combined for k in ("customs", "tariff", "duty", "আমদানি", "রপ্তানি")):
        tags.append("customs")
    if any(k in combined for k in ("labor", "labour", "wages", "worker", "শ্রমিক", "শ্রম")):
        tags.append("labor")
    if any(k in combined for k in ("company", "corporate", "shareholder", "rjsc")):
        tags.append("company_law")
    if any(k in combined for k in ("bank", "loan", "credit", "interest rate", "বাংলাদেশ ব্যাংক")):
        tags.append("banking")
    if any(k in combined for k in ("environment", "pollution", "doe", "পরিবেশ")):
        tags.append("environment")

    if not tags:
        tags.append("general_corporate")

    status = "in_force"
    confidence = 0.85
    if "hereby repealed" in combined or "is repealed" in combined or "রহিত করা হইল" in combined:
        status = "repealed"
        confidence = 0.95
    elif "hereby amended" in combined or "amendment" in combined or "সংশোধন" in combined:
        status = "amended"
        confidence = 0.90

    preamble = ""
    for line in text.split("\n")[:15]:
        line_clean = line.strip()
        if any(line_clean.lower().startswith(p) for p in ("an act to", "an ordinance to", "a notification to", "whereas", "সংবিধিবদ্ধ")):
            preamble = line_clean
            break
    if not preamble:
        for line in text.split("\n")[:10]:
            if len(line.strip()) > 30:
                preamble = line.strip()
                break

    summary = f"{title}. {preamble}".strip() if preamble else f"Statutory legislation: {title}."
    return ClassificationResult(
        domain_tags=tags,
        status=status,
        status_confidence=confidence,
        summary_ai=summary,
        relations=[],
        is_ai_generated=True,
    )


class ClassifierAgent:
    """Agent that assigns domain classifications, status estimates, and extracts legal relationships."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    def classify(self, title: str, text: str) -> ClassificationResult:
        if not self.llm:
            return heuristic_classify(title, text)

        prompt = (
            "You are an expert legal scholar on Bangladesh statutory legislation. "
            "Analyze the legal text and categorize it.\n"
            f"TITLE: {title}\n"
            f"CONTROLLED DOMAIN VOCABULARY: {list(CONTROLLED_DOMAINS)}\n"
            "INSTRUCTIONS:\n"
            "1. Assign 1 to 4 domain tags from the controlled vocabulary.\n"
            "2. Assess whether the instrument is in_force, amended, or repealed.\n"
            "3. Extract any explicit laws/SROs that this instrument amends, repeals, or implements.\n"
            "4. Provide a factual 2-3 sentence executive compliance summary.\n\n"
            f"TEXT EXCERPT:\n{text[:25000]}"
        )
        try:
            out = self.llm.generate_json(
                prompt=prompt,
                schema=ClassificationOutput,
                system="You are an expert legal scholar on Bangladesh statutory legislation.",
            )
            # Filter domain tags strictly against controlled vocabulary
            valid_tags = [t for t in out.domain_tags if t in CONTROLLED_DOMAINS]
            if not valid_tags:
                valid_tags = ["general_corporate"]

            return ClassificationResult(
                domain_tags=valid_tags,
                status=out.status,
                status_confidence=out.status_confidence,
                summary_ai=out.summary_ai,
                relations=out.relations,
                is_ai_generated=True,
            )
        except Exception:
            return heuristic_classify(title, text)
