"""Tests for the demo-account seeder (component4/api/seed_users.py).

Run from the repository root:
    python -m unittest discover component4/tests -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# A throwaway database, configured BEFORE the API modules are imported. If another
# test module imported them first, the seeder simply shares that temporary database.
_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(_tmp.name) / 'seed.sqlite3'}")
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 52)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from sqlalchemy import delete, select  # noqa: E402

import seed_users  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from models import User  # noqa: E402
from security import verify_password  # noqa: E402

DEMO_NAMES = [name for name, _, _ in seed_users.DEMO_USERS]


def stored_hash(username):
    with SessionLocal() as db:
        return db.scalars(select(User.password_hash).where(User.username == username)).one()


class SeedUsersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # test_api.py deletes its temporary folder when it finishes; when this module
        # shares that database, recreate the folder and tables before running.
        Path(engine.url.database).parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        # Close connections so Windows can delete the temporary file
        engine.dispose()

    def setUp(self):
        # Start every test without the demo accounts (other tests' users are left alone)
        with SessionLocal() as db:
            db.execute(delete(User).where(User.username.in_(DEMO_NAMES)))
            db.commit()

    def test_creates_all_demo_accounts_with_roles(self):
        results = seed_users.seed("first-password")
        self.assertEqual(set(results.values()), {"created"})
        with SessionLocal() as db:
            users = {u.username: u for u in db.scalars(select(User).where(User.username.in_(DEMO_NAMES)))}
        for username, role, clinic in seed_users.DEMO_USERS:
            self.assertEqual(users[username].role, role)
            self.assertEqual(users[username].clinic_id, clinic)
            self.assertTrue(verify_password("first-password", users[username].password_hash))

    def test_second_run_keeps_existing_passwords(self):
        seed_users.seed("first-password")
        results = seed_users.seed("other-password")
        self.assertEqual(set(results.values()), {"exists"})
        self.assertTrue(verify_password("first-password", stored_hash("supervisor")))

    def test_reset_passwords_changes_existing_accounts(self):
        seed_users.seed("first-password")
        results = seed_users.seed("new-password", reset_passwords=True)
        self.assertEqual(set(results.values()), {"reset"})
        self.assertTrue(verify_password("new-password", stored_hash("researcher")))

    def test_short_password_is_refused(self):
        with self.assertRaises(ValueError):
            seed_users.seed("short")

    def test_if_configured_skips_without_password(self):
        old = os.environ.pop("C4_SEED_PASSWORD", None)
        try:
            self.assertEqual(seed_users.main(["--if-configured"]), 0)
        finally:
            if old is not None:
                os.environ["C4_SEED_PASSWORD"] = old
        with SessionLocal() as db:
            self.assertIsNone(db.scalars(select(User).where(User.username == "supervisor")).first())

    def test_short_password_on_container_start_does_not_block_api(self):
        # --if-configured is used before uvicorn starts: it must exit 0 so the API still runs
        self.assertEqual(seed_users.main(["--if-configured", "--password", "short"]), 0)
        self.assertEqual(seed_users.main(["--password", "short"]), 1)

    def test_password_from_environment(self):
        os.environ["C4_SEED_PASSWORD"] = "env-password"
        try:
            self.assertEqual(seed_users.main([]), 0)
        finally:
            del os.environ["C4_SEED_PASSWORD"]
        self.assertTrue(verify_password("env-password", stored_hash("practitioner.clinic1")))


if __name__ == "__main__":
    unittest.main()
