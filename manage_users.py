#!/usr/bin/env python
"""LexGOV AI Database User Management Utility.

Usage:
  python manage_users.py list
  python manage_users.py create <email> <password> [--name "Full Name"] [--plan professional] [--admin]
  python manage_users.py reset-password <email> <new_password>
  python manage_users.py set-admin <email> [--revoke]
  python manage_users.py set-plan <email> <free|starter|growth|professional>
  python manage_users.py delete <email>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import auth
from app.config import get_settings
from app.db import Database
from app.subscriptions import SubscriptionService


def get_db_and_services():
    settings = get_settings()
    backend_db = BACKEND_DIR / "storage" / "compliance.db"
    if backend_db.exists():
        db_path = backend_db
    else:
        db_path = settings.storage_dir / "compliance.db"
        if not db_path.exists():
            print(f"[!] Database not found at {db_path}. Initializing...")
    db = Database(db_path)
    sub_svc = SubscriptionService(db)
    return db, sub_svc


def cmd_list(args):
    db, _ = get_db_and_services()
    users = db.list_all_users()
    if not users:
        print("[i] No users found in database.")
        return

    print("\n" + "=" * 105)
    print(f"{'Email':<32} {'Full Name':<22} {'Role':<10} {'Plan':<14} {'Admin':<7} {'Created At'}")
    print("=" * 105)
    for u in users:
        admin_badge = "YES" if u.get("is_platform_admin") else "no"
        email = u.get("email") or ""
        name = (u.get("full_name") or "-")[:20]
        role = u.get("role") or "owner"
        plan = u.get("plan_id") or "free"
        created = (u.get("created_at") or "")[:19]
        print(f"{email:<32} {name:<22} {role:<10} {plan:<14} {admin_badge:<7} {created}")
    print("=" * 105)
    print(f"Total: {len(users)} registered users\n")


def cmd_create(args):
    db, sub_svc = get_db_and_services()
    email = args.email.strip().lower()
    existing = db.get_user_by_email(email)
    if existing:
        print(f"[ERROR] User with email '{email}' already exists.")
        sys.exit(1)

    try:
        auth.validate_password(args.password)
    except ValueError as e:
        print(f"[ERROR] Password invalid: {e}")
        sys.exit(1)

    salt = auth.generate_salt()
    pwd_hash = auth.hash_password(args.password, salt)
    user = db.create_user(email, pwd_hash, salt, full_name=args.name)

    ws_name = f"{args.name or email.split('@')[0]}'s Workspace"
    ws = db.create_workspace(ws_name)
    db.create_membership(user["id"], ws["id"], role=args.role)
    sub_svc.ensure_free_subscription(ws["id"])
    if args.plan and args.plan != "free":
        sub_svc.change_plan(ws["id"], args.plan)

    if args.admin:
        db.set_platform_admin(user["id"], is_admin=True)

    print(f"[SUCCESS] User created successfully!")
    print(f"  Email:             {user['email']}")
    print(f"  Full Name:         {user.get('full_name') or '-'}")
    print(f"  Workspace:         {ws['name']} ({ws['id']})")
    print(f"  Role:              {args.role}")
    print(f"  Plan:              {args.plan}")
    print(f"  Platform Admin:    {'YES' if args.admin else 'NO'}")


def cmd_reset_password(args):
    db, _ = get_db_and_services()
    email = args.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        print(f"[ERROR] User '{email}' not found.")
        sys.exit(1)

    try:
        auth.validate_password(args.password)
    except ValueError as e:
        print(f"[ERROR] Password invalid: {e}")
        sys.exit(1)

    salt = auth.generate_salt()
    pwd_hash = auth.hash_password(args.password, salt)
    db.update_user_password(user["id"], pwd_hash, salt)
    print(f"[SUCCESS] Password for '{email}' has been reset.")


def cmd_set_admin(args):
    db, _ = get_db_and_services()
    email = args.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        print(f"[ERROR] User '{email}' not found.")
        sys.exit(1)

    is_admin = not args.revoke
    db.set_platform_admin(user["id"], is_admin=is_admin)
    status_str = "GRANTED" if is_admin else "REVOKED"
    print(f"[SUCCESS] Platform admin access {status_str} for '{email}'.")


def cmd_set_plan(args):
    db, sub_svc = get_db_and_services()
    email = args.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        print(f"[ERROR] User '{email}' not found.")
        sys.exit(1)

    ws = db.get_user_workspace(user["id"])
    if not ws:
        print(f"[ERROR] No workspace found for user '{email}'.")
        sys.exit(1)

    sub_svc.change_plan(ws["id"], args.plan)
    print(f"[SUCCESS] Plan for '{email}' (workspace '{ws['name']}') changed to '{args.plan}'.")


def cmd_delete(args):
    db, _ = get_db_and_services()
    email = args.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        print(f"[ERROR] User '{email}' not found.")
        sys.exit(1)

    confirm = input(f"Are you sure you want to permanently delete '{email}'? [y/N]: ")
    if confirm.strip().lower() == "y":
        db.delete_user(user["id"])
        print(f"[SUCCESS] User '{email}' deleted.")
    else:
        print("[CANCELLED] Deletion aborted.")


def main():
    parser = argparse.ArgumentParser(description="LexGOV AI User & Database Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all users in the database")

    # create
    p_create = subparsers.add_parser("create", help="Create a new user")
    p_create.add_argument("email", help="User email address")
    p_create.add_argument("password", help="User password (min 8 chars, 1 uppercase, 1 digit)")
    p_create.add_argument("--name", default=None, help="User full name")
    p_create.add_argument("--plan", default="free", choices=["free", "starter", "growth", "professional"])
    p_create.add_argument("--role", default="owner", choices=["owner", "admin", "analyst", "viewer"])
    p_create.add_argument("--admin", action="store_true", help="Grant platform admin privileges")

    # reset-password
    p_reset = subparsers.add_parser("reset-password", help="Reset password for an existing user")
    p_reset.add_argument("email", help="User email address")
    p_reset.add_argument("password", help="New password")

    # set-admin
    p_admin = subparsers.add_parser("set-admin", help="Grant or revoke platform admin privileges")
    p_admin.add_argument("email", help="User email address")
    p_admin.add_argument("--revoke", action="store_true", help="Revoke platform admin privileges")

    # set-plan
    p_plan = subparsers.add_parser("set-plan", help="Change a user workspace subscription plan")
    p_plan.add_argument("email", help="User email address")
    p_plan.add_argument("plan", choices=["free", "starter", "growth", "professional"])

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a user from the database")
    p_del.add_argument("email", help="User email address")

    args = parser.parse_args()

    dispatch = {
        "list": cmd_list,
        "create": cmd_create,
        "reset-password": cmd_reset_password,
        "set-admin": cmd_set_admin,
        "set-plan": cmd_set_plan,
        "delete": cmd_delete,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
