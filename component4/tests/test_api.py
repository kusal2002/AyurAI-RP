"""Automated tests for the Component 4 API (authentication, RBAC, decisions, audit chain).

Run from the repository root:
    python -m unittest discover component4/tests -v

Uses a temporary SQLite database, so your real data is never touched, and sends
nothing to the blockchain (anchoring needs a live Sepolia connection).
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Configure a throwaway database and secrets BEFORE the API modules are imported
_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp.name) / 'test.sqlite3'}"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 52
os.environ["C4_SERVICE_API_KEY"] = "test-service-key"
os.environ["C2_NEO4J_URI"] = ""   # tests never contact Component 2's real graph

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import update  # noqa: E402

import main  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from models import AuditLog, User  # noqa: E402
from routers import federation_routes  # noqa: E402
from security import hash_password  # noqa: E402

PASSWORD = "test-password"


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SessionLocal() as db:
            for username, role, clinic in [
                ("practitioner.clinic1", "practitioner", "clinic-1"),
                ("practitioner.clinic2", "practitioner", "clinic-2"),
                ("supervisor", "supervisor", None),
                ("researcher", "researcher", None),
            ]:
                db.add(User(username=username, password_hash=hash_password(PASSWORD), role=role, clinic_id=clinic))
            db.commit()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        # Close the database connections so Windows can delete the temporary file
        engine.dispose()
        _tmp.cleanup()

    def auth(self, username):
        response = self.client.post("/api/v1/c4/auth/login", json={"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    # ---------- authentication (FR6, NFR security) ----------
    def test_health(self):
        self.assertEqual(self.client.get("/health").json()["status"], "healthy")

    def test_wrong_password_rejected(self):
        response = self.client.post("/api/v1/c4/auth/login", json={"username": "supervisor", "password": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_missing_token_rejected_within_500ms(self):
        start = time.perf_counter()
        response = self.client.get("/api/v1/c4/decisions")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertEqual(response.status_code, 401)
        self.assertLess(elapsed_ms, 500)   # NFR: reject unauthenticated calls within 500 ms

    def test_forged_token_rejected(self):
        response = self.client.get("/api/v1/c4/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
        self.assertEqual(response.status_code, 401)

    # ---------- decisions and role-based access (FR4, FR7) ----------
    def test_decisions_and_rbac(self):
        p1, p2 = self.auth("practitioner.clinic1"), self.auth("practitioner.clinic2")
        sup, res = self.auth("supervisor"), self.auth("researcher")

        r = self.client.post("/api/v1/c4/decisions", headers=p1, json={"case_ref": "CASE-T1", "decision": "approve"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["clinic_id"], "clinic-1")   # taken from the token, not the request

        r = self.client.post("/api/v1/c4/decisions", headers=p1, json={"case_ref": "CASE-T2", "decision": "reject"})
        self.assertEqual(r.status_code, 422)                   # rationale required for reject

        r = self.client.post("/api/v1/c4/decisions", headers=p2,
                             json={"case_ref": "CASE-T3", "decision": "reject", "rationale": "Mapping looks wrong"})
        self.assertEqual(r.status_code, 201)

        r = self.client.post("/api/v1/c4/decisions", headers=res, json={"case_ref": "CASE-T4", "decision": "approve"})
        self.assertEqual(r.status_code, 403)                   # researchers cannot decide

        r = self.client.post("/api/v1/c4/decisions", headers=p1, json={"case_ref": "<script>", "decision": "approve"})
        self.assertEqual(r.status_code, 422)                   # input validation

        mine = self.client.get("/api/v1/c4/decisions", headers=p1).json()
        self.assertTrue(all(d["clinic_id"] == "clinic-1" for d in mine))   # own clinic only
        everyone = self.client.get("/api/v1/c4/decisions", headers=sup).json()
        self.assertTrue({"clinic-1", "clinic-2"} <= {d["clinic_id"] for d in everyone})

        logs = self.client.get("/api/v1/c4/audit/logs", headers=sup).json()
        self.assertTrue(all("Mapping looks wrong" not in str(entry) for entry in logs))   # no free text in audit

    # ---------- service events ----------
    def test_service_event_requires_key(self):
        body = {"service": "component2", "event": "c2.reasoning.completed", "reference_id": "req-1"}
        self.assertEqual(self.client.post("/api/v1/c4/audit/events", json=body).status_code, 401)
        r = self.client.post("/api/v1/c4/audit/events", json=body, headers={"X-Service-Key": "test-service-key"})
        self.assertEqual(r.status_code, 201)

    # ---------- tamper-evident audit chain (FR8) ----------
    def test_zz_tampering_is_detected(self):
        # Named "zz" so it runs last: it deliberately corrupts the audit log
        sup = self.auth("supervisor")
        self.assertTrue(self.client.get("/api/v1/c4/audit/verify", headers=sup).json()["valid"])
        self.assertEqual(self.client.get("/api/v1/c4/audit/verify", headers=self.auth("practitioner.clinic1")).status_code, 403)

        with SessionLocal() as db:
            target = db.query(AuditLog).order_by(AuditLog.id).first()
            db.execute(update(AuditLog).where(AuditLog.id == target.id).values(action="auth.login_TAMPERED"))
            db.commit()
            tampered_id = target.id

        result = self.client.get("/api/v1/c4/audit/verify", headers=sup).json()
        self.assertFalse(result["valid"])
        self.assertEqual(result["first_invalid_id"], tampered_id)   # points at exactly the edited row

    # ---------- FAKL readiness check (read-only, counts only) ----------
    def test_fakl_status_requires_login_and_reports_configuration(self):
        self.assertEqual(self.client.get("/api/v1/c4/fakl/status").status_code, 401)
        status = self.client.get("/api/v1/c4/fakl/status", headers=self.auth("researcher")).json()
        self.assertFalse(status["configured"])          # no graph configured in tests
        self.assertFalse(status["connected"])
        self.assertIsNone(status["counts"])

    # ---------- federation results on a server without the dataset ----------
    def test_clinic_counts_used_when_dataset_missing(self):
        counts_file = Path(_tmp.name) / "clinic_counts.csv"
        counts_file.write_text("clinic_id,low,moderate,high,data_source\n1,5,6,7,test\n2,1,2,3,test\n3,0,0,9,test\n")
        with patch.object(federation_routes.fl_config, "FEATURES_FILE", None), \
             patch.object(federation_routes, "CLINIC_COUNTS_FILE", counts_file):
            config = self.client.get("/api/v1/c4/federation/config", headers=self.auth("researcher")).json()
        self.assertTrue(config["real_data"])
        self.assertEqual((config["clinics"][0]["low"], config["clinics"][0]["high"]), (5, 7))

    def test_timestamps_are_utc(self):
        sup = self.auth("supervisor")
        self.assertTrue(self.client.get("/api/v1/c4/audit/logs", headers=sup).json()[0]["timestamp"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
