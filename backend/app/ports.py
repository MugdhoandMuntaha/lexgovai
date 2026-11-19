"""Abstract ports (Protocols) for external boundaries.

Decouples business logic from wall-clock time, notification dispatchers, external HTTP fetchers, and LLMs.
Allows tests to use deterministic fakes with zero network activity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .llm import LLMClient


class Clock(Protocol):
    """Abstract clock for deterministic time manipulation in tests."""

    def now(self) -> datetime:
        """Returns the current timezone-aware UTC datetime."""
        ...

    def today_dhaka(self) -> str:
        """Returns the current calendar date in Asia/Dhaka as 'YYYY-MM-DD'."""
        ...


class Notifier(Protocol):
    """Abstract notification dispatcher for multi-channel alerts and reminders."""

    def send(
        self,
        workspace_id: str,
        user_id: str,
        channel: str,  # "in_app" | "email"
        title: str,
        link: str,
        body: str,
        dedupe_key: str | None = None,
    ) -> bool:
        """Dispatches a notification. Returns True if successfully enqueued or delivered."""
        ...


class SourceFetcher(Protocol):
    """Abstract poller for retrieving external regulatory documents and web pages."""

    def fetch(self, url: str) -> tuple[str, str]:
        """Fetches and normalizes text from a URL. Returns (extracted_text, sha256_hash)."""
        ...


class OcrEngine(Protocol):
    """Abstract OCR engine for transcribing scanned/image documents into text."""

    def is_available(self) -> bool:
        """Returns True if this engine can execute in the current runtime."""
        ...

    def extract_text_from_pdf(
        self, pdf_bytes: bytes, max_pages: int = 20
    ) -> tuple[str, str, float, str]:
        """Returns (transcribed_text, extraction_method, confidence_score, notes)."""
        ...


class SourceCrawler(Protocol):
    """Abstract headless browser crawler for dynamic JavaScript-rendered government portals."""

    def crawl_source(
        self,
        start_url: str,
        domain_allowlist: list[str] | None = None,
        max_depth: int = 2,
        max_pages: int = 25,
        timeout_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        """Renders JS, enforces SSRF guards, respects robots.txt and depth/page caps.
        
        Returns list of page dicts: [{"url": ..., "text": ..., "content_hash": ..., "links": [...], "status": ...}]
        """
        ...


class ChannelAdapter(Protocol):
    """Abstract channel adapter for multi-channel alert delivery (in-app, email, SMS, WhatsApp)."""

    def send(
        self,
        alert_id: str,
        recipient_address: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatches notification to channel provider. Returns provider delivery record."""
        ...

    def parse_delivery_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Parses webhook callback from provider into canonical delivery status."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Checks provider credentials and connectivity."""
        ...

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        """Calculates segments and cost estimate (e.g. for SMS/WhatsApp)."""
        ...


class SmsProvider(Protocol):
    """Abstract SMS gateway interface for Bangladesh telco aggregators (SSL Wireless, generic HTTP, mock)."""

    def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict[str, Any]:
        """Sends SMS via gateway. Returns {provider_message_id, status, error, segments}."""
        ...

    def parse_dlr_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Parses DLR callback into canonical format."""
        ...

