"""Tests for password reset and change-password functionality."""

from __future__ import annotations

import json
from fastapi.testclient import TestClient

from app.auth import hash_token


def _create_user(client: TestClient, email: str = "reset_test@lexgov.ai", password: str = "InitialPassword123!") -> dict:
    res = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "full_name": "Reset Test User"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_forgot_password_generic_response_on_nonexistent_email(client: TestClient):
    """Asserts that requesting a reset for a missing email does not leak account existence."""
    res = client.post("/api/auth/forgot-password", json={"email": "nobody_exists@lexgov.ai"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "instructions have been generated" in data["message"]
    assert data.get("reset_token") is None


def test_password_reset_end_to_end_flow(client: TestClient):
    """Tests the full forgot -> verify -> reset -> login flow."""
    email = "mugdho_reset_flow@lexgov.ai"
    old_pwd = "OldPassword123!"
    new_pwd = "NewBrandSecurePassword456!"

    _create_user(client, email=email, password=old_pwd)

    # 1. Request forgot password
    forgot_res = client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    token = forgot_res.json().get("reset_token")
    assert token is not None, "Reset token should be present in test/dev environment"

    # 2. Verify token
    verify_res = client.get(f"/api/auth/password-reset/verify?token={token}")
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["valid"] is True
    assert "mugdho" in vdata["email"] or "***@" in vdata["email"]

    # 3. Verify bad token returns 400
    bad_verify = client.get("/api/auth/password-reset/verify?token=fake_invalid_token_12345")
    assert bad_verify.status_code == 400

    # 4. Attempt reset with weak password (too short)
    weak_res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "short"})
    assert weak_res.status_code == 400
    assert "at least 10 characters" in weak_res.json()["detail"]

    # 5. Attempt reset with common password
    common_res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "password123"})
    assert common_res.status_code == 400
    assert "too common" in common_res.json()["detail"]

    # 6. Perform valid password reset
    reset_res = client.post("/api/auth/reset-password", json={"token": token, "new_password": new_pwd})
    assert reset_res.status_code == 200
    assert reset_res.json()["ok"] is True

    # 7. Attempting to reuse the token fails
    reuse_res = client.post("/api/auth/reset-password", json={"token": token, "new_password": new_pwd})
    assert reuse_res.status_code == 400
    assert "already been used" in reuse_res.json()["detail"]

    # 8. Login with old password fails
    old_login = client.post("/api/auth/login", json={"email": email, "password": old_pwd})
    assert old_login.status_code == 401

    # 9. Login with new password succeeds
    new_login = client.post("/api/auth/login", json={"email": email, "password": new_pwd})
    assert new_login.status_code == 200
    assert new_login.json()["user"]["email"] == email


def test_change_password_authenticated(client: TestClient):
    """Tests authenticated password change from settings."""
    email = "mugdho_change_pwd@lexgov.ai"
    pwd1 = "InitialPassword123!"
    pwd2 = "UpdatedPassword789!"

    _create_user(client, email=email, password=pwd1)

    # 1. Change password with wrong current password
    wrong_curr = client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongPassword123!", "new_password": pwd2},
    )
    assert wrong_curr.status_code == 400
    assert "Current password is incorrect" in wrong_curr.json()["detail"]

    # 2. Change password with identical new password
    same_pwd = client.post(
        "/api/auth/change-password",
        json={"current_password": pwd1, "new_password": pwd1},
    )
    assert same_pwd.status_code == 400
    assert "cannot be identical" in same_pwd.json()["detail"]

    # 3. Change password with too short password
    short_pwd = client.post(
        "/api/auth/change-password",
        json={"current_password": pwd1, "new_password": "short"},
    )
    assert short_pwd.status_code == 400
    assert "at least 10 characters" in short_pwd.json()["detail"]

    # 4. Valid password change
    valid_change = client.post(
        "/api/auth/change-password",
        json={"current_password": pwd1, "new_password": pwd2},
    )
    assert valid_change.status_code == 200
    assert valid_change.json()["ok"] is True

    # 5. Subsequent attempt using old password fails
    subsequent = client.post(
        "/api/auth/change-password",
        json={"current_password": pwd1, "new_password": "AnotherPassword999!"},
    )
    assert subsequent.status_code == 400
    assert "Current password is incorrect" in subsequent.json()["detail"]
