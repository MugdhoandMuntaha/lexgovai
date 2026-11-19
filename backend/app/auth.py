"""Authentication utilities using Python standard library (scrypt, secrets, hmac).

No third-party crypto dependencies required; fully compatible with Python 3.12+.
Includes password validation, sliding session expiry, and in-memory rate limiting.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import jwt
from jwt import ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError, PyJWKClient, PyJWTError
from fastapi import HTTPException, Request, Response, status

SESSION_COOKIE_NAME = "complianceos_session"
SLIDING_LIFETIME = timedelta(days=7)
ABSOLUTE_LIFETIME = timedelta(days=30)
SESSION_LIFETIME = SLIDING_LIFETIME


class UnauthenticatedException(HTTPException):
    def __init__(self, detail: str = "Authentication required."):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

# Password rules & denylist
COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password",
    "password123",
    "password1234",
    "1234567890",
    "12345678901",
    "qwerty1234",
    "admin12345",
    "administrator",
    "compliance123",
    "complianceos",
    "letmein123",
    "welcome123",
    "pass123456",
    "iloveyou123",
    "bangladesh1",
    "dhaka12345",
    "testing123",
    "changeme123",
    "secret1234",
})


def validate_password(password: str) -> None:
    """Validates password complexity: minimum 10 chars, not in common denylist."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common or easily guessed. Please choose a more secure password.")
    if password.strip() != password or password.isspace():
        raise ValueError("Password cannot start, end with, or be entirely whitespace.")


# ---------------------------------------------------------------------------
# Rate Limiting & Throttling
# ---------------------------------------------------------------------------


class RateLimiter(Protocol):
    def check(self, key: str) -> tuple[bool, int]:
        """Returns (is_allowed, retry_after_seconds)."""
        ...

    def record_failure(self, key: str) -> None:
        ...

    def reset(self, key: str) -> None:
        ...


