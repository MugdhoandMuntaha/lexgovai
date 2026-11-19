"""API Endpoints for LexGOV AI Alert Center.

Provides workspace-scoped endpoints for alert inbox, acknowledgment, preference matrix,
phone OTP verification, compliance owner assignments, workspace settings, live SMS segment
calculation, test sends, delivery stats, and external webhook receivers.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from ..services import Services
from .events import AlertSeverity, EVENT_CATALOG
from .router import AlertRouter
from .verification import VerificationService, mask_email
from .channels.sms import count_sms_segments, mask_phone_number, normalize_bd_phone
from .short_links import ShortLinkService

logger = logging.getLogger("complianceos.alerts.api")


# ---------------------------------------------------------------------------
# Pydantic Request & Response Schemas
# ---------------------------------------------------------------------------

class AckAlertRequest(BaseModel):
    acked_via: str = Field(default="in_app", description="'in_app', 'email', 'sms', or 'whatsapp'")


class SetPreferenceItem(BaseModel):
    event_type: str
    channel: str
    enabled: bool


class BatchPreferencesRequest(BaseModel):
    preferences: list[SetPreferenceItem]


class OtpRequest(BaseModel):
    phone_number: str


class OtpVerifyRequest(BaseModel):
    phone_number: str
    code: str


class WhatsAppOptInRequest(BaseModel):
    phone_number: str


class SmsPreviewRequest(BaseModel):
    text: str


class ComplianceOwnerRequest(BaseModel):
    domain_tag: str
    primary_user_id: str
    backup_user_id: str | None = None


class WorkspaceAlertSettingsUpdate(BaseModel):
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    weekend_days: list[int] | None = None
    escalation_critical_hours: int | None = None
    escalation_high_hours: int | None = None
    monthly_sms_cap: int | None = None
    monthly_whatsapp_cap: int | None = None
    digest_hour_bst: int | None = None


class TestSendRequest(BaseModel):
    channel: str
    recipient_address: str
    subject: str
    body: str


# ---------------------------------------------------------------------------
# Protected Alerts Router
# ---------------------------------------------------------------------------

def create_alerts_router(
    svc: Services,
    get_current_user_dep: Any,
    get_current_workspace_dep: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/alerts", tags=["alerts"])
    verification_svc = VerificationService(svc.db)
    alert_router = AlertRouter(db=svc.db)

    def require_admin(workspace: dict[str, Any]) -> None:
        if workspace.get("role") not in ("owner", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative permissions required to manage workspace alert routing.",
            )

    @router.get("")
    def list_alerts(
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
        user: dict[str, Any] = Depends(get_current_user_dep),
        status_filter: str | None = Query(None, alias="status"),
        severity_filter: str | None = Query(None, alias="severity"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """Lists alerts for the current workspace. Viewers only see their own alerts."""
        recipient_filter = user["id"] if workspace.get("role") == "viewer" else None
        alerts = svc.db.list_alerts(
            workspace_id=workspace["id"],
            recipient_user_id=recipient_filter,
            status=status_filter,
            severity=severity_filter,
            limit=limit,
            offset=offset,
        )
        return {"alerts": alerts, "count": len(alerts)}

    @router.post("/{alert_id}/ack")
    def acknowledge_alert(
        alert_id: str,
        body: AckAlertRequest,
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Acknowledges a high/critical compliance alert."""
        alert = svc.db.get_alert(alert_id)
        if not alert or alert["workspace_id"] != workspace["id"]:
            raise HTTPException(status_code=404, detail="Alert not found.")

        updated = svc.db.acknowledge_alert(alert_id, user["id"], acked_via=body.acked_via)
        return {"status": "ok", "alert": updated}

    @router.get("/{alert_id}/deliveries")
    def get_alert_deliveries(
        alert_id: str,
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Gets full delivery attempt audit logs for an alert."""
        alert = svc.db.get_alert(alert_id)
        if not alert or alert["workspace_id"] != workspace["id"]:
            raise HTTPException(status_code=404, detail="Alert not found.")
        deliveries = svc.db.get_alert_deliveries(alert_id)
        return {"deliveries": deliveries}

    @router.get("/preferences")
    def get_user_preferences(
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Returns the user's event-type x channel preference toggles."""
        prefs = svc.db.get_alert_preferences(user["id"])
        # Format as dictionary mapping: {event_type: {channel: bool}}
        matrix: dict[str, dict[str, bool]] = {}
        for r in prefs:
            ev = r["event_type"]
            if ev not in matrix:
                matrix[ev] = {}
            matrix[ev][r["channel"]] = bool(r["enabled"])
        return {"preferences": matrix, "catalog": list(EVENT_CATALOG.keys())}

    @router.put("/preferences")
    def update_user_preferences(
        body: BatchPreferencesRequest,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Batch saves the user's notification preference matrix."""
        tuples = [(p.event_type, p.channel, p.enabled) for p in body.preferences]
        svc.db.batch_set_alert_preferences(user["id"], tuples)
        return {"status": "ok"}

    @router.get("/channels")
    def get_user_channels(
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Returns the user's configured notification addresses with privacy masking."""
        channels = svc.db.get_user_channels(user["id"])
        email_record = next((c for c in channels if c["channel"] == "email"), None)
        email_addr = email_record["address"] if email_record else user.get("email", "")

        return {
            "email": {
                "address": mask_email(email_addr),
                "verified": bool(email_record.get("verified_at")) if email_record else True,
                "opted_out": bool(email_record.get("opted_out_at")) if email_record else False,
            },
            "sms": next((
                {
                    "address": c["display_address"],
                    "verified": bool(c["verified_at"]),
                    "opted_out": bool(c["opted_out_at"]),
                    "locale": c.get("locale", "en"),
                }
                for c in channels if c["channel"] == "sms"
            ), None),
            "whatsapp": next((
                {
                    "address": c["display_address"],
                    "verified": bool(c["verified_at"]),
                    "opted_in": bool(c["whatsapp_opt_in_at"]),
                    "opted_out": bool(c["opted_out_at"]),
                }
                for c in channels if c["channel"] == "whatsapp"
            ), None),
        }

    @router.post("/channels/otp/request")
    def request_phone_otp(
        body: OtpRequest,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Generates and dispatches a 6-digit verification code via the configured SMS adapter."""
        try:
            code, norm_phone = verification_svc.request_phone_otp(user["id"], body.phone_number)
            # Dispatch SMS OTP
            sms_adapter = alert_router.channels.get("sms")
            is_mock = True
            if sms_adapter:
                provider_inst = getattr(sms_adapter, "provider", None)
                from .channels.sms import MockSmsProvider
                is_mock = isinstance(provider_inst, MockSmsProvider)
                msg = f"Your LexGOV AI verification code is: {code}. Valid for 10 minutes."
                sms_adapter.send(
                    alert_id=f"otp_{user['id']}",
                    recipient_address=norm_phone,
                    subject="Verification Code",
                    body=msg,
                )
            result: dict[str, Any] = {"status": "ok", "masked_phone": mask_phone_number(norm_phone)}
            if is_mock:
                result["dev_code"] = code
            return result
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    @router.post("/channels/otp/verify")
    def verify_phone_otp(
        body: OtpVerifyRequest,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Verifies the submitted SMS OTP code and activates the SMS channel."""
        try:
            success = verification_svc.verify_phone_otp(user["id"], body.phone_number, body.code)
            if not success:
                raise HTTPException(status_code=400, detail="Invalid verification code.")
            return {"status": "verified"}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    @router.post("/channels/whatsapp/opt-in")
    def opt_in_whatsapp(
        body: WhatsAppOptInRequest,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Records explicit opt-in for WhatsApp business compliance notifications."""
        try:
            verification_svc.opt_in_whatsapp(user["id"], body.phone_number)
            return {"status": "opted_in"}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    @router.post("/channels/{channel}/opt-out")
    def opt_out_channel(
        channel: str,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Provides one-click opt-out for any non-essential communication channel."""
        if channel not in ("sms", "whatsapp", "email", "telegram"):
            raise HTTPException(status_code=400, detail="Invalid channel.")
        verification_svc.opt_out_channel(user["id"], channel)
        return {"status": "opted_out", "channel": channel}

    @router.post("/channels/{channel}/re-opt-in")
    def re_opt_in_channel(
        channel: str,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Re-enables an opted-out communication channel."""
        if channel not in ("sms", "whatsapp", "email", "telegram"):
            raise HTTPException(status_code=400, detail="Invalid channel.")
        verification_svc.re_opt_in_channel(user["id"], channel)
        return {"status": "opted_in", "channel": channel}

    @router.post("/sms/preview-segments")
    def preview_sms_segments(
        body: SmsPreviewRequest,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ):
        """Computes live GSM-7 vs Unicode (Bangla) character count, segments, and cost estimate."""
        info = count_sms_segments(body.text)
        cost_non_masking = round(info["segments"] * 0.35, 2)
        cost_masking = round(info["segments"] * 0.55, 2)
        return {
            **info,
            "cost_non_masking_bdt": cost_non_masking,
            "cost_masking_bdt": cost_masking,
        }

    # Administrative Alert Routing & Owners
    @router.get("/compliance-owners")
    def list_compliance_owners(
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        owners = svc.db.list_compliance_owners(workspace["id"])
        return {"compliance_owners": owners}

    @router.put("/compliance-owners")
    def set_compliance_owner(
        body: ComplianceOwnerRequest,
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        require_admin(workspace)
        updated = svc.db.set_compliance_owner(
            workspace_id=workspace["id"],
            domain_tag=body.domain_tag,
            primary_user_id=body.primary_user_id,
            backup_user_id=body.backup_user_id,
        )
        return {"status": "ok", "compliance_owner": updated}

    @router.delete("/compliance-owners/{domain_tag}")
    def delete_compliance_owner(
        domain_tag: str,
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        require_admin(workspace)
        svc.db.delete_compliance_owner(workspace["id"], domain_tag)
        return {"status": "ok"}

    @router.get("/workspace-settings")
    def get_workspace_alert_settings(
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        settings = svc.db.get_workspace_alert_settings(workspace["id"])
        return {"settings": settings}

    @router.put("/workspace-settings")
    def update_workspace_alert_settings(
        body: WorkspaceAlertSettingsUpdate,
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        require_admin(workspace)
        updates = body.model_dump(exclude_unset=True)
        updated = svc.db.update_workspace_alert_settings(workspace["id"], **updates)
        return {"status": "ok", "settings": updated}

    @router.post("/test-send")
    def test_send_alert(
        body: TestSendRequest,
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        require_admin(workspace)
        adapter = alert_router.channels.get(body.channel)
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Unsupported channel {body.channel}")

        result = adapter.send(
            alert_id=f"test_{workspace['id']}",
            recipient_address=body.recipient_address,
            subject=body.subject,
            body=body.body,
            metadata={"workspace_id": workspace["id"]},
        )
        return {"result": result}

    @router.get("/stats")
    def get_delivery_stats(
        workspace: dict[str, Any] = Depends(get_current_workspace_dep),
    ):
        require_admin(workspace)
        stats = svc.db.get_delivery_stats(workspace["id"])
        return {"delivery_stats": stats}

    return router


# ---------------------------------------------------------------------------
# Public Webhooks & Short Links Router
# ---------------------------------------------------------------------------

def create_alerts_webhook_router(svc: Services) -> APIRouter:
    router = APIRouter(tags=["alert-webhooks"])
    short_link_svc = ShortLinkService(svc.db)

    @router.get("/l/{code}")
    def resolve_short_link(code: str):
        """Resolves signed, expiring short link codes and redirects to the application target."""
        target_url = short_link_svc.resolve(code)
        if not target_url:
            raise HTTPException(status_code=404, detail="Short link expired or invalid.")
        return RedirectResponse(url=target_url, status_code=302)

    @router.post("/webhooks/alerts/sms")
    @router.post("/api/webhooks/alerts/sms")
    def sms_dlr_webhook(request: Request, payload: dict[str, Any]):
        """Receives Delivery Reports (DLR) from Bangladesh SMS Gateways (e.g. SSL Wireless)."""
        logger.info(f"Received SMS DLR: {payload}")
        sms_id = payload.get("sms_id") or payload.get("csms_id") or payload.get("message_id")
        status_val = str(payload.get("status", "")).upper()
        norm_status = "delivered" if status_val in ("DELIVRD", "SUCCESS", "DELIVERED") else "failed"

        if sms_id:
            row = svc.db._fetchone("SELECT id FROM alert_deliveries WHERE provider_message_id = ?", (sms_id,))
            if row:
                svc.db.update_alert_delivery(row["id"], norm_status)
        return {"status": "received"}

    @router.get("/webhooks/alerts/whatsapp")
    @router.get("/api/webhooks/alerts/whatsapp")
    def whatsapp_verify_webhook(
        hub_mode: str = Query(None, alias="hub.mode"),
        hub_challenge: str = Query(None, alias="hub.challenge"),
        hub_verify_token: str = Query(None, alias="hub.verify_token"),
    ):
        """Meta WhatsApp Cloud API webhook challenge verification."""
        expected_token = "complianceos_wa_verify_token"
        if hub_mode == "subscribe" and hub_verify_token == expected_token:
            return Response(content=hub_challenge, media_type="text/plain")
        raise HTTPException(status_code=403, detail="Verification token mismatch.")

    @router.post("/webhooks/alerts/whatsapp")
    @router.post("/api/webhooks/alerts/whatsapp")
    def whatsapp_status_webhook(
        request: Request,
        payload: dict[str, Any],
        x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    ):
        """Receives WhatsApp message status webhooks (sent, delivered, read, failed)."""
        logger.info(f"Received WhatsApp webhook event")
        try:
            entry = payload.get("entry", [{}])[0]
            change = entry.get("changes", [{}])[0]
            statuses = change.get("value", {}).get("statuses", [])
            for st in statuses:
                wamid = st.get("id")
                status_raw = st.get("status")
                norm_status = "read" if status_raw == "read" else ("delivered" if status_raw == "delivered" else status_raw)
                if wamid:
                    row = svc.db._fetchone("SELECT id FROM alert_deliveries WHERE provider_message_id = ?", (wamid,))
                    if row:
                        svc.db.update_alert_delivery(row["id"], norm_status)
        except Exception as e:
            logger.warning(f"Error processing WhatsApp status: {e}")

        return {"status": "received"}

    return router
