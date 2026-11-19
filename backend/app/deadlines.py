"""Regulation-derived deadline extractor and verification module.

Uses LLM structured output to identify statutory due dates, then deterministically
verifies every quote against the regulation text using RapidFuzz.
Never invents deadlines.
"""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field

from .llm import LLMClient
from .verification import SourceChunk, verify_citation

logger = logging.getLogger("complianceos.deadlines")


class ExtractedDeadlineItem(BaseModel):
    title: str = Field(description="Brief title of the mandatory compliance deadline or filing obligation")
    lead_days: int = Field(default=15, description="Number of calendar days allowed or recurring cycle interval")
    statutory_quote: str = Field(description="Exact verbatim quote from the regulation establishing this deadline")
    recommended_date: str = Field(default="", description="Calculated ISO date or relative due description")


class DeadlineExtractionOutput(BaseModel):
    deadlines: list[ExtractedDeadlineItem]


def extract_and_verify_deadlines(
    llm: LLMClient, regulation_text: str, regulation_title: str
) -> list[dict[str, Any]]:
    """Extracts statutory deadlines and deterministically verifies quotes with RapidFuzz."""
    prompt = (
        f"Analyze the following official regulation text for '{regulation_title}'.\n\n"
        f"=== REGULATION TEXT ===\n{regulation_text}\n\n"
        "Extract every statutory filing deadline, payment cutoff, or time-bound obligation. "
        "For each obligation, provide an exact verbatim quote from the text that proves the deadline."
    )
    system = "You are an expert Bangladeshi VAT and corporate compliance auditor. Extract statutory deadlines strictly quoting the provided text."

    out = llm.generate_json(prompt, DeadlineExtractionOutput, system)
    results = []

    sources = [SourceChunk(source=regulation_title, section="Statutory Provision", text=regulation_text)]

    for item in out.deadlines:
        # RapidFuzz deterministic verification against the regulation text
        score, _, span = verify_citation(snippet=item.statutory_quote, sources=sources)
        is_verified = score >= 0.75

        status = "pending_confirmation" if is_verified else "needs_review"
        results.append({
            "title": item.title,
            "lead_days": item.lead_days,
            "quote": span,
            "confidence": score,
            "status": status,
            "flagged_for_review": not is_verified,
        })

    return results
