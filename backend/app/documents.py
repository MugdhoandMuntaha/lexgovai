"""Text extraction (PDF/TXT) and section-aware chunking shared by SOPs and regulations."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from .ports import OcrEngine

MAX_CHUNK_CHARS = 1200
DEFAULT_MIN_CHARS_PER_PAGE = 50
DEFAULT_MAX_OCR_PAGES = 20

_KEYWORD_HEADING = re.compile(r"^(section|clause|article|part|chapter|schedule|annex)\s+[\w.\-]+", re.IGNORECASE)
_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")


class DocumentParseError(ValueError):
    pass


@dataclass(frozen=True)
class Chunk:
    index: int
    section: str
    text: str


def extract_document_text(
    filename: str,
    content: bytes,
    ocr_engine: OcrEngine | None = None,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
    max_ocr_pages: int = DEFAULT_MAX_OCR_PAGES,
) -> tuple[str, str, float | None, str | None]:
    """Extracts text from PDF/TXT documents, automatically routing scanned/image PDFs to OCR.

    Returns:
        (text, extraction_method, ocr_confidence, ocr_notes)
    """
    name = filename.lower()
    if name.endswith(".txt") or name.endswith(".md"):
        text = content.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            raise DocumentParseError("Text file is empty.")
        return text, "text", 1.0, None

    if not name.endswith(".pdf"):
        raise DocumentParseError("Unsupported file type. Upload a .pdf or .txt file.")

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        num_pages = len(reader.pages)
        digital_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        digital_text = digital_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    except Exception as exc:
        raise DocumentParseError(f"Could not read PDF: {exc}") from exc

    # If digital text exceeds min characters per page, use native digital extraction
    threshold = min_chars_per_page * max(1, num_pages)
    if len(digital_text) >= threshold:
        return digital_text, "text", 1.0, None

    # Little or no text extracted -> route through OCR engine
    if ocr_engine is None or not ocr_engine.is_available():
        if digital_text:
            return digital_text, "text", 0.50, f"Sparse digital text ({len(digital_text)} chars across {num_pages} pages). OCR unavailable."
        raise DocumentParseError("Scanned or image-only PDF detected, but OCR engine is not configured.")

    ocr_text, method, confidence, notes = ocr_engine.extract_text_from_pdf(content, max_pages=max_ocr_pages)
    ocr_text = ocr_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not ocr_text:
        if digital_text:
            return digital_text, "text", 0.30, "OCR returned empty text; falling back to sparse digital text."
        raise DocumentParseError("OCR failed to transcribe readable text from scanned PDF.")

    return ocr_text, method, confidence, notes


def extract_text(filename: str, content: bytes) -> str:
    """Backwards-compatible text extractor returning plain string."""
    text, _, _, _ = extract_document_text(filename, content)
    return text


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 100:
        return False
    if _KEYWORD_HEADING.match(stripped):
        return True
    # Numbered headings like "1. Filing Deadlines:" - short and not a full sentence.
    return bool(_NUMBERED_HEADING.match(stripped)) and (stripped.endswith(":") or not stripped.endswith("."))


def _clean_heading(line: str) -> str:
    return line.strip().rstrip(":").strip()


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (section_label, body) pairs. The heading line is kept inside the body for context."""
    sections: list[tuple[str, list[str]]] = []
    current_label = "Preamble"
    current_lines: list[str] = []

    for line in text.split("\n"):
        if _is_heading(line):
            if any(l.strip() for l in current_lines):
                sections.append((current_label, current_lines))
            current_label = _clean_heading(line)
            current_lines = [line.strip()]
        else:
            current_lines.append(line.rstrip())

    if any(l.strip() for l in current_lines):
        sections.append((current_label, current_lines))

    return [(label, "\n".join(lines).strip()) for label, lines in sections]


def _split_long(body: str) -> list[str]:
    if len(body) <= MAX_CHUNK_CHARS:
        return [body]
    parts: list[str] = []
    buffer = ""
    for paragraph in re.split(r"\n\s*\n", body):
        if buffer and len(buffer) + len(paragraph) + 2 > MAX_CHUNK_CHARS:
            parts.append(buffer)
            buffer = paragraph
        else:
            buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        # A single paragraph that is still too long gets hard-split on sentence boundaries.
        while len(buffer) > MAX_CHUNK_CHARS:
            cut = buffer.rfind(". ", 0, MAX_CHUNK_CHARS)
            cut = cut + 1 if cut > MAX_CHUNK_CHARS // 2 else MAX_CHUNK_CHARS
            parts.append(buffer[:cut].strip())
            buffer = buffer[cut:].strip()
    if buffer:
        parts.append(buffer)
    return parts


def chunk_text(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for label, body in split_sections(text):
        for part in _split_long(body):
            chunks.append(Chunk(index=len(chunks), section=label, text=part))
    return chunks

