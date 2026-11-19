"""SMS Channel Adapter for Bangladesh Gateways.

Implements number normalization to +8801XXXXXXXXX, accurate GSM-7 vs Unicode (Bangla)
segment counting, SSL Wireless adapter, generic HTTP gateway adapter, and a mock provider.
"""

from __future__ import annotations

import logging
import math
import os
import re
import urllib.parse
from typing import Any
import httpx

from ...ports import SmsProvider

logger = logging.getLogger("complianceos.alerts.sms")

# Bangladesh Mobile Operators: 013 (GP), 014 (Banglalink), 015 (Teletalk), 016 (Airtel), 017 (GP), 018 (Robi), 019 (Banglalink)
BD_PHONE_REGEX = re.compile(r"^(?:\+?8801|01)([3-9]\d{8})$")

# Standard GSM 7-bit default alphabet characters
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENDED = set("^{}\\[~]|€")


def normalize_bd_phone(phone: str) -> str:
    """Normalizes a Bangladesh mobile number to E.164 (+8801XXXXXXXXX).
    
    Raises ValueError if the number is not a valid Bangladesh mobile operator number.
    """
    clean = re.sub(r"[\s\-\(\)]", "", phone.strip())
    match = BD_PHONE_REGEX.match(clean)
    if not match:
        raise ValueError(f"Invalid Bangladesh mobile number: {phone}. Must be an 11-digit operator format (013-019).")
    return f"+8801{match.group(1)}"


def mask_phone_number(phone: str) -> str:
    """Masks a phone number for display/logging privacy e.g. +88017****1234."""
    try:
        norm = normalize_bd_phone(phone)
        return f"{norm[:6]}****{norm[-4:]}"
    except Exception:
        if len(phone) > 6:
            return f"{phone[:3]}****{phone[-3:]}"
        return "****"


def is_unicode_text(text: str) -> bool:
    """Checks if the message text contains non-GSM-7 characters (e.g. Bangla script)."""
    for ch in text:
        if ch not in GSM7_BASIC and ch not in GSM7_EXTENDED:
            return True
    return False


def count_sms_segments(text: str) -> dict[str, Any]:
    """Calculates SMS segment usage based on GSM-7 and Unicode telecommunication standards.
    
    Standards:
    - GSM 7-bit: 160 chars for 1 segment; 153 chars per segment if multi-part.
    - Unicode (Bangla): 70 chars for 1 segment; 67 chars per segment if multi-part.
    """
    if not text:
        return {"segments": 0, "chars": 0, "is_unicode": False, "max_single": 160}

    is_unicode = is_unicode_text(text)
    length = len(text)

    if is_unicode:
        if length <= 70:
            segments = 1
        else:
            segments = math.ceil(length / 67)
        max_single = 70
        concat_limit = 67
    else:
        # GSM-7 extended characters count as 2 chars
        effective_len = sum(2 if ch in GSM7_EXTENDED else 1 for ch in text)
        if effective_len <= 160:
            segments = 1
        else:
            segments = math.ceil(effective_len / 153)
        max_single = 160
        concat_limit = 153

    return {
        "segments": segments,
        "chars": length,
        "is_unicode": is_unicode,
        "max_single": max_single,
        "concat_limit": concat_limit,
    }


# ---------------------------------------------------------------------------
# Provider Implementations
# ---------------------------------------------------------------------------


class MockSmsProvider:
    """Deterministic mock provider for unit testing and offline development."""

    def __init__(self):
        self.sent_messages: list[dict[str, Any]] = []

    def send_sms(self, phone_number: str, message: str, sender_id: str | None = None) -> dict[str, Any]:
        norm = normalize_bd_phone(phone_number)
        seg_info = count_sms_segments(message)
        msg_id = f"mock_sms_{len(self.sent_messages) + 1}"
        record = {
            "provider_message_id": msg_id,
            "phone_number": norm,
            "message": message,
            "sender_id": sender_id,
            "segments": seg_info["segments"],
            "status": "delivered",
            "error": None,
        }
        self.sent_messages.append(record)
        logger.info(f"[MOCK SMS] Sent to {mask_phone_number(norm)}: {message[:60]}... ({seg_info['segments']} segs)")
        return record

    def parse_dlr_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        return {
            "provider_message_id": payload.get("message_id") or payload.get("sid"),
            "status": "delivered",
            "error": None,
        }


