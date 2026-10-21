"""Patient registration (name, phone), access control, doctor-review routes and PDF reports.

ISOLATED: every data path points at a temporary folder (test_intake_workflow.IsolatedDatasets) and the personal-data
database is a temporary file. All names and numbers are fictional. The API runs under uvicorn in a background thread
and is called over real HTTP; Component 4 is a local stub of GET /auth/me.

Run from repository root:
    python -m unittest component1.tests.test_patient_records -v
"""

import json
import re
import socket
import sqlite3
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import uvicorn
from fastapi import HTTPException
from starlette.requests import Request

from component1.acquisition.ppg import capture_live_ppg
from component1.api import intake, patient_records, server
from component1.reports import pdf_report
from component1.tests.test_intake_workflow import (
    COMMON_NO_SAFETY, FakeEsp32, IsolatedDatasets, questionnaire_body, upload, wait_for_job,
)

NAME, PHONE = "Kamala Test-Fictional", "077 123 4567"
C4_USERS = {  # token -> Component 4 /auth/me answer (fictional accounts)
    "tok-prac-1": {"username": "practitioner.clinic1", "role": "practitioner", "clinic_id": "clinic-1"},
    "tok-prac-2": {"username": "practitioner.clinic2", "role": "practitioner", "clinic_id": "clinic-2"},
    "tok-super": {"username": "supervisor", "role": "supervisor", "clinic_id": None},
    "tok-research": {"username": "researcher", "role": "researcher", "clinic_id": None},
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class StubC4(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        token = self.headers.get("Authorization", "")[7:]
        user = C4_USERS.get(token)
        self.send_response(200 if user else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(user or {"detail": "invalid token"}).encode())

    def log_message(self, *args):
        pass


def call(base, method, path, body=None, headers=None):
    request = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw, status, kind, info = response.read(), response.status, response.headers.get("Content-Type", ""), response.headers
    except urllib.error.HTTPError as error:
        raw, status, kind, info = error.read(), error.code, error.headers.get("Content-Type", ""), error.headers
    return status, (json.loads(raw) if "json" in kind else raw), info


def text_of(pdf: bytes) -> str:
    """Uncompressed, Helvetica-encoded PDF -> searchable text: every shown string, joined (wrapped lines rejoin)."""
    raw = pdf.decode("latin-1")
    pieces = re.findall(r"\(((?:\\.|[^\\)])*)\)\s*Tj", raw)
    return " ".join(piece.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\") for piece in pieces)


class PatientRecords(IsolatedDatasets):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pii = cls.root / "c1_patient_identity.sqlite3"
        cls.extra = [mock.patch.object(patient_records, "PII_DB_PATH", cls.pii),
                     mock.patch.object(patient_records, "C4_AUTH_ME_URL", "")]
        for patcher in cls.extra:
            patcher.start()
        cls.c4 = HTTPServer(("127.0.0.1", free_port()), StubC4)
        threading.Thread(target=cls.c4.serve_forever, daemon=True).start()
        patient_records.C4_AUTH_ME_URL = f"http://127.0.0.1:{cls.c4.server_port}/api/v1/c4/auth/me"
        cls.api = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=free_port(), log_level="warning"))
        threading.Thread(target=cls.api.run, daemon=True).start()
        while not cls.api.started:
            time.sleep(0.05)
        cls.base = f"http://127.0.0.1:{cls.api.config.port}"

    @classmethod
    def tearDownClass(cls):
        cls.api.should_exit = True
        cls.c4.shutdown()
        for patcher in cls.extra:
            patcher.stop()
        super().tearDownClass()

    def mode(self, value):
        patcher = mock.patch.object(patient_records, "ACCESS_MODE", value)
        patcher.start()
        self.addCleanup(patcher.stop)
        patient_records._token_cache.clear()

    def register(self, name=NAME, phone=PHONE, request_id=None, headers=None):
        return call(self.base, "POST", "/api/c1/patients/register",
                    {"request_id": request_id or uuid.uuid4().hex, "full_name": name, "phone": phone}, headers)

    # ---------------------------------------------------------------- validation

    def test_name_and_phone_validation(self):
        for name in ("Nimal Perera", "A. Silva-Fernando", "O'Neil Jayasuriya", "නිමල් පෙරේරා", "குமார் ராஜா"):
            self.assertTrue(patient_records.normalise_name(name))
        self.assertEqual(patient_records.normalise_name("  Nimal    Perera "), "Nimal Perera")
        for bad in ("", "A", "Nimal 2", "x" * 101, "Nimal@Perera", "--"):
            with self.assertRaises(ValueError):
                patient_records.normalise_name(bad)
        cases = {"077 123 4567": "+94771234567", "0771234567": "+94771234567", "+94 77 123 4567": "+94771234567",
                 "94771234567": "+94771234567", "0094 77 123 4567": "+94771234567", "011-234-5678": "+94112345678",
                 "+44 20 7946 0958": "+442079460958", "+1 (415) 555-0100": "+14155550100"}
        for raw, e164 in cases.items():
            self.assertEqual(patient_records.normalise_phone(raw), e164, raw)
        for bad in ("", "12345", "077 123 456", "+94 77 123 45678", "phone", "+0123456789", "+1234567890123456"):
            with self.assertRaises(ValueError):
                patient_records.normalise_phone(bad)
        self.assertEqual(patient_records.display_phone("+94771234567"), "+94 77 123 4567")

    # ---------------------------------------------------------------- access control

    def test_off_mode_disables_every_personal_data_route(self):
        self.mode("off")
        self.assertEqual(call(self.base, "GET", "/api/c1/patient-data/status")[1]["enabled"], False)
        sid = intake.create_session()["session_id"]
        for method, path in (("POST", "/api/c1/patients/register"), ("GET", f"/api/c1/sessions/{sid}/patient"),
                             ("PUT", f"/api/c1/sessions/{sid}/patient"), ("GET", "/api/c1/doctor/sessions"),
                             ("GET", f"/api/c1/doctor/sessions/{sid}/report"), ("GET", f"/api/c1/doctor/sessions/{sid}/report.pdf")):
            status, body, _ = call(self.base, method, path, {"full_name": NAME, "phone": PHONE} if method != "GET" else None)
            self.assertEqual(status, 503, path)
            self.assertIn("disabled", body["detail"])

    def test_local_dev_mode_only_answers_this_computer(self):
        self.mode("local_dev")
        self.assertEqual(self.register()[0], 201)
        for headers in ({"X-Forwarded-For": "203.0.113.9"}, {"X-Real-IP": "203.0.113.9"}, {"Forwarded": "for=203.0.113.9"},
                        {"Host": "www.ayurai.org"}):
            status, body, _ = self.register(headers=headers)
            self.assertEqual(status, 403, headers)
        remote = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"host", b"127.0.0.1:8001")],
                          "client": ("198.51.100.7", 5555)})
        with self.assertRaises(HTTPException) as ctx:
            patient_records.require_operator(remote)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_component4_tokens_roles_and_clinic_scoping(self):
        self.mode("component4")
        auth = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731
        self.assertEqual(self.register()[0], 401)  # no token
        self.assertEqual(self.register(headers=auth("forged"))[0], 401)  # Component 4 rejects it
        self.assertEqual(self.register(headers=auth("tok-research"))[0], 403)  # role not allowed
        status, created, _ = self.register(headers=auth("tok-prac-1"))
        self.assertEqual(status, 201)
        sid = created["session_id"]
        self.assertEqual(created["patient"]["clinic_id"], "clinic-1")
        self.assertEqual(call(self.base, "GET", f"/api/c1/sessions/{sid}/patient", headers=auth("tok-prac-1"))[0], 200)
        for path in (f"/api/c1/sessions/{sid}/patient", f"/api/c1/doctor/sessions/{sid}", f"/api/c1/doctor/sessions/{sid}/report.pdf"):
            self.assertEqual(call(self.base, "GET", path, headers=auth("tok-prac-2"))[0], 404, path)  # other clinic: invisible
            self.assertEqual(call(self.base, "GET", path, headers=auth("tok-super"))[0], 200, path)
        listed = lambda token: {s["session_id"] for s in call(self.base, "GET", "/api/c1/doctor/sessions", headers=auth(token))[1]["sessions"]}  # noqa: E731
        self.assertIn(sid, listed("tok-prac-1"))
        self.assertNotIn(sid, listed("tok-prac-2"))
        self.assertIn(sid, listed("tok-super"))
        with mock.patch.object(patient_records, "C4_AUTH_ME_URL", "http://127.0.0.1:1/api/v1/c4/auth/me"):
            patient_records._token_cache.clear()
            self.assertEqual(self.register(headers=auth("tok-prac-1"))[0], 503)  # sign-in service down: refused, not opened

    # ---------------------------------------------------------------- registration

    def test_registration_creates_one_session_and_keeps_personal_data_out_of_it(self):
        self.mode("local_dev")
        request_id = uuid.uuid4().hex
        status, created, headers = self.register(request_id=request_id)
        self.assertEqual(status, 201)
        sid = created["session_id"]
        self.assertRegex(sid, r"^demo_[0-9a-f]{8}$")
        self.assertEqual(created["patient"]["phone_display"], "+94 77 123 4567")
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        again = self.register(request_id=request_id)  # double click / retry
        self.assertEqual((again[0], again[1]["session_id"], again[1]["duplicate"]), (200, sid, True))
        self.assertEqual(len([p for p in self.sessions.iterdir() if p.name == sid]), 1)
        session_files = " ".join(p.read_text(encoding="utf-8", errors="ignore") for p in (self.sessions / sid).rglob("*") if p.is_file())
        for secret in ("Kamala", "4567", "+9477"):
            self.assertNotIn(secret, session_files + sid)
        with sqlite3.connect(self.db) if self.db.exists() else sqlite3.connect(":memory:") as screening:
            tables = {r[0] for r in screening.execute("SELECT name FROM sqlite_master")}
        self.assertNotIn("patient_registrations", tables)  # screening database untouched

    def test_validation_errors_never_repeat_the_input(self):
        self.mode("local_dev")
        status, body, _ = self.register(phone="077-SECRET-99")
        self.assertEqual(status, 422)
        self.assertNotIn("SECRET", json.dumps(body))
        status, body, _ = self.register(name="Kamala 007")
        self.assertEqual(status, 422)
        self.assertNotIn("Kamala", json.dumps(body))

    def test_details_can_be_corrected_and_added_to_old_sessions(self):
        self.mode("local_dev")
        sid = self.register()[1]["session_id"]
        status, body, _ = call(self.base, "PUT", f"/api/c1/sessions/{sid}/patient", {"full_name": "Kamala Corrected-Test", "phone": PHONE})
        self.assertEqual((status, body["changed_fields"], body["patient"]["full_name"]), (200, ["full_name"], "Kamala Corrected-Test"))
        with sqlite3.connect(self.pii) as conn:
            log = conn.execute("SELECT fields FROM registration_changes WHERE session_id = ?", (sid,)).fetchall()
        self.assertEqual(log, [("full_name",)])  # field names only, never the values
        old = intake.create_session()["session_id"]  # session from before registration existed
        self.assertEqual(call(self.base, "GET", f"/api/c1/sessions/{old}/patient")[0], 404)
        status, body, _ = call(self.base, "PUT", f"/api/c1/sessions/{old}/patient", {"full_name": "Late Registration", "phone": "+44 20 7946 0958"})
        self.assertEqual((status, body["patient"]["phone_display"]), (200, "+442079460958"))

    def test_records_persist_in_the_sqlite_file_across_a_restart(self):
        self.mode("local_dev")
        sid = self.register()[1]["session_id"]
        patient_records._token_cache.clear()
        with sqlite3.connect(self.pii) as conn:  # nothing is kept in memory: a new process reads the same file
            self.assertEqual(conn.execute("SELECT full_name FROM patient_registrations WHERE session_id = ?", (sid,)).fetchone()[0], NAME)
        self.assertEqual(call(self.base, "GET", f"/api/c1/sessions/{sid}/patient")[1]["patient"]["full_name"], NAME)

    # ---------------------------------------------------------------- reports and PDFs

    def full_session(self, sid):
        intake.save_questionnaire(sid, questionnaire_body({**COMMON_NO_SAFETY, "C01": "yes", "C02": "no", "C03": "no"}))
        for modality, seed in (("conjunctiva", 1), ("nails", 2), ("tongue", 3)):
            upload(sid, modality, seed)
        intake.ppg_comfort_check(sid, intake.ComfortIn(answers={"P02": "no", "P03": "no", "P05": "no", "P06": "no", "P07": "yes"}))
        with mock.patch.object(capture_live_ppg.serial, "Serial", FakeEsp32):
            intake.record_ppg(sid, intake.PpgRecordIn(seconds=5))
            self.assertEqual(wait_for_job()["state"], "saved")
        return intake.analyze(sid)

    def pdf_text(self, sid, patient):
        with mock.patch.object(pdf_report, "_FONT_CANDIDATES", []), mock.patch.dict(pdf_report._fonts, {}, clear=True):
            report = server._build_report(sid)
            pdf = pdf_report.build_pdf(report, patient=patient, include_contact=True, generated_at=datetime.now(timezone.utc),
                                       ppg_duration_s=patient_records._ppg_duration(report["modalities"]["ppg"].get("recording_id")),
                                       compress=False)
        return text_of(pdf)

    def test_pdf_for_a_normal_screening(self):
        self.mode("local_dev")
        sid = self.register()[1]["session_id"]
        report = self.full_session(sid)
        status, pdf, headers = call(self.base, "GET", f"/api/c1/doctor/sessions/{sid}/report.pdf?thumbnails=true")
        self.assertEqual((status, headers.get("Content-Type")), (200, "application/pdf"))
        self.assertTrue(pdf.startswith(b"%PDF-") and b"/Subtype /Image" in pdf)  # thumbnails embedded on request
        self.assertNotIn("Kamala", headers.get("Content-Disposition"))
        self.assertIn(sid, headers.get("Content-Disposition"))
        text = self.pdf_text(sid, {"full_name": NAME, "phone_display": "+94 77 123 4567"})
        tier = {"low": "Low", "moderate": "Moderate", "high": "High", "insufficient_evidence": "Insufficient evidence"}[report["screening_result"]["risk_level"]]
        for expected in (NAME, "+94 77 123 4567", sid, "RESEARCH PROTOTYPE", f"{tier} (experimental, not clinically validated)",
                         "not a probability or calibrated confidence", "Normal screening pathway", "Image evidence",
                         "PPG evidence", "HR and SpO2 alone are not validated anaemia evidence", "Pending review: no practitioner decision",
                         "Confirm with laboratory haemoglobin", "Not a medical diagnosis", "Page 1 of"):
            self.assertIn(expected, text, expected)
        self.assertIn(f"{report['modalities']['ppg']['sample_count']}", text)
        self.assertNotIn("Approved by", text)

    def test_pdf_for_a_safety_referral(self):
        self.mode("local_dev")
        sid = self.register()[1]["session_id"]
        intake.save_referral(sid, intake.ReferralIn(profile={"age_months": 300, "sex": "female", "pregnancy_status": "not_pregnant"},
                                                    consent=True, answers={**COMMON_NO_SAFETY, "SAF01": "yes"}))
        status, pdf, _ = call(self.base, "GET", f"/api/c1/doctor/sessions/{sid}/report.pdf")
        self.assertEqual(status, 200)
        text = self.pdf_text(sid, {"full_name": NAME, "phone_display": "+94 77 123 4567"})
        for expected in ("SAFETY REFERRAL: immediate clinician assessment required", "Further screening was blocked",
                         "No risk tier: this is a safety-referral-only record"):
            self.assertIn(expected, text)
        for absent in ("Image evidence", "PPG evidence", "Experimental risk tier"):
            self.assertNotIn(absent, text)

    def test_pdf_handles_missing_data_without_inventing_values(self):
        self.mode("local_dev")
        sid = intake.create_session()["session_id"]  # coded session, never registered
        intake.save_questionnaire(sid, questionnaire_body(dict(COMMON_NO_SAFETY), consent_images=False, consent_ppg=False))
        intake.analyze(sid)
        self.assertEqual(call(self.base, "GET", f"/api/c1/doctor/sessions/{sid}/report.pdf")[0], 200)
        text = self.pdf_text(sid, None)
        for expected in ("Not registered (coded session; no name stored)", "No PPG recording was used",
                         "Insufficient evidence (experimental, not clinically validated)", "Not recorded"):
            self.assertIn(expected, text)
        for invented in ("bpm (median)", "% (median)", "Recording duration"):
            self.assertNotIn(invented, text)
        summary = call(self.base, "GET", f"/api/c1/doctor/sessions/{sid}")[1]
        self.assertEqual((summary["patient"]["registered"], summary["review_status"]), (False, "pending_review"))

    def test_sinhala_name_renders(self):
        pdf = pdf_report.build_pdf(server._build_report(self.register_coded()), patient={"full_name": "නිමල් පෙරේරා", "phone_display": "+94 77 123 4567"},
                                   include_contact=True, generated_at=datetime.now(timezone.utc))
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def register_coded(self):
        sid = intake.create_session()["session_id"]
        intake.save_questionnaire(sid, questionnaire_body(dict(COMMON_NO_SAFETY), consent_images=False, consent_ppg=False))
        return sid

    def test_personal_data_stays_out_of_component2_and_public_routes(self):
        self.mode("local_dev")
        sid = self.register()[1]["session_id"]
        self.full_session(sid)
        report = server._build_report(sid)
        payload = server._c2_payload(report)
        everything_public = json.dumps([payload, report, server._screening_result(report), intake.intake_state(sid), server.sessions()])
        for secret in ("Kamala", "+94771234567", "077 123 4567", "123 4567"):
            self.assertNotIn(secret, everything_public)
        saved = json.loads((self.sessions / sid / "c2_payload.json").read_text(encoding="utf-8"))
        self.assertEqual(set(saved), set(payload))  # same contract as before


if __name__ == "__main__":
    unittest.main()
