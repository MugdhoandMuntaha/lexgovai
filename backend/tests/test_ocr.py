"""Tests for Part B: OCR Engine, scanned PDF detection, metering, and zero hallucination rule."""

from __future__ import annotations

import io
from pathlib import Path
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.documents import extract_document_text, DocumentParseError
from app.main import create_app
from app.ocr import FakeOcr, CompositeOcrEngine
from tests.conftest import FakeLLM, make_settings, mint_test_jwt


def make_image_only_pdf() -> bytes:
    """Generates a valid single-page image-only PDF with zero digital text."""
    img = Image.new("RGB", (200, 200), color=(240, 240, 240))
    bio = io.BytesIO()
    img.save(bio, format="PDF")
    return bio.getvalue()


def test_scanned_pdf_auto_routes_to_ocr():
    """Confirms that an image-only PDF with zero text routes through the OCR engine."""
    pdf_bytes = make_image_only_pdf()
    fake_ocr = FakeOcr(
        canned_text="Section 1.1: Mandatory Return Submission.\nAll registered taxpayers must submit returns within 15 days.",
        confidence=0.91,
    )

    text, method, confidence, notes = extract_document_text(
        filename="scanned_gazette.pdf",
        content=pdf_bytes,
        ocr_engine=fake_ocr,
    )

    assert "Section 1.1" in text
    assert method == "ocr_fake"
    assert confidence == 0.91
    assert notes is not None


def test_scanned_pdf_fails_without_ocr_engine():
    """Confirms that an image-only PDF raises DocumentParseError if no OCR engine is available."""
    pdf_bytes = make_image_only_pdf()

    with pytest.raises(DocumentParseError) as exc_info:
        extract_document_text(
            filename="scanned_gazette.pdf",
            content=pdf_bytes,
            ocr_engine=None,
        )
    assert "OCR engine is not configured" in str(exc_info.value)


def test_digital_pdf_bypasses_ocr():
    """Confirms that a native digital PDF with text does NOT trigger OCR."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # Text file or digital text simulation
    fake_ocr = FakeOcr(canned_text="OCR Should Not Be Called")
    content = b"Section 1.0: Operating Rules\nThis is a plain digital text file that contains more than enough characters to bypass OCR."

    text, method, confidence, notes = extract_document_text(
        filename="digital_sop.txt",
        content=content,
        ocr_engine=fake_ocr,
    )

    assert method == "text"
    assert confidence == 1.0
    assert "Operating Rules" in text


def test_ocr_upload_plan_entitlement_and_metering(tmp_path: Path):
    """Verifies that uploading a scanned PDF gates on document_ocr capability and meters ocr_pages."""
    pdf_bytes = make_image_only_pdf()
    fake_ocr = FakeOcr(
        canned_text="Section 1.0: Warehouse Operations\nDischarge cargo within 15 calendar days."
    )
    settings = make_settings(tmp_path)
    app = create_app(settings, llm=FakeLLM(), ocr=fake_ocr)

    with TestClient(app) as client:
        # 1. User on Free plan (no document_ocr entitlement)
        free_jwt = mint_test_jwt(sub="user-free-ocr", email="free_ocr@example.com")
        headers = {"Authorization": f"Bearer {free_jwt}"}

        # Create company profile
        cp_res = client.post(
            "/api/company-profile",
            json={"company_name": "Free Co", "industry": "logistics", "country": "bangladesh"},
            headers=headers,
        )
        assert cp_res.status_code == 200
        cp_id = cp_res.json()["id"]

        # Free tier upload has sop_upload='off', so upgrade to Starter where sop_upload='on' and document_ocr='basic'
        ws = client.get("/api/me", headers=headers).json()["workspace"]
        app.state.services.subscriptions.change_plan(ws["id"], "free")

        # Attempt upload on Free plan -> 403 FEATURE_NOT_IN_PLAN for sop_upload
        res_free = client.post(
            "/api/documents/upload",
            data={"company_profile_id": cp_id},
            files={"file": ("scanned_sop.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert res_free.status_code == 403

        # Upgrade to Starter plan (has document_ocr=basic, ocr_pages=20 limit)
        app.state.services.subscriptions.change_plan(ws["id"], "starter")

        # Upload on Starter succeeds with OCR extraction
        res_starter = client.post(
            "/api/documents/upload",
            data={"company_profile_id": cp_id},
            files={"file": ("scanned_sop.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert res_starter.status_code == 200
        data = res_starter.json()
        assert data["extraction_method"] == "ocr_fake"
        assert data["ocr_confidence"] is not None

        # Verify usage meter was incremented for ocr_pages
        used, limit, _ = app.state.services.usage.get_metric_usage(ws["id"], "ocr_pages")
        assert used >= 1
        assert limit == 20

    app.state.services.db.close()

