"""Application settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    data_dir: Path = BASE_DIR / "data"
    storage_dir: Path = BASE_DIR / "storage"
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000", "http://testserver"]
    )
    retrieval_top_k: int = 4
    # Findings whose citation matches its source text below this ratio get flagged for human review.
    review_threshold: float = 0.75
    max_upload_bytes: int = 10 * 1024 * 1024
    app_env: str = "development"
    billing_provider: str = "mock"
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_service_role_key: str | None = None

    @property
    def regulation_dir(self) -> Path:
        return self.data_dir / "regulations"

    @property
    def sample_dir(self) -> Path:
        return self.data_dir / "samples"


def get_settings() -> Settings:
    raw_model = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash"
    if "gemini-2.0" in raw_model or "gemini-2.5" in raw_model or "gemini-1.5" in raw_model:
        raw_model = "gemini-3.5-flash"

    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None,
        gemini_model=raw_model,
        embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", Settings.embedding_model),
        embedding_dimensions=int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", Settings.embedding_dimensions)),
        storage_dir=Path(os.getenv("STORAGE_DIR", "/tmp/storage" if os.getenv("VERCEL") else str(Settings.storage_dir))),
        cors_origins=_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://testserver")),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", Settings.retrieval_top_k)),
        review_threshold=float(os.getenv("REVIEW_THRESHOLD", Settings.review_threshold)),
        app_env=os.getenv("APP_ENV", Settings.app_env),
        billing_provider=os.getenv("BILLING_PROVIDER", Settings.billing_provider),
        supabase_url=os.getenv("SUPABASE_URL") or None,
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET") or None,
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None,
    )

