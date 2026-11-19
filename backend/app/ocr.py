"""Optical Character Recognition (OCR) engine for scanned statutory gazettes and image-only SOPs.

Supports Gemini Vision OCR as primary engine, optional local Tesseract fallback,
and deterministic FakeOcr for offline tests.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
from typing import Any

from .llm import LLMClient
from .ports import OcrEngine

logger = logging.getLogger(__name__)

SYSTEM_OCR_PROMPT = (
    "You are an expert, meticulous OCR transcriber for legal gazettes and corporate compliance SOPs in Bangladesh. "
    "Transcribe the provided document image verbatim character-for-character. "
    "Preserve all section headers, clause numbers, bullet points, and Bengali script. "
    "Never summarize, paraphrase, omit, or invent text. "
    "Output only the transcribed document text."
)


def rasterize_pdf_to_images(pdf_bytes: bytes, max_pages: int = 20) -> list[bytes]:
    """Renders PDF pages into PNG image bytes using pypdfium2."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise RuntimeError("pypdfium2 is required for PDF rasterization.")

    pdf = pdfium.PdfDocument(pdf_bytes)
    total_pages = len(pdf)
    num_pages = min(total_pages, max_pages)

    image_bytes_list: list[bytes] = []
    for i in range(num_pages):
        page = pdf[i]
        # Render at 2.0x scale (144 dpi) for high-fidelity OCR transcription
        image = page.render(scale=2.0).to_pil()
        bio = io.BytesIO()
        image.save(bio, format="PNG")
        image_bytes_list.append(bio.getvalue())

    return image_bytes_list


class GeminiVisionOcr:
    """Primary OCR engine using Gemini Vision models with structured multimodal input."""

    def __init__(self, llm: LLMClient | None):
        self.llm = llm

    def is_available(self) -> bool:
        return self.llm is not None

    def extract_text_from_pdf(
        self, pdf_bytes: bytes, max_pages: int = 20
    ) -> tuple[str, str, float, str]:
        if not self.llm:
            raise RuntimeError("GeminiVisionOcr requires a configured LLM client.")

        images = rasterize_pdf_to_images(pdf_bytes, max_pages=max_pages)
        if not images:
            return "", "ocr_gemini", 0.0, "Empty document or failed to rasterize pages."

        page_texts: list[str] = []
        for idx, img_bytes in enumerate(images, start=1):
            prompt = f"Transcribe page {idx} verbatim. Preserve all clause headers, numbers, and Bengali text."
            page_text = self.llm.generate_text_with_image(
                prompt=prompt,
                image_bytes=img_bytes,
                mime_type="image/png",
                system=SYSTEM_OCR_PROMPT,
            )
            if page_text:
                page_texts.append(page_text.strip())

        full_text = "\n\n".join(page_texts)
        confidence = 0.90 if len(full_text) > 100 else 0.70
        notes = f"Transcribed {len(page_texts)} pages via Gemini Vision OCR."
        return full_text, "ocr_gemini", confidence, notes


class TesseractOcr:
    """Optional local fallback using the Tesseract OCR CLI binary."""

    def __init__(self, tesseract_cmd: str | None = None):
        self.cmd = tesseract_cmd or shutil.which("tesseract")

    def is_available(self) -> bool:
        return bool(self.cmd and shutil.which(self.cmd))

    def extract_text_from_pdf(
        self, pdf_bytes: bytes, max_pages: int = 20
    ) -> tuple[str, str, float, str]:
        if not self.is_available():
            raise RuntimeError("Tesseract binary is not installed or available on PATH.")

        images = rasterize_pdf_to_images(pdf_bytes, max_pages=max_pages)
        if not images:
            return "", "ocr_tesseract", 0.0, "Empty document or failed to rasterize pages."

        page_texts: list[str] = []
        for img_bytes in images:
            try:
                # Check if Bengali + English are available; otherwise fallback to eng
                proc = subprocess.run(
                    [self.cmd, "stdin", "stdout", "-l", "ben+eng"],
                    input=img_bytes,
                    capture_output=True,
                    check=True,
                )
                text = proc.stdout.decode("utf-8", errors="replace").strip()
            except subprocess.CalledProcessError:
                # Fallback to English only if ben data is not installed
                proc = subprocess.run(
                    [self.cmd, "stdin", "stdout", "-l", "eng"],
                    input=img_bytes,
                    capture_output=True,
                    check=True,
                )
                text = proc.stdout.decode("utf-8", errors="replace").strip()

            if text:
                page_texts.append(text)

        full_text = "\n\n".join(page_texts)
        confidence = 0.80 if len(full_text) > 100 else 0.50
        notes = f"Transcribed {len(page_texts)} pages via Tesseract OCR."
        return full_text, "ocr_tesseract", confidence, notes


class FakeOcr:
    """Deterministic OCR engine for offline tests."""

    def __init__(self, canned_text: str | None = None, confidence: float = 0.92):
        self.canned_text = (
            canned_text
            or "Section 1.0: Operating Hours & Overtime Policy.\nAll commercial vehicles must report departure within 15 days."
        )
        self.confidence = confidence

    def is_available(self) -> bool:
        return True

    def extract_text_from_pdf(
        self, pdf_bytes: bytes, max_pages: int = 20
    ) -> tuple[str, str, float, str]:
        return self.canned_text, "ocr_fake", self.confidence, "Transcribed via FakeOcr fixture."


class CompositeOcrEngine:
    """Router that dispatches to Gemini Vision first, then Tesseract, or raises."""

    def __init__(self, primary: OcrEngine, fallback: OcrEngine | None = None):
        self.primary = primary
        self.fallback = fallback

    def is_available(self) -> bool:
        return self.primary.is_available() or (self.fallback is not None and self.fallback.is_available())

    def extract_text_from_pdf(
        self, pdf_bytes: bytes, max_pages: int = 20
    ) -> tuple[str, str, float, str]:
        if self.primary.is_available():
            try:
                return self.primary.extract_text_from_pdf(pdf_bytes, max_pages=max_pages)
            except Exception as e:
                logger.warning(f"Primary OCR engine failed: {e}. Attempting fallback...")
                if self.fallback and self.fallback.is_available():
                    return self.fallback.extract_text_from_pdf(pdf_bytes, max_pages=max_pages)
                raise
        elif self.fallback and self.fallback.is_available():
            return self.fallback.extract_text_from_pdf(pdf_bytes, max_pages=max_pages)

        raise RuntimeError("No OCR engine is currently available.")

