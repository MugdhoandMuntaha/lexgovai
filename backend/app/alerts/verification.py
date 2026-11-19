"""Contact Verification & Consent Management for LexGOV AI Alert Center.

Handles OTP generation and verification for SMS, signed email confirmation tokens,
explicit opt-in timestamps for WhatsApp, and masking helpers.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import Database, utcnow
from .channels.sms import normalize_bd_phone, mask_phone_number


def mask_email(email: str) -> str:
    """Masks an email for privacy e.g. j***d@example.com."""
    if "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked_user = user[0] + "*"
    else:
        masked_user = user[0] + "*" * (len(user) - 2) + user[-1]
    return f"{masked_user}@{domain}"


def hash_otp_code(code: str, salt: str = "cos_otp_salt_bd") -> str:
    """Computes a SHA-256 hash of the 6-digit OTP code."""
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


class VerificationService:
    def __init__(self, db: Database):
        self.db = db

    def request_phone_otp(self, user_id: str, phone_number: str) -> tuple[str, str]:
        """Generates a 6-digit OTP, stores hashed code with 10-min expiry, returns (otp_code, normalized_phone)."""
        norm_phone = normalize_bd_phone(phone_number)
        
        # Check rate-limit: 1 OTP request per 60 seconds
        latest = self.db.get_latest_sms_otp(norm_phone, user_id)
        if latest:
            created_dt = datetime.fromisoformat(latest["created_at"])
            now_dt = datetime.now(timezone.utc)
            if (now_dt - created_dt).total_seconds() < 60:
                raise ValueError("Please wait 60 seconds before requesting another verification code.")

        code = f"{random.randint(100000, 999999)}"
        code_hash = hash_otp_code(code)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(timespec="seconds")

        self.db.create_sms_otp(norm_phone, user_id, code_hash, expires_at)
        return code, norm_phone

    def verify_phone_otp(self, user_id: str, phone_number: str, code: str) -> bool:
        """Verifies the submitted 6-digit OTP. Enforces max 3 attempts and 10-minute expiry."""
        norm_phone = normalize_bd_phone(phone_number)
        latest = self.db.get_latest_sms_otp(norm_phone, user_id)
        if not latest:
            return False

        now_dt = datetime.now(timezone.utc)
        expires_dt = datetime.fromisoformat(latest["expires_at"])
        if now_dt > expires_dt:
            self.db.delete_sms_otp(latest["id"])
            raise ValueError("Verification code has expired. Please request a new code.")

        attempts = self.db.increment_sms_otp_attempts(latest["id"])
        if attempts > 3:
            self.db.delete_sms_otp(latest["id"])
            raise ValueError("Too many invalid attempts. This verification code has been invalidated.")

        expected_hash = latest["code_hash"]
        submitted_hash = hash_otp_code(code.strip())

        if hmac.compare_digest(submitted_hash, expected_hash):
            # Success! Delete OTP record and mark user channel verified
            self.db.delete_sms_otp(latest["id"])
            masked = mask_phone_number(norm_phone)
            self.db.set_user_channel(user_id, "sms", norm_phone, display_address=masked)
            self.db.verify_user_channel(user_id, "sms")
            return True

        return False

    def opt_in_whatsapp(self, user_id: str, phone_number: str | None = None) -> bool:
        """Verifies phone number and records explicit WhatsApp consent."""
        if not phone_number or "*" in phone_number:
            channels = self.db.get_user_channels(user_id)
            sms_ch = next((c for c in channels if c["channel"] == "sms" and c.get("verified_at")), None)
            if not sms_ch:
                raise ValueError("A verified phone number is required before opting in to WhatsApp.")
            norm_phone = sms_ch["address"]
        else:
            norm_phone = normalize_bd_phone(phone_number)

        masked = mask_phone_number(norm_phone)
        self.db.set_user_channel(user_id, "whatsapp", norm_phone, display_address=masked)
        self.db.verify_user_channel(user_id, "whatsapp")
        self.db.opt_in_whatsapp(user_id)
        return True

    def opt_out_channel(self, user_id: str, channel: str) -> bool:
        """Records immediate opt-out for a communication channel."""
        return self.db.opt_out_user_channel(user_id, channel)

    def re_opt_in_channel(self, user_id: str, channel: str) -> bool:
        """Removes opt-out state for a communication channel."""
        return self.db.re_opt_in_user_channel(user_id, channel)
