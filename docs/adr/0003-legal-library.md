# ADR 0003: Bangladesh Legal Library Architecture & Autonomous Ingestion Engine

**Status:** Accepted  
**Date:** 2026-11-13  
**Context:** Bangladesh Statutory Law Library, Multi-Agent Ingestion Pipeline, Zero-Hallucination Critic, Hybrid RRF Search

---

## 1. Context & Objectives

LexGOV AI provides automated SOP compliance analysis against National Board of Revenue (NBR) regulatory changes. However, regulatory compliance across Bangladesh enterprises requires access to a broader corpus of statutory enactments, gazette notices, SROs (Statutory Regulatory Orders), ordinances, and circulars issued by multiple government bodies (Bangladesh Government Press, Ministry of Law, NBR, Bangladesh Bank, BSEC, RJSC).

This ADR establishes the **Bangladesh Legal Library**:
1. An autonomous ingestion engine capable of discovering, fetching, extracting (pypdf + Tesseract OCR for Bengali/English scanned gazettes), structuring, classifying, and diffing legal texts.
2. A deterministic RapidFuzz-backed Critic Verifier ensuring zero AI hallucination in legal summaries and citations.
3. A Hybrid Search engine (SQLite FTS5 full-text + ChromaDB vector embeddings with Reciprocal Rank Fusion).
4. Strict plan entitlement gating (`legal_library`: `basic`, `standard`, `full`).
5. A comprehensive Next.js 16 (React 19 Server Components) user and admin interface.

---

## 2. Core Architecture Principles

1. **Authoritative Source Text is Primary:** Official gazette and government portal texts are the sole authoritative baseline. All AI outputs (summaries, domain tags, status guesses) are explicitly labeled AI-generated and verified by the RapidFuzz Critic.
2. **Zero-Completeness Claim:** The platform never claims complete legal coverage. All UI views and API endpoints display exact coverage metrics (counts of published laws, monitored sources, and last run dates).
3. **Strict Vector Collection Isolation:** The `law_sections` ChromaDB collection is completely isolated from customer `sop_chunks`. Customer document embeddings and statutory laws are never co-mingled.
4. **Quota Isolation:** Autonomous library ingestion and scheduled crawling run at the platform level and do not consume customer workspace analysis quotas.
5. **Auto-Publish Policy with Critic Fail-Safe:** An enactment is auto-published only when:
   - Extraction is clean (digital text or OCR confidence $\ge 0.85$).
   - Structuring passes length and ratio sanity checks.
   - RapidFuzz Critic verifies the AI executive summary against raw text ($\text{score} \ge 0.75$).
   Any defect routes the enactment into `law_review_queue` as `pending_review` for human admin review.
6. **Plan Capability Gating:** Governed strictly by `app/plans.py` via `legal_library`:
   - `basic` (Free): Browse catalog, view details and statutory sections, basic FTS search.
   - `standard` (Starter / Growth): Watchlist & change notifications, version diffing, personalized company sector recommendations.
   - `full` (Professional): Grounded "Ask about this law" Q&A and "Analyze SOP against law" multi-agent benchmarking.

---

## 3. Data Model (Schema Version 5)

The database schema is upgraded to `schema_version = 5` with 8 relational tables and 1 virtual FTS5 table:

