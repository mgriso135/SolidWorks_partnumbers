"""Create the first production administrator.

Run after migrations, from the backend directory:

    .venv/bin/python scripts/create_admin.py --email admin@example.com

The password can also be supplied with PARTCODE_ADMIN_PASSWORD. The script is
safe to re-run with --reset-password when an administrator needs a reset.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Tenant, User  # noqa: E402
from app.security import hash_password  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="Administrator email (prompted if omitted)")
    parser.add_argument("--password", help="Password (prompted if omitted; prefer the prompt)")
    parser.add_argument("--tenant-name", default="Default", help="Tenant display name")
    parser.add_argument("--tenant-slug", default="default", help="Tenant slug")
    parser.add_argument("--role", default="admin", choices=["admin", "editor", "viewer"])
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Update an existing user's password, role, and active flag",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    email = (args.email or input("Admin email: ")).strip().lower()
    if not email or "@" not in email:
        print("A valid email is required.", file=sys.stderr)
        return 2

    password = args.password or os.getenv("PARTCODE_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Admin password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match.", file=sys.stderr)
            return 2
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 2

    try:
        with SessionLocal() as db:
            tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant_slug))
            if tenant is None:
                tenant = Tenant(name=args.tenant_name, slug=args.tenant_slug)
                db.add(tenant)
                db.flush()

            user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
            if user is not None and not args.reset_password:
                print(
                    f"User {email} already exists in tenant {tenant.slug!r}. "
                    "Use --reset-password to update it.",
                    file=sys.stderr,
                )
                return 1

            if user is None:
                user = User(
                    tenant_id=tenant.id,
                    email=email,
                    password_hash=hash_password(password),
                    role=args.role,
                    active=True,
                )
                db.add(user)
            else:
                user.password_hash = hash_password(password)
                user.role = args.role
                user.active = True

            db.commit()
    except OperationalError as exc:
        print(
            "Database tables are missing or unreachable. Run `alembic upgrade head` first.\n"
            f"{exc}",
            file=sys.stderr,
        )
        return 1

    print(f"Administrator ready: {email} (tenant {args.tenant_slug}, role {args.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
