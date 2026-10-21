"""Create the demo accounts (one practitioner per clinic, a supervisor, a researcher).

Usage (from component4/api, or the c4-api container):
    python seed_users.py --password <demo-password>
    python seed_users.py                       # password from C4_SEED_PASSWORD
    python seed_users.py --reset-passwords     # also change existing accounts' passwords
    python seed_users.py --if-configured       # do nothing when no password is set (container start)

Safe to run again: existing accounts are kept unless --reset-passwords is given.
Demo accounts only — real deployments would register users properly.
"""

import argparse
import os
import sys

from sqlalchemy import select

from database import Base, SessionLocal, engine
from models import User
from security import hash_password

DEMO_USERS = [
    # (username, role, clinic_id)   clinic_id None = access to all clinics
    ("practitioner.clinic1", "practitioner", "clinic-1"),
    ("practitioner.clinic2", "practitioner", "clinic-2"),
    ("practitioner.clinic3", "practitioner", "clinic-3"),
    ("supervisor", "supervisor", None),
    ("researcher", "researcher", None),
]

MIN_PASSWORD_LENGTH = 8


def seed(password: str, reset_passwords: bool = False) -> dict[str, str]:
    """Create missing demo accounts. Returns {username: "created" | "reset" | "exists"}."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Seed password must be at least {MIN_PASSWORD_LENGTH} characters.")

    Base.metadata.create_all(bind=engine)
    results = {}
    with SessionLocal() as db:
        for username, role, clinic_id in DEMO_USERS:
            user = db.scalars(select(User).where(User.username == username)).first()
            if user is None:
                db.add(User(username=username, password_hash=hash_password(password),
                            role=role, clinic_id=clinic_id))
                results[username] = "created"
            elif reset_passwords:
                user.password_hash = hash_password(password)
                results[username] = "reset"
            else:
                results[username] = "exists"
        db.commit()
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create the Component 4 demo accounts.")
    parser.add_argument("--password", help="password given to every demo account "
                                           "(default: the C4_SEED_PASSWORD environment variable)")
    parser.add_argument("--reset-passwords", action="store_true",
                        help="also set this password on accounts that already exist")
    parser.add_argument("--if-configured", action="store_true",
                        help="exit quietly when no password is given or configured")
    args = parser.parse_args(argv)

    password = args.password or os.getenv("C4_SEED_PASSWORD", "")
    if not password:
        if args.if_configured:
            print("seed_users: C4_SEED_PASSWORD not set, skipping demo accounts")
            return 0
        parser.error("give --password or set C4_SEED_PASSWORD")

    try:
        results = seed(password, reset_passwords=args.reset_passwords)
    except ValueError as exc:
        print(f"seed_users: {exc}", file=sys.stderr)
        # On container start, a bad seed setting must not stop the API from starting
        return 0 if args.if_configured else 1

    roles = {username: (role, clinic) for username, role, clinic in DEMO_USERS}
    for username, outcome in results.items():
        role, clinic = roles[username]
        print(f"{outcome:7}: {username} ({role}, {clinic or 'all clinics'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
