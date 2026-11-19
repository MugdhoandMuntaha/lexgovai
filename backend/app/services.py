"""Shared service container passed to routes and agents."""

from __future__ import annotations

from dataclasses import dataclass

from .billing import BillingProvider, MockBillingProvider
from .config import Settings
from .db import Database
from .entitlements import EntitlementService
from .llm import LLMClient, LLMNotConfiguredError
from .ports import OcrEngine, SourceCrawler
from .subscriptions import SubscriptionService
from .usage import UsageService
from .vectorstore import VectorStore


@dataclass
class Services:
    settings: Settings
    db: Database
    store: VectorStore
    llm: LLMClient | None
    entitlements: EntitlementService
    usage: UsageService
    subscriptions: SubscriptionService
    billing: BillingProvider
    notifier: any = None
    ocr: OcrEngine | None = None
    crawler: SourceCrawler | None = None
    ocr: OcrEngine | None = None
    crawler: SourceCrawler | None = None

    def require_llm(self) -> LLMClient:
        if self.llm is None:
            raise LLMNotConfiguredError(
                "GEMINI_API_KEY is not configured on the backend. Add it to backend/.env and restart the server."
            )
        return self.llm