```sql
-- Configured government portals (BGPress, MinLaw, NBR, Bangladesh Bank, etc.)
CREATE TABLE law_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    source_type TEXT NOT NULL, -- html_crawl, pdf_feed, gazette_poll
    enabled INTEGER NOT NULL DEFAULT 0,
    crawl_config TEXT NOT NULL DEFAULT '{}',
    rate_limit INTEGER NOT NULL DEFAULT 3,
    last_run_at TEXT,
    last_status TEXT
);

-- Canonical laws and enactments
CREATE TABLE laws (
    id TEXT PRIMARY KEY,
    canonical_title_en TEXT NOT NULL,
    canonical_title_bn TEXT,
    act_number TEXT,
    year INTEGER,
    law_type TEXT NOT NULL, -- act, ordinance, sro, rule, circular, order, gazette_notice
    issuing_body TEXT NOT NULL,
    language_available TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'in_force', -- in_force, amended, repealed, unknown
    status_confidence REAL NOT NULL DEFAULT 1.0,
    domain_tags TEXT NOT NULL DEFAULT '[]', -- JSON array: tax_vat, banking_finance, labor, customs, etc.
    summary_ai TEXT,
    summary_verified INTEGER NOT NULL DEFAULT 0,
    publish_state TEXT NOT NULL DEFAULT 'draft', -- draft, pending_review, published, rejected
    created_at TEXT NOT NULL
);

-- Versioned statutory editions
CREATE TABLE law_versions (
    id TEXT PRIMARY KEY,
    law_id TEXT NOT NULL,
    version_hash TEXT NOT NULL,
    source_url TEXT,
    fetched_at TEXT NOT NULL,
    extraction_method TEXT NOT NULL, -- digital_text, ocr_tesseract, hybrid
    ocr_quality REAL,
    raw_text_path TEXT,
    is_current INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

-- Structured statutory sections and clauses
CREATE TABLE law_sections (
    id TEXT PRIMARY KEY,
    law_version_id TEXT NOT NULL,
    parent_id TEXT,
    level TEXT NOT NULL, -- chapter, section, subsection, schedule
    number_label TEXT NOT NULL, -- e.g. "Section 15", "ধারা ১৫"
    heading TEXT,
    text TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    FOREIGN KEY (law_version_id) REFERENCES law_versions(id) ON DELETE CASCADE
);

-- SQLite FTS5 Full-Text Search index
CREATE VIRTUAL TABLE law_sections_fts USING fts5(
    section_id UNINDEXED,
    law_id UNINDEXED,
    version_id UNINDEXED,
    heading,
    text,
    number_label
);

-- Inter-law statutory relationships (amends, repeals, implements, refers_to)
CREATE TABLE law_relations (
    id TEXT PRIMARY KEY,
    from_law_id TEXT NOT NULL,
    to_law_id TEXT NOT NULL,
    relation TEXT NOT NULL, -- amends, repeals, supersedes, refers_to, implements
    FOREIGN KEY (from_law_id) REFERENCES laws(id) ON DELETE CASCADE,
    FOREIGN KEY (to_law_id) REFERENCES laws(id) ON DELETE CASCADE
);

-- Ingestion run audit telemetry
CREATE TABLE law_ingest_runs (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    discovered INTEGER NOT NULL DEFAULT 0,
    new INTEGER NOT NULL DEFAULT 0,
    changed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    cost_estimate REAL NOT NULL DEFAULT 0.0,
    notes TEXT,
    FOREIGN KEY (source_id) REFERENCES law_sources(id)
);

-- User and workspace watchlists
CREATE TABLE law_watchlist (
    workspace_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    law_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id, law_id),
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

-- Human review queue
CREATE TABLE law_review_queue (
    id TEXT PRIMARY KEY,
    law_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_by TEXT,
    resolution TEXT,
    resolved_at TEXT,
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);
```

---

## 4. Multi-Agent Autonomous Ingestion Architecture

Ingestion is organized in `backend/app/legal_library/` as discrete, testable agent components:

1. **ExtractionAgent (`extraction.py`):** Reuses the dual-path document extractor (`pypdf` for digital text, `tesseract` for scanned Bengali/English image pages), hashes raw text with SHA-256 for cryptographic deduplication.
2. **StructuringAgent (`structuring.py`):** Decomposes monolithic enactment text into hierarchical clauses (`chapter`, `section`, `subsection`, `schedule`). Uses Pydantic structured LLM generation with fallback regex heuristics; validates that extracted section count and length ratio match source text.
3. **ClassifierAgent (`classifier.py`):** Tags enactments using a controlled domain vocabulary (`tax_vat`, `banking_finance`, `labor`, `customs`, `corporate`, `data_privacy`, `export_import`, `securities`), detects explicit inter-statute relations (`amends`, `repeals`, `refers_to`), and crafts an executive summary.
4. **VerifierAgent (`verifier.py`):** Deterministic critic (zero LLM) validating sentence claims in AI summaries and Q&A citations using RapidFuzz string similarity (`max(token_set_ratio, partial_ratio) >= 75`).
5. **ChangeAgent (`change.py`):** Performs section-by-section diffing across law versions (detecting added, modified, and removed clauses) and dispatches in-app notifications to watchers.
6. **DiscoveryAgent (`discovery.py`):** Drives the crawler through configured `law_sources` with polite rate limits, depth caps, domain whitelists, and SSRF guards.
7. **LegalIngestionPipeline (`pipeline.py`):** Orchestrates the complete end-to-end flow and applies the auto-publish policy.

---

## 5. Hybrid Search Architecture

Statutory query resolution uses **Reciprocal Rank Fusion (RRF)**:
$$\text{RRF Score}(d) = \sum_{m \in \{\text{FTS5}, \text{Vector}\}} \frac{1}{60 + \text{Rank}_m(d)} + \text{Exact Section Boost}$$

- **FTS5:** Tokenized prefix match with natural language stopword fallback.
- **ChromaDB:** Cosine similarity over multilingual text embeddings.
- **Exact Section Number Boost:** Direct $+0.5$ score boost for exact section queries (e.g. `"Section 15"`).

---

## 6. Verification and Status

All 82 backend unit/integration tests passing (including 11/11 dedicated API tests and 5/5 multi-agent pipeline tests). Next.js 16 frontend fully built with zero lint and compile errors.

