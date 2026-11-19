"""End-to-end Legal Library Ingestion Pipeline orchestrating extraction, structuring, classification, verification, and indexing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.db import Database
from app.ports import LLMClient, OcrEngine
from app.vectorstore import VectorStore

from .change import ChangeAgent
from .classifier import ClassifierAgent
from .extraction import ExtractionAgent, ExtractionResult
from .structuring import StructuringAgent
from .verifier import VerifierAgent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestLawResult:
    law_id: str
    version_id: str
    publish_state: str  # 'published', 'pending_review'
    is_new: bool
    is_changed: bool
    is_unchanged: bool
    summary_verified: bool
    review_reason: str | None = None


class LegalIngestionPipeline:
    """Orchestrates the multi-agent legal ingestion pipeline."""

    def __init__(
        self,
        db: Database,
        vectorstore: VectorStore | None = None,
        llm: LLMClient | None = None,
        ocr_engine: OcrEngine | None = None,
    ):
        self.db = db
        self.vectorstore = vectorstore
        self.llm = llm
        self.extraction_agent = ExtractionAgent(ocr_engine)
        self.structuring_agent = StructuringAgent(llm)
        self.classifier_agent = ClassifierAgent(llm)
        self.verifier_agent = VerifierAgent()
        self.change_agent = ChangeAgent(db)

    def ingest_document(
        self,
        filename: str,
        content: bytes,
        source_url: str | None = None,
        existing_law_id: str | None = None,
    ) -> IngestLawResult:
        # Step 1: Extraction
        extract_res = self.extraction_agent.extract(filename, content)
        if extract_res.is_empty:
            raise ValueError("Document yielded no extractable text.")

        content_hash = extract_res.content_hash

        # Check if already exists by existing_law_id or hash
        is_new = False
        is_changed = False
        is_unchanged = False
        target_law = self.db.get_law(existing_law_id) if existing_law_id else None

        if target_law:
            cur_ver = self.db.get_current_law_version(target_law["id"])
            if cur_ver and cur_ver["version_hash"] == content_hash:
                return IngestLawResult(
                    law_id=target_law["id"],
                    version_id=cur_ver["id"],
                    publish_state=target_law["publish_state"],
                    is_new=False,
                    is_changed=False,
                    is_unchanged=True,
                    summary_verified=bool(target_law["summary_verified"]),
                )
            is_changed = True
        else:
            is_new = True

        # Step 2: Structuring
        struct_res = self.structuring_agent.structure(extract_res.text, filename_hint=filename)
        struct_data = struct_res.data

        # Step 3: Classification
        class_res = self.classifier_agent.classify(
            title=struct_data.canonical_title_en,
            text=extract_res.text,
        )

        # Step 4: Verification (RapidFuzz zero LLM)
        verif_res = self.verifier_agent.verify_summary(
            summary_ai=class_res.summary_ai,
            source_text=extract_res.text,
        )

        # Step 5: Publish Policy
        # Auto-publish only if extraction is high quality, structuring is verified, and summary is verified
        auto_publish = True
        review_reasons: list[str] = []

        if extract_res.extraction_method != "text" and (extract_res.ocr_quality or 0.0) < 0.85:
            auto_publish = False
            review_reasons.append(f"Low OCR confidence ({extract_res.ocr_quality:.2f})")

        if not struct_res.is_verified:
            auto_publish = False
            review_reasons.append(struct_res.verification_notes or "Structuring verification failed")

        if not verif_res.is_verified:
            auto_publish = False
            review_reasons.append(verif_res.notes or "AI summary verification flagged")

        publish_state = "published" if auto_publish else "pending_review"

        # Step 6: Database Persistence
        if not target_law:
            law_record = self.db.create_law(
                canonical_title_en=struct_data.canonical_title_en,
                canonical_title_bn=struct_data.canonical_title_bn,
                act_number=struct_data.act_number,
                year=struct_data.year,
                law_type=struct_data.law_type,
                issuing_body=struct_data.issuing_body,
                language_available=struct_data.language_detected,
                status=class_res.status,
                status_confidence=class_res.status_confidence,
                domain_tags=class_res.domain_tags,
                summary_ai=class_res.summary_ai,
                summary_verified=verif_res.is_verified,
                publish_state=publish_state,
            )
            law_id = law_record["id"]
        else:
            law_id = target_law["id"]
            self.db.update_law(
                law_id,
                status=class_res.status,
                summary_ai=class_res.summary_ai,
                summary_verified=verif_res.is_verified,
                publish_state=publish_state,
            )

        # Create version
        version = self.db.create_law_version(
            law_id=law_id,
            version_hash=content_hash,
            source_url=source_url,
            extraction_method=extract_res.extraction_method,
            ocr_quality=extract_res.ocr_quality,
            is_current=True,
        )
        version_id = version["id"]

        # Bulk save sections and index into FTS5
        sections_to_save = [
            {
                "level": s.level,
                "number_label": s.number_label,
                "heading": s.heading,
                "text": s.text,
                "order_index": idx,
            }
            for idx, s in enumerate(struct_data.sections)
        ]
        saved_sections = self.db.create_law_sections_bulk(version_id, law_id, sections_to_save)

        # Index into ChromaDB if vectorstore and LLM client exist
        if self.vectorstore and self.llm and saved_sections:
            try:
                sec_texts = [f"{s.get('number_label', '')} {s.get('heading', '')}\n{s.get('text', '')}".strip() for s in saved_sections]
                embeddings = [self.llm.embed(t) for t in sec_texts]
                self.vectorstore.add_law_sections(
                    law_id=law_id,
                    version_id=version_id,
                    sections=saved_sections,
                    embeddings=embeddings,
                    language=struct_data.language_detected,
                    status=class_res.status,
                )
            except Exception as e:
                logger.warning(f"Failed to vector-index law sections into ChromaDB: {e}")

        # Enqueue in review queue if pending review
        final_review_reason = None
        if publish_state == "pending_review":
            final_review_reason = "; ".join(review_reasons)
            self.db.enqueue_law_review(law_id, reason=final_review_reason)

        # Handle amendments and notifications if an existing law changed
        if is_changed:
            self.change_agent.process_change(law_id, version_id)

        # Record relations
        for rel in class_res.relations:
            # Try to find target law by title
            matched_laws = self.db.list_laws(q=rel.target_law_title, limit=1)
            if matched_laws:
                self.db.create_law_relation(law_id, matched_laws[0]["id"], rel.relation)

        return IngestLawResult(
            law_id=law_id,
            version_id=version_id,
            publish_state=publish_state,
            is_new=is_new,
            is_changed=is_changed,
            is_unchanged=False,
            summary_verified=verif_res.is_verified,
            review_reason=final_review_reason,
        )

