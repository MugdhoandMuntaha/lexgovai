"""Team collaboration, RBAC enforcement, invites, comments, and human-in-the-loop finding reviews.

Follows ADR 0002 Phase 2 specifications:
- Role hierarchy: viewer < member < admin < owner
- Seat limit freeze on downgrade (newest members become read-only viewers)
- Single-use invite tokens hashed with SHA-256 (7-day TTL)
- Audit comments on findings and checklist items
- Human-in-the-loop finding reviews with adjusted impact score recalculation
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
    "owner": 3,
}

RoleName = Literal["viewer", "member", "admin", "owner"]


def has_role_at_least(role: str, required_role: str) -> bool:
    """Verifies that actual role satisfies or exceeds required_role in the hierarchy."""
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def resolve_workspace_members_with_status(
    members: list[dict[str, Any]], seat_limit: int
) -> list[dict[str, Any]]:
    """Annotates each member with effective_role and is_frozen based on plan seat limit.

    Members are evaluated in order of created_at ASC (seniority).
    Any members beyond seat_limit (excluding workspace owners) are frozen to read-only viewers.
    """
    sorted_members = sorted(members, key=lambda m: m.get("created_at", ""))
    result: list[dict[str, Any]] = []

    for index, member in enumerate(sorted_members):
        item = dict(member)
        raw_role = item.get("role", "member")

        if raw_role == "owner" or index < seat_limit:
            item["effective_role"] = raw_role
            item["is_frozen"] = False
        else:
            item["effective_role"] = "viewer"
            item["is_frozen"] = True

        result.append(item)

    return result


def generate_invite_token() -> tuple[str, str, str]:
    """Generates (raw_token, token_hash, expires_at_iso) with 7-day TTL."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec="seconds")
    return raw_token, token_hash, expires_at


class InviteCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: Literal["admin", "member", "viewer"] = "member"


class InviteAcceptRequest(BaseModel):
    token: str = Field(..., min_length=16)


class MemberRoleUpdateRequest(BaseModel):
    role: Literal["admin", "member", "viewer"]


class CommentCreateRequest(BaseModel):
    resource_type: Literal["finding", "checklist_item"]
    resource_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, max_length=5000)


class FindingReviewRequest(BaseModel):
    plan_id: str = Field(..., min_length=1)
    finding_id: str = Field(..., min_length=1)
    status: Literal["approved", "rejected", "edited"]
    note: str | None = Field(default=None, max_length=2000)
    edited_citation: str | None = Field(default=None, max_length=2000)
