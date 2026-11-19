"""Signed Short Links Service for Compliance Alert Links."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import Database


class ShortLinkService:
    def __init__(self, db: Database, base_domain: str | None = None):
        self.db = db
        self.base_domain = base_domain or "https://compliance-sand.vercel.app"

    def create_short_link(self, target_path_or_url: str, expire_days: int = 14) -> dict[str, str]:
        """Creates a signed, expiring short link code and full URL."""
        code = secrets.token_urlsafe(5)[:7]  # 7 chars safe string
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expire_days)).isoformat(timespec="seconds")
        
        self.db.create_short_link(code, target_path_or_url, expires_at)
        return {
            "code": code,
            "short_url": f"{self.base_domain.rstrip('/')}/l/{code}",
            "original_url": target_path_or_url,
            "expires_at": expires_at,
        }

    def resolve(self, code: str) -> str | None:
        """Resolves short link code, verifying expiration."""
        record = self.db.get_short_link(code)
        if not record:
            return None
        expires_at = record.get("expires_at")
        if expires_at:
            now_dt = datetime.now(timezone.utc)
            exp_dt = datetime.fromisoformat(expires_at)
            if now_dt > exp_dt:
                return None
        return record.get("original_url")
