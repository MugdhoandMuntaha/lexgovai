"""Versioned API v1 for external integrations.

Follows ADR 0002 Phase 2 specifications:
- Bearer API key authentication: Authorization: Bearer cos_live_...
- Reject cookie authentication completely on /api/v1 (keys only)
- Scopes: reports:read, findings:read, alerts:read, checklist:read
- Key hash at rest (SHA-256), prefix visible
- In-memory sliding window rate limit (60 requests/minute per key)
- Endpoints: /api/v1/reports, /api/v1/findings, /api/v1/alerts, /api/v1/checklist
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .auth import UnauthenticatedException
from .feature_options import API_KEY_RATE_LIMIT_PER_MINUTE

VALID_SCOPES = {"reports:read", "findings:read", "alerts:read", "checklist:read"}


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["reports:read", "findings:read"])


class ApiRateLimiter:
    """Thread-safe sliding window rate limiter per API key."""

    def __init__(self, limit_per_minute: int = API_KEY_RATE_LIMIT_PER_MINUTE):
        self.limit = limit_per_minute
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, key_id: str) -> None:
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            history = self._requests.setdefault(key_id, [])
            valid_history = [t for t in history if t > window_start]
            if len(valid_history) >= self.limit:
                oldest = valid_history[0]
                retry_after = max(1, int(60.0 - (now - oldest)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.limit} requests per minute.",
                    headers={"Retry-After": str(retry_after)},
                )
            valid_history.append(now)
            self._requests[key_id] = valid_history


def create_api_v1_router(svc: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["API v1 (Integrations)"])
    limiter = ApiRateLimiter(API_KEY_RATE_LIMIT_PER_MINUTE)

    def authenticate_api_key(
        request: Request,
        authorization: str | None = Header(None),
    ) -> dict[str, Any]:
        """Authenticates request strictly using Bearer API key. Rejects cookies."""
        if not authorization or not authorization.startswith("Bearer "):
            raise UnauthenticatedException(
                "API key authentication required. Pass 'Authorization: Bearer cos_live_...'."
            )

        raw_key = authorization.removeprefix("Bearer ").strip()
        if not raw_key.startswith("cos_live_"):
            raise UnauthenticatedException("Invalid API key format. Expected 'cos_live_...' prefix.")

        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        key_record = svc.db.get_api_key_by_hash(key_hash)
        if not key_record or key_record.get("revoked_at"):
            raise UnauthenticatedException("Invalid or revoked API key.")

        workspace_id = key_record["workspace_id"]
        # Workspace must have api_integrations entitlement
        if not svc.entitlements.has_at_least(workspace_id, "api_integrations", "limited"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace subscription does not include API integrations.",
            )

        # Rate limiting check
        limiter.check_and_record(key_record["id"])

        # Touch last_used_at
        svc.db.touch_api_key(key_record["id"])

        return key_record

    def require_scope(scope: str) -> Callable:
        def dependency(key_record: dict[str, Any] = Depends(authenticate_api_key)) -> dict[str, Any]:
            scopes = set(key_record.get("scopes", []))
            if scope not in scopes and "*" not in scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API key lacks required scope '{scope}'.",
                )
            return key_record

        return dependency

    @router.get("/reports")
    def get_v1_reports(key: dict[str, Any] = Depends(require_scope("reports:read"))):
        workspace_id = key["workspace_id"]
        plans = svc.db.list_action_plans(workspace_id)
        return {
            "workspace_id": workspace_id,
            "count": len(plans),
            "reports": [
                {
                    "id": p.get("id"),
                    "document_name": p.get("document_name"),
                    "regulation": p.get("regulation"),
                    "impact_score": p.get("impact_score"),
                    "urgency": p.get("urgency"),
                    "created_at": p.get("created_at"),
                }
                for p in plans
            ],
        }

    @router.get("/findings")
    def get_v1_findings(key: dict[str, Any] = Depends(require_scope("findings:read"))):
        workspace_id = key["workspace_id"]
        plans = svc.db.list_action_plans(workspace_id)
        findings = []
        for p in plans:
            for f in p.get("findings", []):
                findings.append(
                    {
                        "plan_id": p.get("id"),
                        "finding_id": f.get("id"),
                        "severity": f.get("severity"),
                        "issue": f.get("issue"),
                        "citation": f.get("citation"),
                        "confidence": f.get("confidence"),
                        "flagged_for_review": f.get("flagged_for_review", False),
                    }
                )
        return {
            "workspace_id": workspace_id,
            "count": len(findings),
            "findings": findings,
        }

    @router.get("/alerts")
    def get_v1_alerts(key: dict[str, Any] = Depends(require_scope("alerts:read"))):
        workspace_id = key["workspace_id"]
        subs = svc.db.list_monitor_subscriptions(workspace_id)
        changes = []
        for s in subs:
            rid = s["regulation_id"]
            reg_changes = svc.db.list_regulatory_changes(rid)
            for ch in reg_changes:
                changes.append(
                    {
                        "id": ch["id"],
                        "regulation_id": ch["regulation_id"],
                        "summary": ch["summary"],
                        "change_type": ch["change_type"],
                        "obligations": ch.get("obligations", []),
                        "detected_at": ch["detected_at"],
                    }
                )
        return {
            "workspace_id": workspace_id,
            "count": len(changes),
            "alerts": changes,
        }

    @router.get("/checklist")
    def get_v1_checklist(key: dict[str, Any] = Depends(require_scope("checklist:read"))):
        workspace_id = key["workspace_id"]
        items = svc.db.get_checklist_items(workspace_id)
        return {
            "workspace_id": workspace_id,
            "count": len(items),
            "items": items,
        }

    return router
