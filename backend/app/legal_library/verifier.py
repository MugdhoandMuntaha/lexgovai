"""VerifierAgent: Zero-LLM deterministic verifier using RapidFuzz to ground AI summaries against official source text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from rapidfuzz import fuzz


@dataclass(frozen=True)
class VerificationResult:
    is_verified: bool
    sentence_scores: list[tuple[str, float]]
    average_score: float
    notes: str | None = None


class VerifierAgent:
    """Deterministic RapidFuzz verifier that validates AI summaries against authoritative source text."""

    def __init__(self, min_sentence_score: float = 65.0, min_average_score: float = 72.0):
        self.min_sentence_score = min_sentence_score
        self.min_average_score = min_average_score

    def verify_summary(self, summary_ai: str, source_text: str) -> VerificationResult:
        if not summary_ai.strip() or not source_text.strip():
            return VerificationResult(
                is_verified=False,
                sentence_scores=[],
                average_score=0.0,
                notes="Summary or source text is empty.",
            )

        # Split summary into distinct sentences (supporting English .?! and Bengali দাড়ি ।)
        raw_sentences = re.split(r"[.?!।]\s+", summary_ai.strip())
        sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 15]

        if not sentences:
            sentences = [summary_ai.strip()]

        scores: list[tuple[str, float]] = []
        # Pre-clean source text into a single space-normalized string for fast partial_ratio
        clean_source = " ".join(source_text.split())

        for sent in sentences:
            clean_sent = " ".join(sent.split())
            score_partial = float(fuzz.partial_ratio(clean_sent, clean_source))
            score_token = float(fuzz.token_set_ratio(clean_sent, clean_source))
            score = max(score_partial, score_token)
            scores.append((sent, score))

        avg_score = sum(s[1] for s in scores) / max(len(scores), 1)

        # Check if every sentence satisfies min_sentence_score and average satisfies min_average_score
        all_sentences_pass = all(s[1] >= self.min_sentence_score for s in scores)
        avg_passes = avg_score >= self.min_average_score

        is_verified = all_sentences_pass and avg_passes

        notes = None
        if not is_verified:
            failing = [f"'{s[0][:40]}...' (score {s[1]:.1f})" for s in scores if s[1] < self.min_sentence_score]
            notes = (
                f"Summary verification flagged (avg score {avg_score:.1f}%): "
                f"Unverified claims in {len(failing)} sentence(s): {'; '.join(failing)}"
            )

        return VerificationResult(
            is_verified=is_verified,
            sentence_scores=scores,
            average_score=avg_score,
            notes=notes,
        )
