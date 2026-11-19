"""Management CLI for LexGOV AI.

Usage:
    python -m app.cli create-user <email> <password> [--plan <plan>] [--name <name>]
    python -m app.cli set-plan <workspace_id_or_email> <plan_id>
    python -m app.cli purge-expired
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .auth import generate_salt, hash_password
from .config import get_settings
from .db import Database
from .entitlements import EntitlementService
from .plans import PLANS
from .subscriptions import SubscriptionService


def create_user_cmd(args: argparse.Namespace, db: Database, sub_svc: SubscriptionService) -> int:
    email = args.email.strip().lower()
    if db.get_user_by_email(email):
        print(f"Error: User with email '{email}' already exists.", file=sys.stderr)
        return 1

    plan = args.plan.lower()
    if plan not in PLANS:
        print(f"Error: Invalid plan '{plan}'. Allowed plans: {list(PLANS.keys())}", file=sys.stderr)
        return 1

    supabase_id = getattr(args, "supabase_id", None)
    if not args.password and not supabase_id:
        print("Error: Either password or --supabase-id must be provided.", file=sys.stderr)
        return 1

    if supabase_id:
        user, _ = db.get_or_create_supabase_user(supabase_id, email, args.name)
    else:
        salt = generate_salt()
        pw_hash = hash_password(args.password, salt)
        user = db.create_user(email=email, password_hash=pw_hash, salt=salt, full_name=args.name)
    workspace_name = f"{args.name or email}'s Workspace"
    workspace = db.create_workspace(name=workspace_name)
    db.create_membership(user_id=user["id"], workspace_id=workspace["id"], role="owner")

    # Create free subscription first, then upgrade if requested
    sub_svc.provision_free_subscription(workspace["id"])
    if plan != "free":
        sub_svc.change_plan(workspace["id"], plan)

    print(f"Created user: {user['id']} ({email})")
    print(f"Created workspace: {workspace['id']} ({workspace_name})")
    print(f"Plan: {plan}")
    return 0


def set_plan_cmd(args: argparse.Namespace, db: Database, sub_svc: SubscriptionService) -> int:
    target = args.workspace_id_or_email.strip()
    plan_id = args.plan_id.lower()
    if plan_id not in PLANS:
        print(f"Error: Invalid plan '{plan_id}'. Allowed plans: {list(PLANS.keys())}", file=sys.stderr)
        return 1

    workspace = None
    if "@" in target:
        user = db.get_user_by_email(target.lower())
        if not user:
            print(f"Error: No user found with email '{target}'.", file=sys.stderr)
            return 1
        workspace = db.get_user_workspace(user["id"])
        if not workspace:
            print(f"Error: User '{target}' has no associated workspace.", file=sys.stderr)
            return 1
    else:
        workspace = db.get_workspace(target)
        if not workspace:
            print(f"Error: Workspace '{target}' not found.", file=sys.stderr)
            return 1

    sub_svc.change_plan(workspace["id"], plan_id)
    print(f"Updated workspace {workspace['id']} ({workspace['name']}) to plan: {plan_id}")
    return 0


def grant_admin_cmd(args: argparse.Namespace, db: Database) -> int:
    target = args.email_or_user_id.strip()
    success = db.set_platform_admin(target, is_admin=True)
    if success:
        print(f"Granted platform admin privileges to: {target}")
        return 0
    print(f"Error: No user found matching '{target}'.", file=sys.stderr)
    return 1


def seed_demo_cmd(db: Database, sub_svc: SubscriptionService) -> int:
    plans = ["free", "starter", "growth", "professional"]
    for p in plans:
        email = f"demo_{p}@complianceos.com.bd"
        existing = db.get_user_by_email(email)
        if not existing:
            salt = generate_salt()
            pw_hash = hash_password("DemoPassword123!", salt)
            u = db.create_user(email=email, password_hash=pw_hash, salt=salt, full_name=f"Demo {p.capitalize()}")
            ws = db.create_workspace(name=f"Demo {p.capitalize()} Enterprise")
            db.create_membership(user_id=u["id"], workspace_id=ws["id"], role="owner")
            sub_svc.provision_free_subscription(ws["id"])
            if p != "free":
                sub_svc.change_plan(ws["id"], p)
            print(f"Seeded {p} demo user: {email}")
        else:
            print(f"{p} demo user already exists: {email}")

    # Seed platform admin demo user
    admin_email = "admin@complianceos.com.bd"
    existing_admin = db.get_user_by_email(admin_email)
    if not existing_admin:
        salt = generate_salt()
        pw_hash = hash_password("AdminPassword123!", salt)
        u = db.create_user(email=admin_email, password_hash=pw_hash, salt=salt, full_name="LexGOV AI Admin")
        ws = db.create_workspace(name="LexGOV AI Operations")
        db.create_membership(user_id=u["id"], workspace_id=ws["id"], role="owner")
        sub_svc.provision_free_subscription(ws["id"])
        sub_svc.change_plan(ws["id"], "professional")
        db.set_platform_admin(u["id"], is_admin=True)
        print(f"Seeded platform admin: {admin_email}")
    else:
        db.set_platform_admin(existing_admin["id"], is_admin=True)
        print(f"Platform admin updated: {admin_email}")

    # Seed sample news items if none exist
    if not db.list_news_items():
        db.create_news_item(
            title="NBR Gazettes SRO No. 182-Ain/2024 on Electronic VAT Filing",
            content="The National Board of Revenue has mandated electronic filing and 15-day reconciliation for registered freight forwarders and logistics providers operating in Bangladesh.",
            sector="Logistics & Freight",
            jurisdiction="Bangladesh",
            source_url="https://nbr.gov.bd/sro/2024/182",
            regulation_id="nbr-vat-sro-4.2",
        )
        db.create_news_item(
            title="Bangladesh Bank Issues Guidelines for Cross-Border E-Commerce Settlement",
            content="Authorized Dealers are instructed to adhere to the revised inward remittance and merchant settlement framework under FE Circular No. 14.",
            sector="E-commerce",
            jurisdiction="Bangladesh",
            source_url="https://bb.org.bd/circulars/2024/fe14",
        )
        db.create_news_item(
            title="Customs Modernization: Automated ASYCUDA World Harmonization",
            content="Chattogram Custom House transitions to automated risk profiling for designated HS codes, requiring digitized invoice attachments prior to bill of entry submission.",
            sector="Manufacturing & Trade",
            jurisdiction="Bangladesh",
            source_url="https://customs.gov.bd/notices/2024/asycuda",
        )
        print("Seeded sample regulatory news items.")

    print("Demo seeding complete.")
    return 0


def purge_expired_cmd(db: Database, entitlements: EntitlementService) -> int:
    workspaces = db.list_workspaces()
    total_purged = 0
    for ws in workspaces:
        cutoff = entitlements.retention_cutoff(ws["id"])
        if cutoff:
            count = db.purge_expired_action_plans(cutoff, ws["id"])
            if count > 0:
                print(f"Workspace {ws['id']} ({ws['name']}): purged {count} expired plans.")
            total_purged += count
    print(f"Purge complete: {total_purged} expired action plans removed across {len(workspaces)} workspaces.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LexGOV AI Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-user
    create_parser = subparsers.add_parser("create-user", help="Create a user, workspace, and subscription")
    create_parser.add_argument("email", help="User email address")
    create_parser.add_argument("password", nargs="?", default=None, help="User password (optional if --supabase-id is passed)")
    create_parser.add_argument("--supabase-id", default=None, help="Supabase User UUID to link")
    create_parser.add_argument("--plan", default="free", choices=list(PLANS.keys()), help="Initial subscription plan")
    create_parser.add_argument("--name", default=None, help="User full name")

    # set-plan
    set_plan_parser = subparsers.add_parser("set-plan", help="Set subscription plan for a workspace or user email")
    set_plan_parser.add_argument("workspace_id_or_email", help="Workspace ID or User email")
    set_plan_parser.add_argument("plan_id", choices=list(PLANS.keys()), help="Target plan ID")

    # purge-expired
    subparsers.add_parser("purge-expired", help="Purge expired action plans based on workspace retention policy")

    # grant-admin
    grant_parser = subparsers.add_parser("grant-admin", help="Grant platform admin privileges to a user")
    grant_parser.add_argument("email_or_user_id", help="User email address or user ID")

    # seed-demo
    subparsers.add_parser("seed-demo", help="Seed demo users for all plans plus platform admin")

    args = parser.parse_args(argv)
    settings = get_settings()
    db = Database(settings.storage_dir / "compliance.db")
    sub_svc = SubscriptionService(db)
    entitlements = EntitlementService(db)

    if args.command == "create-user":
        return create_user_cmd(args, db, sub_svc)
    elif args.command == "set-plan":
        return set_plan_cmd(args, db, sub_svc)
    elif args.command == "purge-expired":
        return purge_expired_cmd(db, entitlements)
    elif args.command == "grant-admin":
        return grant_admin_cmd(args, db)
    elif args.command == "seed-demo":
        return seed_demo_cmd(db, sub_svc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
