"""Create the demo accounts (one practitioner per clinic, a supervisor, a researcher).

Usage:  python component4/api/seed_users.py --password <demo-password>
Demo accounts only — real deployments would register users properly.
"""

import argparse

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", required=True, help="password given to every demo account")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for username, role, clinic_id in DEMO_USERS:
            if db.scalars(select(User).where(User.username == username)).first():
                print(f"exists : {username}")
                continue
            db.add(User(username=username, password_hash=hash_password(args.password),
                        role=role, clinic_id=clinic_id))
            print(f"created: {username} ({role}, {clinic_id or 'all clinics'})")
        db.commit()
