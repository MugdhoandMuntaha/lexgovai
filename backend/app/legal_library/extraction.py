"""ExtractionAgent: Fetches candidates, uses pypdf when good, otherwise OCR, hashes content."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.documents import extract_document_text
from app.ports import OcrEngine


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    content_hash: str
    extraction_method: str  # 'text', 'ocr_gemini', 'ocr_tesseract'
    ocr_quality: float | None = None
    notes: str | None = None
    is_empty: bool = False


class ExtractionAgent:
    """Extracts raw authoritative text from digital or scanned legal documents."""

    def __init__(self, ocr_engine: OcrEngine | None = None):
        self.ocr_engine = ocr_engine

    def extract(self, filename: str, content: bytes) -> ExtractionResult:
        text, method, confidence, notes = extract_document_text(
            filename=filename,
            content=content,
            ocr_engine=self.ocr_engine,
        )
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return ExtractionResult(
            text=text,
            content_hash=content_hash,
            extraction_method=method,
            ocr_quality=confidence,
            notes=notes,
            is_empty=len(text.strip()) == 0,
        )