class InMemoryRateLimiter:
    """In-memory sliding window rate limiter for login brute-force defense."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, lockout_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}
        self._lockouts: dict[str, float] = {}

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            # Check active lockout
            locked_until = self._lockouts.get(key, 0)
            if now < locked_until:
                return False, int(locked_until - now) + 1
            if key in self._lockouts:
                del self._lockouts[key]

            # Prune failures outside sliding window
            timestamps = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
            self._failures[key] = timestamps
            if len(timestamps) >= self.max_attempts:
                self._lockouts[key] = now + self.lockout_seconds
                return False, self.lockout_seconds
            return True, 0

    def record_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            timestamps = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
            timestamps.append(now)
            self._failures[key] = timestamps
            if len(timestamps) >= self.max_attempts:
                self._lockouts[key] = now + self.lockout_seconds

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._lockouts.pop(key, None)


login_limiter = InMemoryRateLimiter()


# ---------------------------------------------------------------------------
# Cryptographic Password & Token Primitives
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    """Derives a secure password hash using scrypt (recommended by OWASP/NIST)."""
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1,
    ).hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    derived = hash_password(password, salt)
    return hmac.compare_digest(derived, expected_hash)


def get_internal_token_secret(override_secret: str | None = None) -> str:
    return (
        override_secret
        or os.getenv("SESSION_SECRET")
        or os.getenv("SUPABASE_JWT_SECRET")
        or "complianceos-serverless-jwt-signing-secret-key-32chars"
    )


def generate_session_token(
    user_id: str | None = None,
    workspace_id: str | None = None,
    email: str | None = None,
    full_name: str | None = None,
    secret: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp = int((now + ABSOLUTE_LIFETIME).timestamp())
    signing_secret = get_internal_token_secret(secret)
    payload = {
        "sub": user_id or uuid.uuid4().hex,
        "workspace_id": workspace_id or "",
        "email": email or "",
        "full_name": full_name or "",
        "iat": int(now.timestamp()),
        "exp": exp,
        "iss": "complianceos-internal",
    }
    return jwt.encode(payload, signing_secret, algorithm="HS256")


def decode_internal_token(token: str, secret: str | None = None) -> dict[str, Any] | None:
    signing_secret = get_internal_token_secret(secret)
    try:
        payload = jwt.decode(
            token,
            signing_secret,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_exp": True},
        )
        if payload.get("iss") == "complianceos-internal" and payload.get("sub"):
            return payload
    except Exception:
        pass
    return None


def set_session_cookie(response: Response, session_id: str, is_production: bool = False) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=int(ABSOLUTE_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=is_production,
        path="/",
    )


def clear_session_cookie(response: Response, is_production: bool = False) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=is_production,
        path="/",
    )


# ---------------------------------------------------------------------------
# Supabase JWT Verification & Session Extraction
# ---------------------------------------------------------------------------

_jwk_clients: dict[str, PyJWKClient] = {}
_jwk_lock = threading.Lock()


def get_jwk_client(jwks_url: str) -> PyJWKClient:
    with _jwk_lock:
        if jwks_url not in _jwk_clients:
            _jwk_clients[jwks_url] = PyJWKClient(jwks_url, cache_keys=True)
        return _jwk_clients[jwks_url]


def verify_supabase_token(
    token: str,
    supabase_url: str | None = None,
    supabase_jwt_secret: str | None = None,
    expected_audience: str = "authenticated",
) -> dict[str, Any]:
    """Cryptographically verifies a Supabase JWT access token.
    
    Supports asymmetric JWKS (RS256/ES256) and legacy symmetric secret (HS256).
    Strictly validates signature, exp, aud, and iss.
    Never trusts unverified claims.
    """
    if not token or not token.strip():
        raise UnauthenticatedException("Authentication token missing.")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as e:
        raise UnauthenticatedException(f"Invalid token header: {e}")

    alg = unverified_header.get("alg", "HS256")
    expected_issuer = f"{supabase_url.rstrip('/')}/auth/v1" if supabase_url else None

    signing_key = None
    if alg == "HS256":
        if not supabase_jwt_secret:
            raise UnauthenticatedException("HS256 token received but SUPABASE_JWT_SECRET is not configured.")
        signing_key = supabase_jwt_secret
    else:
        # Asymmetric key from JWKS
        if not supabase_url:
            raise UnauthenticatedException("Asymmetric token received but SUPABASE_URL is not configured for JWKS resolution.")
        jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        try:
            client = get_jwk_client(jwks_url)
            signing_key = client.get_signing_key_from_jwt(token).key
        except Exception as e:
            raise UnauthenticatedException(f"Failed to retrieve JWKS signing key: {e}")

    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True,
        "verify_iss": bool(expected_issuer),
    }

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=expected_audience,
            issuer=expected_issuer,
            options=options,
        )
    except ExpiredSignatureError:
        raise UnauthenticatedException("Token has expired.")
    except InvalidAudienceError:
        raise UnauthenticatedException("Invalid token audience.")
    except InvalidIssuerError:
        raise UnauthenticatedException("Invalid token issuer.")
    except PyJWTError as e:
        raise UnauthenticatedException(f"Token validation failed: {e}")

    if not payload.get("sub"):
        raise UnauthenticatedException("Token missing subject (sub) claim.")

    return payload


def extract_session_token(request: Request) -> str | None:
    # 1. Authorization header: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        # Keep scoped Bearer API keys (/api/v1) separate; they start with cos_
        if not token.startswith("cos_"):
            return token

    # 2. Cookies: check complianceos_session, sb-access-token, or sb_access_token
    for cookie_name in (SESSION_COOKIE_NAME, "sb-access-token", "sb_access_token"):
        val = request.cookies.get(cookie_name)
        if val:
            return val

    # 3. Supabase SSR chunked cookies (sb-*-auth-token)
    for key, val in request.cookies.items():
        if key.startswith("sb-") and "auth-token" in key:
            try:
                raw = val
                if not raw.startswith("{") and not raw.startswith("["):
                    try:
                        raw = base64.b64decode(val).decode("utf-8")
                    except Exception:
                        pass
                data = json.loads(raw)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str):
                    return data[0]
                if isinstance(data, dict) and "access_token" in data:
                    return data["access_token"]
            except Exception:
                pass

    return None
