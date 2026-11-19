from __future__ import annotations

import hashlib
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import login_limiter  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.schemas import (  # noqa: E402
    AnalyzerLLMOutput,
    FindingLLMOutput,
    GeneratorLLMOutput,
    StarterGuideLLMOutput,
    StarterPolicyLLMContent,
    WatcherLLMOutput,
)

FABRICATED_QUOTE = "Quarterly VAT audits are outsourced to an external chartered accountant firm."


class FakeLLM:
    """Deterministic stand-in for Gemini: hashed bag-of-words embeddings + canned structured outputs."""

    model_name = "fake-model"

    def __init__(self):
        self.calls: dict[str, int] = {}

    def embed(self, texts, task):
        self.calls["embed"] = self.calls.get("embed", 0) + 1
        vectors = []
        for text in texts:
            vec = [0.0] * 64
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors

    def generate_json(self, prompt, schema, system):
        self.calls[schema.__name__] = self.calls.get(schema.__name__, 0) + 1
        if schema is WatcherLLMOutput:
            return WatcherLLMOutput(
                title="NBR VAT SRO Clause 4.2",
                change_summary="Filing deadline cut from 30 to 15 days; a named VAT Filing Officer is now mandatory.",
                change_type="Amendment",
                changed_clauses=["Deadline: 30 days -> 15 days", "Designated officer now mandatory"],
                obligations=[
                    "File Mushak-9.1 within 15 calendar days after the tax period",
                    "Designate a named certified VAT Filing Officer",
                ],
            )
        if schema is AnalyzerLLMOutput:
            return AnalyzerLLMOutput(
                impact_score=140,  # out of range on purpose: must be clamped
                urgency="CRITICAL",
                findings=[
                    FindingLLMOutput(
                        issue="Outdated 30-day VAT filing deadline",
                        issue_type="outdated reference",
                        severity="High",
                        explanation="SOP still allows 30 days.",
                        citation_source="sop",
                        citation_section="6.1",
                        # Slightly reformatted quote (curly quotes / spacing) must still verify.
                        citation_text_snippet="submits monthly VAT returns to the NBR  within 30 calendar days",
                    ),
                    FindingLLMOutput(
                        issue="No designated VAT Filing Officer",
                        issue_type="gap",
                        severity="high",
                        explanation="Regulation requires a named officer.",
                        citation_source="regulation",
                        citation_section="2. Mandatory Designated Officer",
                        citation_text_snippet="formally designate a named, certified VAT Filing Officer",
                    ),
                    FindingLLMOutput(
                        issue="Hallucinated audit clause",
                        issue_type="conflict",
                        severity="weird",
                        explanation="This quote does not exist anywhere.",
                        citation_source="sop",
                        citation_section="Section 9",
                        citation_text_snippet=FABRICATED_QUOTE,
                    ),
                ],
            )
        if schema is GeneratorLLMOutput:
            return GeneratorLLMOutput(
                policy_draft=["Section 6.1: Returns are filed within 15 calendar days by the VAT Filing Officer.", " "],
                technical_fixes=["Add a day-10 reminder in the ERP calendar", "Appoint the VAT Filing Officer"],
            )
        if schema is StarterGuideLLMOutput:
            cat_ids = re.findall(r"Category ID: ([a-z_]+)", prompt)
            return StarterGuideLLMOutput(
                summary="AI-crafted executive summary of foundational policies for your business.",
                policies=[
                    StarterPolicyLLMContent(
                        category_id=cid,
                        covers=f"AI-generated coverage description for {cid}.",
                        include_points=[
                            f"Standard operational rule 1 for {cid}",
                            f"Standard operational rule 2 for {cid}",
                            f"Standard operational rule 3 for {cid}",
                        ],
                    )
                    for cid in cat_ids
                ],
            )
        from app.assistant import AssistantAnswerOutput, AssistantCitation
        from app.deadlines import DeadlineExtractionOutput, ExtractedDeadlineItem

        if schema is AssistantAnswerOutput:
            is_off_topic = "poem" in prompt.lower() or "joke" in prompt.lower()
            return AssistantAnswerOutput(
                is_in_scope=not is_off_topic,
                answer="Under NBR VAT SRO Clause 4.2, all registered companies must submit monthly returns within 15 calendar days.",
                citations=[
                    AssistantCitation(
                        source="NBR VAT SRO Clause 4.2",
                        section="Clause 4.2",
                        quote="within 15 calendar days",
                    )
                ],
            )
        if schema is DeadlineExtractionOutput:
            return DeadlineExtractionOutput(
                deadlines=[
                    ExtractedDeadlineItem(
                        title="Monthly Electronic Mushak-9.1 Return",
                        lead_days=15,
                        statutory_quote="within 15 calendar days",
                        recommended_date="2026-11-15",
                    )
                ]
            )
        if schema.__name__ == "AnswerOut":
            return schema(answer="Under Section 15 of the Act, VAT registered entities must maintain audited sales accounts and file returns within the statutory deadline.")
        if schema.__name__ == "StructuringOutput":
            from app.legal_library.structuring import StructuredSectionItem
            return schema(
                sections=[
                    StructuredSectionItem(
                        number_label="Section 1",
                        heading="Short Title and Commencement",
                        text="This Act may be called the Value Added Tax and Supplementary Duty Act, 2012.",
                        order_index=1,
                    ),
                    StructuredSectionItem(
                        number_label="Section 15",
                        heading="Imposition of Value Added Tax",
                        text="Value Added Tax shall be imposed and payable on taxable supply of goods and services.",
                        order_index=2,
                    ),
                ]
            )
        if schema.__name__ == "ClassifierOutput":
            from app.legal_library.classifier import ClassifiedRelationItem
            return schema(
                domain_tags=["tax_vat"],
                status_estimate="in_force",
                status_confidence=0.95,
                relations=[
                    ClassifiedRelationItem(
                        related_title="Value Added Tax Act, 1991",
                        relation="repeals",
                        year=1991,
                    )
                ],
                grounded_summary="This Act consolidates the law relating to value added tax and supplementary duty in Bangladesh.",
            )
        raise AssertionError(f"unexpected schema {schema}")