class SslWirelessSmsProvider:
    """Adapter for SSL Wireless Bulk SMS API (Bangladesh)."""

    def __init__(
        self,
        api_token: str | None = None,
        sid: str | None = None,
        api_url: str | None = None,
        timeout: float = 10.0,
    ):
        self.api_token = api_token or os.getenv("SSL_SMS_API_TOKEN") or os.getenv("SMS_API_KEY")
        self.sid = sid or os.getenv("SSL_SMS_SID") or os.getenv("SMS_SENDER_ID", "LexGOV AI")
        # SSL Wireless push API endpoint
        self.api_url = api_url or os.getenv("SSL_SMS_API_URL", "https://smsplus.sslwireless.com/api/v3/send-sms")
        self.timeout = timeout

    def send_sms(self, phone_number: str, message: str, sender_id: str | None = None) -> dict[str, Any]:
        norm = normalize_bd_phone(phone_number)
        seg_info = count_sms_segments(message)
        active_sid = sender_id or self.sid

        if not self.api_token:
            raise ValueError("SSL Wireless API Token is not configured.")

        # SSL Wireless API payload
        payload = {
            "api_token": self.api_token,
            "sid": active_sid,
            "msisdn": norm.replace("+", ""),  # SSL Wireless expects 8801XXXXXXXXX
            "sms": message,
            "csms_id": f"cos_{norm[-6:]}_{os.urandom(4).hex()}",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.api_url, json=payload)
                data = resp.json() if resp.status_code == 200 else {}
                
                # SSL Wireless returns status_code == 200 and status == "SUCCESS"
                if resp.status_code == 200 and data.get("status") == "SUCCESS":
                    sms_info = data.get("smsinfo", [{}])[0] if data.get("smsinfo") else {}
                    return {
                        "provider_message_id": sms_info.get("sms_id") or payload["csms_id"],
                        "status": "sent",
                        "segments": seg_info["segments"],
                        "error": None,
                    }
                else:
                    err_msg = data.get("error_message") or f"HTTP {resp.status_code}: {resp.text[:100]}"
                    return {
                        "provider_message_id": None,
                        "status": "failed",
                        "segments": seg_info["segments"],
                        "error": err_msg,
                    }
        except Exception as e:
            logger.error(f"SSL Wireless SMS failed: {e}")
            return {
                "provider_message_id": None,
                "status": "failed",
                "segments": seg_info["segments"],
                "error": str(e),
            }

    def parse_dlr_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        # SSL Wireless DLR payload: { "msisdn": ..., "sms_id": ..., "status": "DELIVRD" }
        status_raw = str(payload.get("status", "")).upper()
        status = "delivered" if status_raw in ("DELIVRD", "SUCCESS", "DELIVERED") else "failed"
        return {
            "provider_message_id": payload.get("sms_id") or payload.get("csms_id"),
            "status": status,
            "error": None if status == "delivered" else f"Provider status: {status_raw}",
        }


