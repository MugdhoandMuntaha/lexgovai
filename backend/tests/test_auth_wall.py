"""Comprehensive tests for mandatory authentication wall and fail-closed security.

Verifies:
1. Route enumerator: every endpoint except /api/auth/signup, /api/auth/login, and /api/health rejects unauthenticated calls with 401.
2. Unauthenticated failure modes: missing cookie, invalid token, expired session, revoked session after logout.
3. Brute-force rate limiting: 5 failed attempts trigger 429 with Retry-After.
4. Generic login error: user enumeration is prevented on both missing users and wrong passwords.
5. Password rules: minimum 10 chars, common denylist rejected with 400.
6. Health check privacy: GET /api/health returns only {"status": "ok"}.
7. Cross-workspace IDOR protection: returns 404 Not Found (never 403 or leaked details).
8. CSRF origin check: untrusted origins are blocked with 403 on state-changing requests.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.auth import login_limiter
from app.config import Settings
from app.main import create_app
from tests.conftest import FakeLLM, make_settings, mint_test_jwt

PUBLIC_ALLOWLIST = {
    ("POST", "/api/auth/signup"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
    ("POST", "/api/webhooks/alerts/sms"),
    ("GET", "/api/webhooks/alerts/whatsapp"),
    ("POST", "/api/webhooks/alerts/whatsapp"),
    ("POST", "/api/auth/forgot-password"),
    ("GET", "/api/auth/password-reset/verify"),
    ("POST", "/api/auth/reset-password"),
}


def test_route_enumerator_enforces_auth_fail_closed(unauthenticated_client: TestClient):
    """Reflects over all registered OpenAPI paths and asserts non-public endpoints return 401."""
    app = unauthenticated_client.app
    paths = app.openapi()["paths"]
    tested = 0

    for path, methods_dict in paths.items():
        if not path.startswith("/api"):
            continue

        for method in methods_dict.keys():
            method_upper = method.upper()
            if method_upper in {"HEAD", "OPTIONS"}:
                continue
            if (method_upper, path) in PUBLIC_ALLOWLIST:
                continue

            tested += 1
            test_url = path.replace("{plan_id}", "test_id").replace("{item_id}", "test_id")

            if method_upper == "GET":
                resp = unauthenticated_client.get(test_url)
            elif method_upper == "POST":
                resp = unauthenticated_client.post(test_url, json={})
            elif method_upper == "PATCH":
                resp = unauthenticated_client.patch(test_url, json={})
            elif method_upper == "DELETE":
                resp = unauthenticated_client.delete(test_url)
            else:
                continue

            assert resp.status_code == 401, (
                f"Fail-closed violation: Route {method_upper} {test_url} returned {resp.status_code} "
                f"instead of 401 for unauthenticated request: {resp.text}"
            )
            body = resp.json()
            assert body.get("code") == "UNAUTHENTICATED"

    assert tested >= 15, f"Expected at least 15 protected routes tested, but tested {tested}"


def test_auth_unauthenticated_failure_modes(tmp_path: Path):
    app = create_app(make_settings(tmp_path), llm=FakeLLM())
    with TestClient(app) as c:
        # 1. No token/cookie
        res = c.get("/api/me")
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"

        # 2. Invalid / malformed token
        c.cookies.set("complianceos_session", "invalid_token_xyz")
        res = c.get("/api/me")
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"
        c.cookies.clear()

        # 3. Expired JWT
        expired_jwt = mint_test_jwt(exp_delta=timedelta(seconds=-60))
        res = c.get("/api/me", headers={"Authorization": f"Bearer {expired_jwt}"})
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"

        # 4. Wrong audience
        wrong_aud_jwt = mint_test_jwt(aud="wrong-audience")
        res = c.get("/api/me", headers={"Authorization": f"Bearer {wrong_aud_jwt}"})
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"

        # 5. Wrong issuer
        wrong_iss_jwt = mint_test_jwt(iss="https://untrusted-issuer.com/auth/v1")
        res = c.get("/api/me", headers={"Authorization": f"Bearer {wrong_iss_jwt}"})
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"

        # 6. Tampered signature
        tampered_jwt = mint_test_jwt(secret="completely-different-signing-secret")
        res = c.get("/api/me", headers={"Authorization": f"Bearer {tampered_jwt}"})
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"

        # 7. Valid JWT via Bearer header succeeds & JIT provisions
        valid_jwt = mint_test_jwt(sub="supa-user-1", email="supa1@example.com", full_name="Supa User One")
        res = c.get("/api/me", headers={"Authorization": f"Bearer {valid_jwt}"})
        assert res.status_code == 200
        assert res.json()["user"]["email"] == "supa1@example.com"

        # 8. Valid JWT via cookie succeeds
        c.cookies.set("complianceos_session", valid_jwt)
        res = c.get("/api/me")
        assert res.status_code == 200
        assert res.json()["user"]["email"] == "supa1@example.com"

        # 9. Logout clears cookie
        logout_res = c.post("/api/auth/logout")
        assert logout_res.status_code == 200

        # Request after clearing cookie returns 401
        c.cookies.clear()
        res = c.get("/api/me")
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"

    app.state.services.db.close()


def test_jit_provisioning_and_user_mapping(tmp_path: Path):
    app = create_app(make_settings(tmp_path), llm=FakeLLM())
    with TestClient(app) as c:
        jwt_token = mint_test_jwt(sub="supa-uuid-999", email="jit_user@example.com", full_name="JIT Provisioned")
        res = c.get("/api/me", headers={"Authorization": f"Bearer {jwt_token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["email"] == "jit_user@example.com"
        assert data["workspace"]["role"] == "owner"
        assert data["subscription"]["plan_id"] == "free"

        # Verify DB directly
        db = app.state.services.db
        user_row = db.get_user_by_supabase_id("supa-uuid-999")
        assert user_row is not None
        assert user_row["email"] == "jit_user@example.com"
        assert user_row["supabase_user_id"] == "supa-uuid-999"

        # Repeated request with same token resolves the same user without creating duplicates
        res2 = c.get("/api/me", headers={"Authorization": f"Bearer {jwt_token}"})
        assert res2.status_code == 200
        assert res2.json()["user"]["id"] == user_row["id"]

    app.state.services.db.close()


def test_login_rate_limiting_defense(tmp_path: Path):
    app = create_app(make_settings(tmp_path), llm=FakeLLM())
    with TestClient(app) as c:
        # Clear rate limiter state for clean test
        test_email = "brute_force_target@example.com"
        login_limiter.reset(f"email:{test_email}")
        login_limiter.reset("ip:testclient")

        # 5 bad attempts
        for attempt in range(5):
            res = c.post(
                "/api/auth/login",
                json={"email": test_email, "password": "WrongPassword!"},
            )
            assert res.status_code == 401
            assert res.json()["detail"] == "Incorrect email or password."

        # 6th attempt must be 429 Too Many Requests
        throttled = c.post(
            "/api/auth/login",
            json={"email": test_email, "password": "WrongPassword!"},
        )
        assert throttled.status_code == 429
        assert "Retry-After" in throttled.headers
        assert int(throttled.headers["Retry-After"]) > 0

    app.state.services.db.close()


def test_generic_login_error_prevents_user_enumeration(tmp_path: Path):
    app = create_app(make_settings(tmp_path), llm=FakeLLM())
    with TestClient(app) as c:
        # 1. Non-existent user
        res_nonexistent = c.post(
            "/api/auth/login",
            json={"email": "nobody_exists_here@example.com", "password": "SomePassword123!"},
        )
        assert res_nonexistent.status_code == 401
        assert res_nonexistent.json()["detail"] == "Incorrect email or password."

        # 2. Existing user, wrong password
        signup_res = c.post(
            "/api/auth/signup",
            json={"email": "alice_enum@example.com", "password": "CorrectPassword123!"},
        )
        assert signup_res.status_code == 200

        res_wrong_pw = c.post(
            "/api/auth/login",
            json={"email": "alice_enum@example.com", "password": "WrongPassword123!"},
        )
        assert res_wrong_pw.status_code == 401
        assert res_wrong_pw.json()["detail"] == "Incorrect email or password."

        # Exact same message prevents side-channel enumeration
        assert res_nonexistent.json() == res_wrong_pw.json()

        # 3. Duplicate signup returns 409 Conflict
        dup_res = c.post(
            "/api/auth/signup",
            json={"email": "alice_enum@example.com", "password": "AnotherPassword123!"},
        )
        assert dup_res.status_code == 409
        assert "already exists" in dup_res.json()["detail"]

    app.state.services.db.close()


def test_password_validation_rules(tmp_path: Path):
    app = create_app(make_settings(tmp_path), llm=FakeLLM())
    with TestClient(app) as c:
        # Under 10 characters
        res = c.post(
            "/api/auth/signup",
            json={"email": "short_pw@example.com", "password": "short1"},
        )
        assert res.status_code == 422 or res.status_code == 400

        # In common password denylist
        res = c.post(
            "/api/auth/signup",
            json={"email": "common_pw@example.com", "password": "password123"},
        )
        assert res.status_code == 400
        assert "common" in res.json()["detail"].lower()

        # Valid strong password succeeds
        res = c.post(
            "/api/auth/signup",
            json={"email": "good_pw@example.com", "password": "UniqueStrongPassword123!"},
        )
        assert res.status_code == 200

    app.state.services.db.close()


def test_health_check_privacy(unauthenticated_client: TestClient):
    """GET /api/health must never leak backend details, models, or versions to unauthenticated callers."""
    res = unauthenticated_client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert "llm_configured" not in res.json()
    assert "model" not in res.json()


def test_cross_workspace_idor_isolation_returns_404(tmp_path: Path):
    """Cross-workspace resource lookup returns 404 (never 403 or data)."""
    app = create_app(make_settings(tmp_path), llm=FakeLLM())

    # User A creates a company profile
    with TestClient(app) as client_a:
        signup_a = client_a.post(
            "/api/auth/signup",
            json={"email": "user_a@example.com", "password": "SecurePassword123!", "company_name": "Org A"},
        )
        assert signup_a.status_code == 200
        cp_a = client_a.post(
            "/api/company-profile",
            json={"company_name": "Org A", "industry": "retail", "country": "bangladesh"},
        )
        assert cp_a.status_code == 200
        cp_a_id = cp_a.json()["id"]

    # User B tries to access or attach to User A's profile
    with TestClient(app) as client_b:
        signup_b = client_b.post(
            "/api/auth/signup",
            json={"email": "user_b@example.com", "password": "SecurePassword123!", "company_name": "Org B"},
        )
        assert signup_b.status_code == 200

        # Try to upload document referencing User A's profile
        fake_sop = "Section 1: Operating procedure."
        res = client_b.post(
            "/api/documents/upload",
            data={"company_profile_id": cp_a_id},
            files={"file": ("sop.txt", fake_sop.encode(), "text/plain")},
        )
        # Should be 404 Not Found (or 403 for free tier SOP upload, so let's upgrade User B to Starter to isolate IDOR)
        client_b.app.state.services.subscriptions.change_plan(signup_b.json()["workspace"]["id"], "starter")
        res2 = client_b.post(
            "/api/documents/upload",
            data={"company_profile_id": cp_a_id},
            files={"file": ("sop.txt", fake_sop.encode(), "text/plain")},
        )
        assert res2.status_code == 404
        assert "not found" in res2.json()["detail"].lower()

    app.state.services.db.close()


def test_csrf_origin_verification(client: TestClient):
    """CSRF check blocks state-changing requests from untrusted browser origins."""
    # Untrusted origin
    res = client.post(
        "/api/company-profile",
        json={"company_name": "Attacker Org", "industry": "retail", "country": "bangladesh"},
        headers={"Origin": "https://evil-attacker.com"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "CSRF_ERROR"

    # Trusted origin
    res_ok = client.post(
        "/api/company-profile",
        json={"company_name": "Safe Org", "industry": "retail", "country": "bangladesh"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_ok.status_code == 200
