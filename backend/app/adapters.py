"""Concrete adapter implementations for ports: Clocks, Notifiers, and Source Fetchers."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import smtplib
import socket
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import Any

from .feature_options import POLLER_MAX_BODY_BYTES, POLLER_TIMEOUT_SECONDS
from .ports import Clock, Notifier, SourceFetcher

logger = logging.getLogger(__name__)

DHAKA_TZ = timezone(timedelta(hours=6))


# ---------------------------------------------------------------------------
# Clock Adapters
# ---------------------------------------------------------------------------


class SystemClock:
    """Production clock using real system wall time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today_dhaka(self) -> str:
        return datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")


class FakeClock:
    """Deterministic clock for reproducible tests across day and month boundaries."""

    def __init__(self, initial_time: datetime | None = None):
        self._current = initial_time or datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._current

    def today_dhaka(self) -> str:
        return self._current.astimezone(DHAKA_TZ).strftime("%Y-%m-%d")

    def advance(self, delta: timedelta) -> None:
        self._current += delta

    def set_time(self, new_time: datetime) -> None:
        self._current = new_time


# ---------------------------------------------------------------------------
# Notifier Adapters
# ---------------------------------------------------------------------------


class ConsoleNotifier:
    """Development and test email adapter that logs messages without external SMTP."""

    def __init__(self):
        self.sent_messages: list[dict[str, Any]] = []

    def send(
        self,
        workspace_id: str,
        user_id: str,
        channel: str,
        title: str,
        link: str,
        body: str,
        dedupe_key: str | None = None,
    ) -> bool:
        msg = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "channel": channel,
            "title": title,
            "link": link,
            "body": body,
            "dedupe_key": dedupe_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.sent_messages.append(msg)
        logger.info(f"[CONSOLE NOTIFIER - {channel.upper()}] To: {user_id} | Title: {title} | Link: {link}")
        return True

    def send_email(self, to: str, subject: str, body: str) -> bool:
        self.sent_messages.append({
            "channel": "email",
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"[CONSOLE NOTIFIER - EMAIL] To: {to} | Subject: {subject}")
        return True


class SmtpNotifier:
    """Production email notifier using Python standard library smtplib."""

    def __init__(self, host: str = "localhost", port: int = 587, user: str = "", password: str = "", from_email: str = "noreply@lexgov.ai"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email

    def send(
        self,
        workspace_id: str,
        user_id: str,
        channel: str,
        title: str,
        link: str,
        body: str,
        dedupe_key: str | None = None,
    ) -> bool:
        if channel != "email":
            return False

        msg = EmailMessage()
        msg["Subject"] = f"[LexGOV AI] {title}"
        msg["From"] = self.from_email
        msg["To"] = user_id
        # Email contains title, general body, and link only (no proprietary SOP text)
        msg.set_content(f"{title}\n\n{body}\n\nView details: {link}\n\nLexGOV AI Intelligence")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.user and self.password:
                    server.starttls()
                    server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False


# ---------------------------------------------------------------------------
# HTML Text Stripper (Standard Library)
# ---------------------------------------------------------------------------


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []

    def handle_data(self, data: str):
        clean = data.strip()
        if clean:
            self.text_parts.append(clean)

    def get_text(self) -> str:
        return "\n".join(self.text_parts)


# ---------------------------------------------------------------------------
# SSRF-Protected Source Fetcher
# ---------------------------------------------------------------------------


class SSRFValidationError(ValueError):
    pass


def is_ip_allowed(ip_str: str) -> bool:
    """Blocks private, loopback, link-local, multicast, and cloud metadata addresses."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip_str == "169.254.169.254"
        ):
            return False
        return True
    except ValueError:
        return False


def validate_url_ssrf(url: str) -> tuple[str, str, list[str]]:
    """Validates that a URL uses http/https and resolves to non-internal IP addresses."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFValidationError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL lacks a valid hostname.")

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as err:
        raise SSRFValidationError(f"DNS resolution failed for '{hostname}': {err}")

    resolved_ips: list[str] = []
    for entry in addr_info:
        ip_str = entry[4][0]
        if not is_ip_allowed(ip_str):
            raise SSRFValidationError(f"Access to IP '{ip_str}' ({hostname}) is forbidden for security (SSRF prevention).")
        resolved_ips.append(ip_str)

    return parsed.scheme, hostname, resolved_ips


class UrlPollAdapter:
    """SSRF-guarded web poller that safely retrieves and normalizes regulatory notices."""

    USER_AGENT = "LexGOV-AI-Monitor/1.0 (+https://lexgov.ai/robot)"

    def is_ip_allowed(self, ip_str: str) -> bool:
        return is_ip_allowed(ip_str)

    def validate_url(self, url: str) -> tuple[str, str]:
        scheme, host, _ = validate_url_ssrf(url)
        return scheme, host

    def fetch(self, url: str) -> tuple[str, str]:
        self.validate_url(url)

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain,*/*;q=0.8",
            },
        )

        with urllib.request.urlopen(req, timeout=POLLER_TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            if final_url != url:
                self.validate_url(final_url)

            content_type = response.headers.get_content_type()
            raw_bytes = response.read(POLLER_MAX_BODY_BYTES + 1)
            if len(raw_bytes) > POLLER_MAX_BODY_BYTES:
                raise ValueError(f"Payload from '{url}' exceeds {POLLER_MAX_BODY_BYTES} byte limit.")

            if content_type == "text/html":
                parser = HTMLTextExtractor()
                parser.feed(raw_bytes.decode("utf-8", errors="replace"))
                text = parser.get_text()
            else:
                text = raw_bytes.decode("utf-8", errors="replace")

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return text, content_hash


class FakeSourceFetcher:
    """Mock poller storing canned responses for testing."""

    def __init__(self, responses: dict[str, str] | None = None):
        self.responses: dict[str, str] = responses or {}
        self.call_count: dict[str, int] = {}

    def fetch(self, url: str) -> tuple[str, str]:
        self.call_count[url] = self.call_count.get(url, 0) + 1
        if url not in self.responses:
            raise ValueError(f"FakeSourceFetcher: 404 URL '{url}' not found in mock store.")
        text = self.responses[url]
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return text, content_hash