class GenericHttpSmsProvider:
    """Configurable HTTP-POST/GET SMS gateway for arbitrary BD aggregators (e.g. Onnorokom, Greenweb, Alpha)."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        sender_id: str | None = None,
        http_method: str = "POST",
        timeout: float = 10.0,
    ):
        self.api_url = api_url or os.getenv("SMS_API_URL")
        self.api_key = api_key or os.getenv("SMS_API_KEY")
        self.sender_id = sender_id or os.getenv("SMS_SENDER_ID", "LexGOV AI")
        self.http_method = http_method.upper()
        self.timeout = timeout

    def send_sms(self, phone_number: str, message: str, sender_id: str | None = None) -> dict[str, Any]:
        norm = normalize_bd_phone(phone_number)
        seg_info = count_sms_segments(message)
        active_sid = sender_id or self.sender_id

        if not self.api_url:
            raise ValueError("Generic SMS API URL is not configured.")

        params = {
            "api_key": self.api_key or "",
            "sender_id": active_sid,
            "to": norm,
            "message": message,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if self.http_method == "GET":
                    resp = client.get(self.api_url, params=params)
                else:
                    resp = client.post(self.api_url, json=params)

                if resp.status_code in (200, 201):
                    msg_id = resp.headers.get("x-message-id") or f"gen_{os.urandom(6).hex()}"
                    return {
                        "provider_message_id": msg_id,
                        "status": "sent",
                        "segments": seg_info["segments"],
                        "error": None,
                    }
                return {
                    "provider_message_id": None,
                    "status": "failed",
                    "segments": seg_info["segments"],
                    "error": f"HTTP {resp.status_code}: {resp.text[:100]}",
                }
        except Exception as e:
            return {
                "provider_message_id": None,
                "status": "failed",
                "segments": seg_info["segments"],
                "error": str(e),
            }

    def parse_dlr_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        status_val = str(payload.get("status", "")).lower()
        delivered = status_val in ("delivered", "success", "1")
        return {
            "provider_message_id": payload.get("message_id") or payload.get("id"),
            "status": "delivered" if delivered else "failed",
            "error": None if delivered else f"Status: {status_val}",
        }


# ---------------------------------------------------------------------------
# SMS Channel Adapter (Implements ChannelAdapter Protocol)
# ---------------------------------------------------------------------------


class SmsChannelAdapter:
    def __init__(
        self,
        provider: SmsProvider | None = None,
        is_masking: bool = False,
    ):
        self.is_masking = is_masking or (os.getenv("SMS_MASKING", "false").lower() == "true")
        
        provider_name = os.getenv("SMS_PROVIDER", "mock").lower()
        if provider:
            self.provider = provider
        elif provider_name == "ssl" and os.getenv("SSL_SMS_API_TOKEN"):
            self.provider = SslWirelessSmsProvider()
        elif provider_name == "generic" and os.getenv("SMS_API_URL"):
            self.provider = GenericHttpSmsProvider()
        else:
            self.provider = MockSmsProvider()

    def send(
        self,
        alert_id: str,
        recipient_address: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = metadata or {}
        sender_id = meta.get("sender_id")

        try:
            norm_phone = normalize_bd_phone(recipient_address)
        except ValueError as ve:
            return {
                "status": "rejected",
                "provider": "sms",
                "provider_message_id": None,
                "cost_estimate": 0.0,
                "segments": 0,
                "error": str(ve),
            }

        seg_info = count_sms_segments(body)
        cost_est = self.estimate_cost(body, norm_phone)["cost_estimate"]

        res = self.provider.send_sms(norm_phone, body, sender_id=sender_id)
        res["provider"] = "sms"
        res["cost_estimate"] = cost_est
        res["segments"] = seg_info["segments"]
        return res

    def parse_delivery_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        return self.provider.parse_dlr_webhook(payload, headers)

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "channel": "sms",
            "provider_type": self.provider.__class__.__name__,
            "masking": self.is_masking,
        }

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        seg_info = count_sms_segments(text)
        rate = 0.55 if self.is_masking else 0.35  # BDT per segment
        cost = round(seg_info["segments"] * rate, 2)
        return {
            "cost_estimate": cost,
            "segments": seg_info["segments"],
            "currency": "BDT",
            "is_unicode": seg_info["is_unicode"],
            "chars": seg_info["chars"],
        }
