"""DiscoveryAgent: Crawls enabled law sources to find and deduplicate candidate statutory documents."""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

from app.crawler import is_likely_regulatory_link
from app.db import Database
from app.ports import SourceCrawler


@dataclass(frozen=True)
class DiscoveredLawCandidate:
    source_id: str
    source_url: str
    title_hint: str
    anchor_text: str
    is_duplicate: bool
    existing_law_id: str | None = None


def normalize_title(title: str) -> str:
    """Normalizes title for deduplication comparison."""
    clean = re.sub(r"[^\w\s]", " ", title.lower())
    return " ".join(clean.split())


class DiscoveryAgent:
    """Discovers statutory candidates from authoritative government portals."""

    def __init__(self, db: Database, crawler: SourceCrawler):
        self.db = db
        self.crawler = crawler

    def discover_candidates(self, source_id: str) -> list[DiscoveredLawCandidate]:
        src = self.db.get_law_source(source_id)
        if not src or not src.get("enabled"):
            return []

        base_url = src["base_url"]
        cfg = src.get("crawl_config") or {}
        max_depth = cfg.get("max_depth", 2)
        max_pages = cfg.get("max_pages", 25)
        allowed_domains = cfg.get("allowed_domains") or [urllib.parse.urlparse(base_url).hostname or ""]

        crawl_results = self.crawler.crawl_source(
            start_url=base_url,
            domain_allowlist=allowed_domains,
            max_depth=max_depth,
            max_pages=max_pages,
        )

        candidates: list[DiscoveredLawCandidate] = []
        existing_laws = self.db.list_laws(publish_state=None, limit=1000)
        existing_map = {normalize_title(l["canonical_title_en"]): l["id"] for l in existing_laws}

        seen_urls: set[str] = set()

        for page in crawl_results:
            if page.get("status") == "blocked":
                self.db.update_law_source(source_id, last_status="blocked")
                continue

            links = page.get("links", [])
            for link_url in links:
                if link_url in seen_urls:
                    continue
                seen_urls.add(link_url)

                # Extract a title hint from the URL slug
                parsed_link = urllib.parse.urlparse(link_url)
                path_slug = parsed_link.path.split("/")[-1].replace(".pdf", "").replace(".html", "")
                title_hint = path_slug.replace("-", " ").replace("_", " ").title() or "Discovered Instrument"

                norm = normalize_title(title_hint)
                existing_id = existing_map.get(norm)

                candidates.append(
                    DiscoveredLawCandidate(
                        source_id=source_id,
                        source_url=link_url,
                        title_hint=title_hint,
                        anchor_text="",
                        is_duplicate=existing_id is not None,
                        existing_law_id=existing_id,
                    )
                )

        return candidates