TEST_SUPABASE_URL = "https://test.supabase.co"
TEST_SUPABASE_JWT_SECRET = "super-secret-jwt-key-for-unit-tests-min-32-chars-long"


def mint_test_jwt(
    sub: str = "test-supabase-user-uuid-1234",
    email: str = "test_jwt_user@example.com",
    full_name: str = "JWT Test User",
    exp_delta: timedelta = timedelta(hours=1),
    aud: str = "authenticated",
    iss: str | None = f"{TEST_SUPABASE_URL}/auth/v1",
    secret: str = TEST_SUPABASE_JWT_SECRET,
    alg: str = "HS256",
) -> str:
    import jwt
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "aud": aud,
        "exp": int((now + exp_delta).timestamp()),
        "iat": int(now.timestamp()),
        "user_metadata": {"full_name": full_name},
    }
    if iss is not None:
        payload["iss"] = iss
    return jwt.encode(payload, secret, algorithm=alg)


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        gemini_api_key=None,
        storage_dir=tmp_path / "storage",
        review_threshold=0.75,
        supabase_url=TEST_SUPABASE_URL,
        supabase_jwt_secret=TEST_SUPABASE_JWT_SECRET,
    )


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    with login_limiter._lock:
        login_limiter._failures.clear()
        login_limiter._lockouts.clear()
    yield
    with login_limiter._lock:
        login_limiter._failures.clear()
        login_limiter._lockouts.clear()


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def unauthenticated_client(tmp_path, fake_llm):
    app = create_app(make_settings(tmp_path), llm=fake_llm)
    with TestClient(app) as c:
        yield c
    app.state.services.db.close()


@pytest.fixture
def client(tmp_path, fake_llm):
    app = create_app(make_settings(tmp_path), llm=fake_llm)
    with TestClient(app) as c:
        res = c.post(
            "/api/auth/signup",
            json={
                "email": "default_test_user@example.com",
                "password": "SecurePassword123!",
                "full_name": "Default Test User",
                "company_name": "Default Test Corp",
            },
        )
        assert res.status_code == 200, res.text
        ws_id = res.json()["workspace"]["id"]
        app.state.services.subscriptions.change_plan(ws_id, "professional")
        yield c
    app.state.services.db.close()


@pytest.fixture
def client_without_llm(tmp_path):
    app = create_app(make_settings(tmp_path), llm=None)
    with TestClient(app) as c:
        res = c.post(
            "/api/auth/signup",
            json={
                "email": "nollm_test_user@example.com",
                "password": "SecurePassword123!",
                "full_name": "No LLM User",
            },
        )
        assert res.status_code == 200, res.text
        ws_id = res.json()["workspace"]["id"]
        app.state.services.subscriptions.change_plan(ws_id, "professional")
        yield c
    app.state.services.db.close()


@pytest.fixture
def fake_crawler():
    from app.crawler import FakeCrawler

    return FakeCrawler()


