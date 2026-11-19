"""The five compliance agents.

1. Watcher      - deterministic diff + LLM summary of what changed in the regulation (cached per version hash)
2. Retriever    - embeds each new obligation and pulls the most relevant SOP sections from ChromaDB
3. Analyzer     - LLM compares obligations against retrieved SOP text and emits cited findings
4. Generator    - LLM drafts replacement SOP clauses and operational fixes
5. Critic       - deterministic RapidFuzz check that every citation really exists in its source text
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .db import new_id
from .documents import chunk_text
from .regulations import RegulationPair, load_regulation_pair, make_regulation_pair, load_regulation_pair_by_id
from .schemas import AnalyzerLLMOutput, GeneratorLLMOutput, WatcherLLMOutput
from .services import Services
from .verification import SourceChunk, verify_citation

ISSUE_TYPES = {"gap", "conflict", "outdated_reference"}
SEVERITIES = {"low", "medium", "high"}
URGENCIES = {"low", "medium", "high", "critical"}
CHANGE_TYPES = {"amendment", "new_obligation", "repeal", "clarification"}

SYSTEM_PROMPT = (
    "You are a meticulous regulatory compliance analyst for Bangladeshi SMEs, specialising in NBR VAT law. "
    "Base every statement strictly on the texts provided. Never invent clauses, numbers, or quotes. "
    "When asked for a quote, copy it character-for-character from the provided text."
)


def _norm_choice(value: str, allowed: set[str], default: str, aliases: dict[str, str] | None = None) -> str:
    key = re.sub(r"[\s\-]+", "_", (value or "").strip().lower())
    key = (aliases or {}).get(key, key)
    return key if key in allowed else default


def _clean_list(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item and item.strip()]


# ---------------------------------------------------------------------------
# Agent 1 - Watcher
# ---------------------------------------------------------------------------


def watcher_payload(pair: RegulationPair) -> dict:
    """The LLM-free part of the Watcher output (texts, titles, diff, hash)."""
    return {
        "regulation_id": pair.regulation_id,
        "version_hash": pair.version_hash,
        "before_title": pair.before_title,
        "after_title": pair.after_title,
        "before_text": pair.before_text,
        "after_text": pair.after_text,
        "diff": pair.diff,
    }


def run_watcher(
    svc: Services, pair: RegulationPair | None = None, regulation_id: str | None = None
) -> tuple[dict, bool]:
    """Returns (RegulationChangeResponse dict, served_from_cache)."""
    llm = svc.require_llm()
    if pair is None:
        pair = load_regulation_pair_by_id(svc.db, regulation_id, svc.settings.regulation_dir)
    cache_key = f"{pair.version_hash}:{llm.model_name}"

    analysis = svc.db.get_watcher_result(cache_key)
    cached = analysis is not None
    if analysis is None:
        prompt = (
            "Compare the previous and revised versions of this regulation.\n\n"
            f"=== PREVIOUS VERSION ===\n{pair.before_text}\n\n"
            f"=== REVISED VERSION ===\n{pair.after_text}\n\n"
            f"=== LINE DIFF ('-' removed, '+' added) ===\n{pair.changed_lines_text}\n\n"
            "Summarise the change, list each changed clause (before vs after), and list every concrete obligation "
            "a registered business must now satisfy (deadlines, named roles, penalties)."
        )
        out = llm.generate_json(prompt, WatcherLLMOutput, SYSTEM_PROMPT)
        analysis = {
            "title": out.title.strip() or pair.after_title,
            "change_summary": out.change_summary.strip(),
            "change_type": _norm_choice(out.change_type, CHANGE_TYPES, "amendment"),
            "changed_clauses": _clean_list(out.changed_clauses),
            "obligations": _clean_list(out.obligations),
        }
        svc.db.save_watcher_result(cache_key, analysis)

    return {**watcher_payload(pair), **analysis}, cached


# ---------------------------------------------------------------------------
# Agent 2 - Retriever
# ---------------------------------------------------------------------------


def run_retriever(svc: Services, document_id: str, watcher: dict) -> list[dict]:
    llm = svc.require_llm()
    queries = watcher["obligations"] or watcher["changed_clauses"]
    if not queries:
        return []

    vectors = llm.embed(queries, "RETRIEVAL_QUERY")
    merged: dict[str, dict] = {}
    for query, vector in zip(queries, vectors):
        for hit in svc.store.query(document_id, vector, svc.settings.retrieval_top_k):
            entry = merged.setdefault(
                hit.chunk_id,
                {"chunk_id": hit.chunk_id, "section": hit.section, "text": hit.text, "distance": hit.distance, "matched": []},
            )
            entry["distance"] = min(entry["distance"], hit.distance)
            entry["matched"].append(query)

    return sorted(merged.values(), key=lambda e: e["distance"])


# ---------------------------------------------------------------------------
# Agent 3 - Impact Analyzer
# ---------------------------------------------------------------------------


def _format_sop_excerpts(chunks: list[dict]) -> str:
    return "\n\n".join(f"[SOP section: {c['section']}]\n{c['text']}" for c in chunks) or "(no SOP text retrieved)"


def _format_regulation(pair: RegulationPair) -> str:
    return "\n\n".join(f"[Regulation section: {c.section}]\n{c.text}" for c in chunk_text(pair.after_text))


def run_analyzer(
    svc: Services,
    company: dict,
    watcher: dict,
    retrieved: list[dict],
    pair: RegulationPair | None = None,
    regulation_id: str | None = None,
) -> dict:
    llm = svc.require_llm()
    if pair is None:
        pair = load_regulation_pair_by_id(svc.db, regulation_id, svc.settings.regulation_dir)
    obligations = "\n".join(f"- {o}" for o in watcher["obligations"]) or "- (none extracted)"
    prompt = (
        f"Company: {company['company_name']} ({company['industry']}, {company['country']}).\n\n"
        f"Regulatory change summary: {watcher['change_summary']}\n\n"
        f"New obligations:\n{obligations}\n\n"
        f"=== REVISED REGULATION ===\n{_format_regulation(pair)}\n\n"
        f"=== COMPANY SOP EXCERPTS (retrieved as most relevant) ===\n{_format_sop_excerpts(retrieved)}\n\n"
        "Identify every way the SOP fails to meet the revised regulation. For each finding:\n"
        "- issue_type: 'gap' (SOP is silent), 'conflict' (SOP contradicts the rule) or 'outdated_reference' "
        "(SOP still cites the old rule/number).\n"
        "- severity: low, medium or high, based on legal and financial exposure.\n"
        "- citation: prefer quoting the SOP text that is non-compliant (citation_source='sop'); for pure gaps "
        "quote the regulation clause that is unmet (citation_source='regulation'). Copy the quote verbatim and "
        "give the section label exactly as shown in brackets.\n"
        "Also give an overall impact_score (0-100) and urgency (low, medium, high, critical). "
        "If the SOP already complies, return an empty findings list and a low score."
    )
    out: AnalyzerLLMOutput = llm.generate_json(prompt, AnalyzerLLMOutput, SYSTEM_PROMPT)

    findings = [
        {
            "id": new_id()[:12],
            "issue": f.issue.strip(),
            "issue_type": _norm_choice(f.issue_type, ISSUE_TYPES, "gap", {"outdated": "outdated_reference"}),
            "severity": _norm_choice(f.severity, SEVERITIES, "medium", {"critical": "high"}),
            "explanation": f.explanation.strip(),
            "citation_source": (f.citation_source or "").strip().lower(),
            "citation_section": f.citation_section.strip(),
            "citation_text_snippet": f.citation_text_snippet.strip(),
        }
        for f in out.findings
        if f.issue.strip()
    ]
    return {
        "impact_score": max(0, min(100, int(out.impact_score))),
        "urgency": _norm_choice(out.urgency, URGENCIES, "high"),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Agent 4 - Action Plan Generator
# ---------------------------------------------------------------------------


def run_generator(svc: Services, company: dict, watcher: dict, analysis: dict, retrieved: list[dict]) -> dict:
    llm = svc.require_llm()
    if not analysis["findings"]:
        return {"policy_draft": [], "technical_fixes": []}

    findings = "\n".join(
        f"- [{f['severity']}/{f['issue_type']}] {f['issue']}: {f['explanation']}" for f in analysis["findings"]
    )
    prompt = (
        f"Company: {company['company_name']} ({company['industry']}).\n"
        f"Regulatory change: {watcher['change_summary']}\n\n"
        f"Compliance findings:\n{findings}\n\n"
        f"=== CURRENT SOP EXCERPTS ===\n{_format_sop_excerpts(retrieved)}\n\n"
        "1. policy_draft: rewrite each affected SOP clause so it fully complies. Keep the original section "
        "numbering (e.g. 'Section 6.1: ...'), use formal SOP language, and include concrete deadlines and roles.\n"
        "2. technical_fixes: concrete operational and system changes needed (calendar reminders, ERP/portal "
        "settings, role assignments, approval workflows, training). One actionable item per entry."
    )
    out: GeneratorLLMOutput = llm.generate_json(prompt, GeneratorLLMOutput, SYSTEM_PROMPT)
    return {"policy_draft": _clean_list(out.policy_draft), "technical_fixes": _clean_list(out.technical_fixes)}


# ---------------------------------------------------------------------------
# Agent 5 - Critic / Verifier (no LLM, verification engine in app.verification)
# ---------------------------------------------------------------------------


def run_critic(
    svc: Services,
    document: dict,
    analysis: dict,
    pair: RegulationPair | None = None,
    regulation_id: str | None = None,
) -> list[dict]:
    if pair is None:
        pair = load_regulation_pair_by_id(svc.db, regulation_id, svc.settings.regulation_dir)
    sop_sources = [SourceChunk(document["filename"], c.section, c.text) for c in chunk_text(document["text"])]
    reg_sources = [SourceChunk(pair.after_title, c.section, c.text) for c in chunk_text(pair.after_text)] + [
        SourceChunk(pair.before_title, c.section, c.text) for c in chunk_text(pair.before_text)
    ]
    threshold = svc.settings.review_threshold
    is_ocr = (document.get("extraction_method") or "text") != "text"
    doc_ocr_confidence = document.get("ocr_confidence") if is_ocr else None
    ocr_method = document.get("extraction_method") if is_ocr else None

    verified: list[dict] = []
    for f in analysis["findings"]:
        claimed = f["citation_source"]
        candidates = sop_sources if claimed == "sop" else reg_sources if claimed == "regulation" else []
        confidence, chunk, verbatim = verify_citation(f["citation_text_snippet"], candidates or sop_sources + reg_sources)
        # If the quote doesn't match its claimed source, check whether it exists anywhere else.
        if confidence < threshold and candidates:
            alt = verify_citation(f["citation_text_snippet"], sop_sources + reg_sources)
            if alt[0] > confidence:
                confidence, chunk, verbatim = alt

        ok = confidence >= threshold and chunk is not None
        is_citation_ocr = is_ocr and (chunk is not None and chunk.source == document.get("filename"))
        if is_citation_ocr and doc_ocr_confidence and doc_ocr_confidence < 0.85:
            ok = False

        verified.append(
            {
                "id": f["id"],
                "issue": f["issue"],
                "issue_type": f["issue_type"],
                "severity": f["severity"],
                "explanation": f["explanation"],
                "citation": {
                    "source": chunk.source if ok else (chunk.source if chunk else "Unverified"),
                    "section": chunk.section if ok else f["citation_section"] or "Unknown",
                    "text_snippet": verbatim if ok else f["citation_text_snippet"],
                    "is_ocr": is_citation_ocr,
                    "ocr_method": ocr_method if is_citation_ocr else None,
                },
                "confidence": confidence,
                "flagged_for_review": not ok,
                "is_ocr": is_citation_ocr,
            }
        )
    return verified

