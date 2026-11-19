"""Customer support ticketing and plan-based priority routing.

Follows ADR 0002 Phase 2 specifications:
- Priority mapping by workspace plan:
  - Professional -> "urgent" (4h SLA)
  - Growth -> "priority" (12h SLA)
  - Starter / Free -> "standard" (48h SLA)
- Transactional notification and outbox acknowledgment
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

SLA_MAP = {
    "urgent": "4 hours (Dedicated Enterprise Engineer)",
    "priority": "12 hours (Priority Compliance Desk)",
    "standard": "48 hours (Standard Support)",
}


def derive_ticket_priority(plan_id: str) -> tuple[Literal["urgent", "priority", "standard"], str]:
    if plan_id == "professional":
        return "urgent", SLA_MAP["urgent"]
    if plan_id == "growth":
        return "priority", SLA_MAP["priority"]
    return "standard", SLA_MAP["standard"]


class SupportTicketCreateRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=10000)
