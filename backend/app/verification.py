"""Deterministic quotation and snippet verification using RapidFuzz.

Extracted from Agent 5 (Critic) as a pure refactor. Used across the multi-agent pipeline,
the AI compliance assistant, and regulation-derived deadline verification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from rapidfuzz import fuzz


@dataclass(frozen=True)
class SourceChunk:
    source: str
    section: str
    text: str


def normalise_text(text: str) -> str:
    """Normalizes quotes, dashes, and whitespace for robust citation comparison."""
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip().strip("\"'").strip()


def verbatim_span(snippet: str, source: str) -> str:
    """Exact substring of `source` that best matches `snippet`, widened to whole words."""
    alignment = fuzz.partial_ratio_alignment(snippet, source)
    if alignment is None:
        return snippet
    start, end = alignment.dest_start, alignment.dest_end
    while start > 0 and not source[start - 1].isspace():
        start -= 1
    while end < len(source) and not source[end].isspace():
        end += 1
    return source[start:end].strip()


def verify_citation(snippet: str, sources: list[SourceChunk]) -> tuple[float, SourceChunk | None, str]:
    """Matches a claimed quote/snippet against candidate text chunks.

    Returns:
        (confidence_score_0_to_1, best_matching_chunk, verbatim_text_span)
    """
    needle = normalise_text(snippet)
    if not needle or not sources:
        return 0.0, None, snippet

    best_score, best_chunk = -1.0, None
    for chunk in sources:
        score = fuzz.partial_ratio(needle, normalise_text(chunk.text))
        if score > best_score:
            best_score, best_chunk = score, chunk

    if best_chunk is None:
        return 0.0, None, snippet

    haystack = normalise_text(best_chunk.text)
    verbatim = verbatim_span(needle, haystack) if len(needle) <= len(haystack) else needle
    return round(best_score / 100, 2), best_chunk, verbatim
