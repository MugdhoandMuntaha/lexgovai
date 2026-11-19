"""Headless browser crawler and link discovery engine for dynamic government portals.

Implements SourceCrawler with Playwright (Chromium), strict SSRF request interception,
robots.txt compliance, same-domain scoping, rate limiting, and regulatory candidate filtering.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
import urllib.robotparser
from typing import Any

from .adapters import SSRFValidationError, is_ip_allowed, validate_url_ssrf
from .ports import SourceCrawler

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "LexGOV-AI-GovCrawler/1.0 (+https://lexgov.ai/robot)"
MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB hard limit per page

# Keywords to identify candidate statutory orders, gazettes, circulars in English and Bengali
REGULATORY_KEYWORDS_EN = (
    "gazette",
    "sro",
    "circular",
    "order",
    "notification",
    "statutory",
    "vat",
    "tax",
    "amendment",
    "law",
    "act",
    "mushak",
)
REGULATORY_KEYWORDS_BN = (
    "গেজেট",
    "এসআরও",
    "পরিপত্র",
    "প্রজ্ঞাপন",
    "আইন",
    "অধ্যাদেশ",
    "বিধিমালা",
    "মূসক",
    "কর",
)


def is_likely_regulatory_link(url: str, anchor_text: str = "") -> bool:
    """Returns True if the URL or anchor text indicates a statutory regulatory document or PDF."""
    if ".pdf" in url.lower():
        return True

    target = f"{url.lower()} {anchor_text.lower()}"
    # Replace URL delimiters and punctuation with spaces to extract clean tokens
    clean_target = re.sub(r"[/_\-.\?&=#:,;]+", " ", target)
    tokens = set(clean_target.split())

    for kw in REGULATORY_KEYWORDS_EN:
        if kw in tokens:
            return True
        # Multi-syllable regulatory terms can also be matched as substrings
        if len(kw) >= 6 and kw in clean_target:
            return True

    for kw_bn in REGULATORY_KEYWORDS_BN:
        if kw_bn in target:
            return True

    return False


def is_blocked_page(page_text: str, status_code: int = 200) -> bool:
    """Detects whether a government portal returned a WAF/CAPTCHA challenge or access block."""
    if status_code in (401, 403, 429):
        return True
    lower = page_text.lower()
    challenge_indicators = (
        "attention required! | cloudflare",
        "access denied",
        "please verify you are human",
        "recaptcha",
        "cf-turnstile",
        "security check to access",
        "rate limit exceeded",
    )
    return any(ind in lower for ind in challenge_indicators)


class PlaywrightCrawlAdapter:
    """Headless Chromium web crawler with Playwright and strict SSRF route interception."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, polite_delay_seconds: float = 1.0):
        self.user_agent = user_agent
        self.polite_delay_seconds = polite_delay_seconds

    def _init_robots(self, start_url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urllib.parse.urlparse(start_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            # Validate robots.txt URL through SSRF guard before fetching
            validate_url_ssrf(robots_url)
            rp.set_url(robots_url)
            rp.read()
        except Exception:
            # If robots.txt cannot be fetched or read, default to permissive
            pass
        return rp

    def crawl_source(
        self,
        start_url: str,
        domain_allowlist: list[str] | None = None,
        max_depth: int = 2,
        max_pages: int = 25,
        timeout_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        # 1. Validate starting URL through SSRF guard
        try:
            validate_url_ssrf(start_url)
        except SSRFValidationError as err:
            logger.warning(f"SSRF guard blocked starting crawl URL '{start_url}': {err}")
            return [
                {
                    "url": start_url,
                    "text": "",
                    "content_hash": "",
                    "links": [],
                    "status": "blocked",
                    "error": f"SSRF blocked: {err}",
                }
            ]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("Playwright is not installed. Run `pip install playwright && playwright install chromium`.")

        parsed_start = urllib.parse.urlparse(start_url)
        base_domain = parsed_start.hostname or ""
        allowed_domains = set(domain_allowlist or [base_domain])

        robots = self._init_robots(start_url)
        results: list[dict[str, Any]] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(start_url, 0)]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)

            # SSRF Route Interception: inspect every subresource request and redirect
            def intercept_route(route, request):
                req_url = request.url
                try:
                    validate_url_ssrf(req_url)
                    route.continue_()
                except Exception as ssrf_err:
                    logger.warning(f"Aborting subresource/redirect to '{req_url}': {ssrf_err}")
                    route.abort("blockedbyclient")

            context.route("**/*", intercept_route)
            page = context.new_page()

            while queue and len(visited) < max_pages:
                current_url, depth = queue.pop(0)
                if current_url in visited or depth > max_depth:
                    continue

                visited.add(current_url)

                # Check robots.txt
                if not robots.can_fetch(self.user_agent, current_url):
                    results.append(
                        {
                            "url": current_url,
                            "text": "",
                            "content_hash": "",
                            "links": [],
                            "status": "blocked",
                            "error": "Disallowed by robots.txt",
                        }
                    )
                    continue

                try:
                    response = page.goto(current_url, wait_until="networkidle", timeout=timeout_seconds * 1000)
                    status_code = response.status if response else 200

                    # Check for redirects violating SSRF or domain allowlist
                    final_url = page.url
                    validate_url_ssrf(final_url)
                    final_host = urllib.parse.urlparse(final_url).hostname or ""
                    if final_host not in allowed_domains:
                        results.append(
                            {
                                "url": current_url,
                                "text": "",
                                "content_hash": "",
                                "links": [],
                                "status": "blocked",
                                "error": f"Redirected to outside domain '{final_host}'",
                            }
                        )
                        continue

                    # Extract visible rendered text
                    body_text = page.locator("body").inner_text()
                    if len(body_text.encode("utf-8")) > MAX_BODY_BYTES:
                        body_text = body_text[:MAX_BODY_BYTES]

                    # Check anti-bot block / CAPTCHA
                    if is_blocked_page(body_text, status_code=status_code):
                        results.append(
                            {
                                "url": current_url,
                                "text": "",
                                "content_hash": "",
                                "links": [],
                                "status": "blocked",
                                "error": f"Access challenge or blocked response (HTTP {status_code})",
                            }
                        )
                        continue

                    content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

                    # Link discovery
                    raw_links: list[dict[str, str]] = page.eval_on_selector_all(
                        "a[href]",
                        "elements => elements.map(e => ({ href: e.href, text: e.innerText || '' }))",
                    )

                    discovered_regulatory_links: list[str] = []
                    for link_obj in raw_links:
                        href = link_obj.get("href", "")
                        anchor_text = link_obj.get("text", "")
                        if not href or not href.startswith("http"):
                            continue

                        # Check SSRF and domain
                        link_host = urllib.parse.urlparse(href).hostname or ""
                        if link_host in allowed_domains and is_likely_regulatory_link(href, anchor_text):
                            discovered_regulatory_links.append(href)
                            if depth + 1 <= max_depth and href not in visited:
                                queue.append((href, depth + 1))

                    results.append(
                        {
                            "url": current_url,
                            "text": body_text,
                            "content_hash": content_hash,
                            "links": list(dict.fromkeys(discovered_regulatory_links)),
                            "status": "ok",
                            "error": None,
                        }
                    )

                except Exception as exc:
                    logger.warning(f"Error crawling '{current_url}': {exc}")
                    results.append(
                        {
                            "url": current_url,
                            "text": "",
                            "content_hash": "",
                            "links": [],
                            "status": "error",
                            "error": str(exc),
                        }
                    )

                # Polite rate-limiting between successive HTTP requests
                time.sleep(self.polite_delay_seconds)

            browser.close()

        return results


class FakeCrawler:
    """Deterministic crawler for offline unit and integration tests."""

    def __init__(self, pages: dict[str, dict[str, Any]] | None = None):
        self.pages: dict[str, dict[str, Any]] = pages or {}
        self.crawl_calls: list[str] = []

    def crawl_source(
        self,
        start_url: str,
        domain_allowlist: list[str] | None = None,
        max_depth: int = 2,
        max_pages: int = 25,
        timeout_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        self.crawl_calls.append(start_url)
        results: list[dict[str, Any]] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(start_url, 0)]

        parsed_start = urllib.parse.urlparse(start_url)
        base_domain = parsed_start.hostname or ""
        allowed_domains = set(domain_allowlist or [base_domain])

        while queue and len(visited) < max_pages:
            current_url, depth = queue.pop(0)
            if current_url in visited or depth > max_depth:
                continue

            visited.add(current_url)

            # SSRF check simulation
            try:
                validate_url_ssrf(current_url)
            except SSRFValidationError as err:
                results.append(
                    {
                        "url": current_url,
                        "text": "",
                        "content_hash": "",
                        "links": [],
                        "status": "blocked",
                        "error": f"SSRF blocked: {err}",
                    }
                )
                continue

            # Domain check
            host = urllib.parse.urlparse(current_url).hostname or ""
            if host not in allowed_domains:
                results.append(
                    {
                        "url": current_url,
                        "text": "",
                        "content_hash": "",
                        "links": [],
                        "status": "blocked",
                        "error": f"Outside allowed domains: {host}",
                    }
                )
                continue

            # Check mock store
            mock_entry = self.pages.get(current_url)
            if not mock_entry:
                results.append(
                    {
                        "url": current_url,
                        "text": "",
                        "content_hash": "",
                        "links": [],
                        "status": "error",
                        "error": "404 Not Found in mock store",
                    }
                )
                continue

            if mock_entry.get("blocked"):
                results.append(
                    {
                        "url": current_url,
                        "text": "",
                        "content_hash": "",
                        "links": [],
                        "status": "blocked",
                        "error": mock_entry.get("error", "Blocked by security policy"),
                    }
                )
                continue

            text = mock_entry.get("text", "")
            links = mock_entry.get("links", [])
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            # Enqueue discovered links
            for link in links:
                if depth + 1 <= max_depth and link not in visited:
                    queue.append((link, depth + 1))

            results.append(
                {
                    "url": current_url,
                    "text": text,
                    "content_hash": content_hash,
                    "links": links,
                    "status": "ok",
                    "error": None,
                }
            )

        return results
