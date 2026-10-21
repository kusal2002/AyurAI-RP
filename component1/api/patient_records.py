"""AyurAI Component 1: patient registration (name, phone), doctor-review summaries and PDF screening reports.

Personal data is kept in its own SQLite file (C1_PII_DB_PATH, default ../datasets/c1_patient_identity.sqlite3):
never in session folders, session IDs, the screening database, Component 2 payloads, URLs, logs or error messages.

Every route that returns or stores personal data or a clinical report is protected (C1_PATIENT_DATA_ACCESS):
  off         default: those routes answer 503 and nothing personal can be read or written
  component4  Authorization: Bearer <Component 4 JWT>, verified with Component 4 GET /auth/me (C1_C4_AUTH_ME_URL);
              role must be in C1_PATIENT_DATA_ROLES (default practitioner,supervisor); a practitioner only sees
              sessions registered by their own clinic, a supervisor sees all
  local_dev   laptop demonstration only: answers requests made on this computer (loopback client, localhost Host,
              no proxy headers). NEVER set this on a server.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from component1.api import intake

ACCESS_MODES = ("off", "component4", "local_dev")
ACCESS_MODE = intake._setting("C1_PATIENT_DATA_ACCESS", "off").lower()
if ACCESS_MODE not in ACCESS_MODES:
    raise RuntimeError("C1_PATIENT_DATA_ACCESS must be off, component4 or local_dev")
C4_AUTH_ME_URL = intake._setting("C1_C4_AUTH_ME_URL", "http://127.0.0.1:8004/api/v1/c4/auth/me")
ALLOWED_ROLES = tuple(r.strip() for r in intake._setting("C1_PATIENT_DATA_ROLES", "practitioner,supervisor").split(",") if r.strip())
ALL_CLINIC_ROLES = ("supervisor", "local_dev")
PII_DB_PATH = Path(intake._setting("C1_PII_DB_PATH", str(intake.DATA_ROOT / "c1_patient_identity.sqlite3")))
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-real-ip", "forwarded", "via")
TOKEN_CACHE_SECONDS = 60
DISABLED = ("Patient registration, doctor reports and PDF downloads are disabled on this server until Component 4 "
            "sign-in is integrated (C1_PATIENT_DATA_ACCESS=off).")

router = APIRouter(prefix="/api/c1")
_registration_lock = threading.Lock()
_token_cache: dict[str, tuple[float, "Operator"]] = {}


@dataclass(frozen=True)
class Operator:
    username: str
    role: str
    clinic_id: str | None


# ---------------------------------------------------------------- access control


def _c4_me(token: str) -> dict[str, Any]:
    """Ask Component 4 who owns this token (no shared secret; Component 4 stays the authority)."""
    request = urllib.request.Request(C4_AUTH_ME_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(401, "Sign-in expired or invalid", headers={"WWW-Authenticate": "Bearer"}) from None
        raise HTTPException(503, "The sign-in service could not verify this request") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise HTTPException(503, "The sign-in service is unavailable") from None


def _host_name(request: Request) -> str:
    host = request.headers.get("host", "")
    return host[1:].split("]")[0] if host.startswith("[") else host.split(":")[0]


def require_operator(request: Request) -> Operator:
    """FastAPI dependency for every route that touches personal data or clinical reports."""
    if ACCESS_MODE == "off":
        raise HTTPException(503, DISABLED)
    if ACCESS_MODE == "local_dev":
        client = request.client.host if request.client else ""
        if client not in LOOPBACK or _host_name(request) not in LOOPBACK or any(h in request.headers for h in PROXY_HEADERS):
            raise HTTPException(403, "Local patient-data mode only answers requests made on this computer")
        return Operator("local-operator", "local_dev", None)
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer ") or not authorization[7:].strip():
        raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
    token = authorization[7:].strip()
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = _token_cache.get(key)
    if cached and cached[0] > time.monotonic():
        operator = cached[1]
    else:
        me = _c4_me(token)
        operator = Operator(str(me.get("username") or ""), str(me.get("role") or ""), me.get("clinic_id"))
        _token_cache[key] = (time.monotonic() + TOKEN_CACHE_SECONDS, operator)
    if not operator.username or operator.role not in ALLOWED_ROLES:
        raise HTTPException(403, "Your role cannot access patient details or clinical reports")
    return operator


def _visible(operator: Operator, registration: dict | None) -> bool:
    if operator.role in ALL_CLINIC_ROLES:
        return True
    return bool(registration and operator.clinic_id and registration.get("clinic_id") == operator.clinic_id)


# ---------------------------------------------------------------- validation (messages never repeat the input)

NAME_PUNCTUATION = set(" .'-’")


def normalise_name(raw: Any) -> str:
    name = " ".join(unicodedata.normalize("NFC", str(raw or "")).split())
    if not 2 <= len(name) <= 100:
        raise ValueError("Enter the patient's full name (2 to 100 characters).")
    letters = 0
    for character in name:
        category = unicodedata.category(character)
        if category[0] == "L":
            letters += 1
        elif category[0] != "M" and character not in NAME_PUNCTUATION:  # M: vowel signs in Sinhala, Tamil, etc.
            raise ValueError("The name may contain letters, spaces, apostrophes, hyphens and full stops only.")
    if letters < 2:
        raise ValueError("Enter the patient's full name (2 to 100 characters).")
    return name


def normalise_phone(raw: Any) -> str:
    """E.164. Ten-digit numbers starting with 0 are Sri Lankan (077 123 4567 -> +94771234567)."""
    compact = re.sub(r"[\s\-().]", "", str(raw or ""))
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if re.fullmatch(r"0\d{9}", compact):
        return "+94" + compact[1:]
    if re.fullmatch(r"94\d{9}", compact):
        return "+" + compact
    if re.fullmatch(r"\+[1-9]\d{7,14}", compact):
        if compact.startswith("+94") and not re.fullmatch(r"\+94\d{9}", compact):
            raise ValueError("Sri Lankan numbers have 9 digits after +94 (for example +94 77 123 4567).")
        return compact
    raise ValueError("Enter a phone number such as 077 123 4567 or +94 77 123 4567; international numbers start with +.")


def display_phone(e164: str) -> str:
    if re.fullmatch(r"\+94\d{9}", e164):
        return f"+94 {e164[3:5]} {e164[5:8]} {e164[8:]}"
    return e164


# ---------------------------------------------------------------- storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS patient_registrations (
    session_id   TEXT PRIMARY KEY,
    request_id   TEXT NOT NULL UNIQUE,
    full_name    TEXT NOT NULL,
    phone_e164   TEXT NOT NULL,
    clinic_id    TEXT,
    created_by   TEXT NOT NULL,
    created_utc  TEXT NOT NULL,
    updated_by   TEXT NOT NULL,
    updated_utc  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS registration_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    changed_utc  TEXT NOT NULL,
    changed_by   TEXT NOT NULL,
    fields       TEXT NOT NULL
);
"""


def _db() -> sqlite3.Connection:
    if not PII_DB_PATH.parent.is_dir():
        raise HTTPException(503, "Patient-data storage is not available")
    new = not PII_DB_PATH.exists()
    conn = sqlite3.connect(PII_DB_PATH)
    if new and os.name == "posix":
        os.chmod(PII_DB_PATH, 0o600)  # owner (the API's service account) only
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def registration(session_id: str) -> dict | None:
    if not PII_DB_PATH.is_file():
        return None
    with closing(_db()) as conn:
        row = conn.execute("SELECT * FROM patient_registrations WHERE session_id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def _patient_out(row: dict, contact: bool = True) -> dict[str, Any]:
    out = {"session_id": row["session_id"], "full_name": row["full_name"], "created_utc": row["created_utc"],
           "updated_utc": row["updated_utc"], "clinic_id": row["clinic_id"]}
    if contact:
        out.update(phone_e164=row["phone_e164"], phone_display=display_phone(row["phone_e164"]))
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validated(body: dict) -> tuple[str, str]:
    try:
        return normalise_name(body.get("full_name")), normalise_phone(body.get("phone"))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def _no_store(content: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(content, status_code=status, headers={"Cache-Control": "no-store"})


def _session(session_id: str, operator: Operator) -> tuple[Path, dict | None]:
    """Session folder plus its registration, or 404 when it does not exist OR this operator may not see it."""
    session_dir = intake._session_dir(session_id)
    found = registration(session_id)
    if not _visible(operator, found):
        raise HTTPException(404, "Session not found")
    return session_dir, found


# ---------------------------------------------------------------- routes


@router.get("/patient-data/status")
def patient_data_status():
    """Public: whether patient features are available here (no personal data)."""
    return {"access_mode": ACCESS_MODE, "enabled": ACCESS_MODE != "off", "requires_bearer_token": ACCESS_MODE == "component4"}


@router.post("/patients/register", status_code=201)
def register_patient(body: dict = Body(...), operator: Operator = Depends(require_operator)):
    """Register name + phone and create the coded screening session in one step.

    request_id (32 hex characters, generated once per registration form) makes retries and double clicks safe:
    the same request_id always returns the same session instead of creating another one.
    """
    request_id = str(body.get("request_id") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise HTTPException(422, "Invalid registration request ID")
    name, phone = _validated(body)
    with _registration_lock, closing(_db()) as conn:
        existing = conn.execute("SELECT * FROM patient_registrations WHERE request_id = ?", (request_id,)).fetchone()
        if existing:
            if not _visible(operator, dict(existing)):
                raise HTTPException(409, "This registration request was already used")
            return _no_store({"session_id": existing["session_id"], "duplicate": True, "patient": _patient_out(dict(existing))}, 200)
        session_id = intake.create_session()["session_id"]  # random ID: never derived from the name or phone
        now = _now()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO patient_registrations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, request_id, name, phone, operator.clinic_id, operator.username, now, operator.username, now),
                )
        except sqlite3.Error:
            shutil.rmtree(intake.SESSIONS_ROOT / session_id, ignore_errors=True)  # the empty session just created
            raise HTTPException(500, "Could not save the registration; no session was created") from None
        row = dict(conn.execute("SELECT * FROM patient_registrations WHERE session_id = ?", (session_id,)).fetchone())
    return _no_store({"session_id": session_id, "duplicate": False, "patient": _patient_out(row)}, 201)


@router.get("/sessions/{session_id}/patient")
def get_patient(session_id: str, operator: Operator = Depends(require_operator)):
    _, found = _session(session_id, operator)
    if found is None:
        raise HTTPException(404, "No patient registration for this session (coded session)")
    return _no_store({"patient": _patient_out(found)})


@router.put("/sessions/{session_id}/patient")
def update_patient(session_id: str, body: dict = Body(...), operator: Operator = Depends(require_operator)):
    """Correct the details, or add them to a session created without registration. Changes are logged (field names only)."""
    intake._session_dir(session_id)
    name, phone = _validated(body)
    with _registration_lock, closing(_db()) as conn, conn:
        row = conn.execute("SELECT * FROM patient_registrations WHERE session_id = ?", (session_id,)).fetchone()
        now = _now()
        if row is None:
            conn.execute("INSERT INTO patient_registrations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (session_id, os.urandom(16).hex(), name, phone, operator.clinic_id, operator.username, now, operator.username, now))
            changed = ["full_name", "phone"]
        else:
            if not _visible(operator, dict(row)):
                raise HTTPException(404, "Session not found")
            changed = [f for f, old, new in (("full_name", row["full_name"], name), ("phone", row["phone_e164"], phone)) if old != new]
            conn.execute("UPDATE patient_registrations SET full_name = ?, phone_e164 = ?, updated_by = ?, updated_utc = ? WHERE session_id = ?",
                         (name, phone, operator.username, now, session_id))
        if changed:
            conn.execute("INSERT INTO registration_changes (session_id, changed_utc, changed_by, fields) VALUES (?, ?, ?, ?)",
                         (session_id, now, operator.username, ",".join(changed)))
        updated = dict(conn.execute("SELECT * FROM patient_registrations WHERE session_id = ?", (session_id,)).fetchone())
    return _no_store({"patient": _patient_out(updated), "changed_fields": changed})


def _summary(session_id: str, found: dict | None, contact: bool) -> dict[str, Any]:
    from component1.api import server

    report = server._build_report(session_id)
    result = report["screening_result"]
    profile = report.get("patient", {})
    base = f"/api/c1/doctor/sessions/{session_id}"
    return {
        "session_id": session_id,
        "created_utc": intake._manifest(intake._session_dir(session_id)).get("created_utc"),
        "patient": {
            **({"full_name": found["full_name"]} if found else {"full_name": None}),
            **({"phone_display": display_phone(found["phone_e164"])} if found and contact else {}),
            "registered": found is not None,
            "age_months": profile.get("age_months"), "sex": profile.get("sex"), "pregnancy_status": profile.get("pregnancy_status"),
        },
        "outcome": report["outcome"],
        "risk_level": result.get("risk_level"),
        "risk_level_validated": False,
        "reliability_score": result.get("reliability_score"),
        "reliability_score_is_probability": False,
        "decision_status": result.get("decision_status"),
        "analysis_outdated": bool(report.get("analysis_outdated")),
        "record_saved": bool((report.get("storage") or {}).get("record_saved")),
        # Component 1 never records practitioner decisions; Component 4 owns them (case_ref = session_id).
        "review_status": "pending_review",
        "links": {"summary": base, "report": f"{base}/report", "pdf": f"{base}/report.pdf"},
    }


@router.get("/doctor/sessions")
def doctor_sessions(operator: Operator = Depends(require_operator)):
    """Sessions this operator may review, newest first; names but no phone numbers."""
    from component1.api import server

    rows = []
    for item in server.sessions()["sessions"]:
        found = registration(item["session_id"])
        if _visible(operator, found):
            rows.append(_summary(item["session_id"], found, contact=False))
    return _no_store({"sessions": rows})


@router.get("/doctor/sessions/{session_id}")
def doctor_session(session_id: str, operator: Operator = Depends(require_operator)):
    _, found = _session(session_id, operator)
    return _no_store(_summary(session_id, found, contact=True))


@router.get("/doctor/sessions/{session_id}/report")
def doctor_report(session_id: str, operator: Operator = Depends(require_operator)):
    from component1.api import server

    _, found = _session(session_id, operator)
    return _no_store({"patient": _patient_out(found) if found else None, "review_status": "pending_review",
                      "report": server._build_report(session_id)})


def _ppg_duration(recording_id: Any) -> float | None:
    """Exact span of the stored samples (SQLite, read-only); None if unavailable."""
    if not isinstance(recording_id, int) or not intake.DB_PATH.is_file():
        return None
    with closing(sqlite3.connect(f"{intake.DB_PATH.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        try:
            span = conn.execute("SELECT MAX(host_elapsed_s) - MIN(host_elapsed_s) FROM ppg_live_samples WHERE recording_id = ?",
                                (recording_id,)).fetchone()[0]
        except sqlite3.Error:
            return None
    return float(span) if span is not None else None


@router.get("/doctor/sessions/{session_id}/report.pdf")
def doctor_report_pdf(session_id: str, thumbnails: bool = Query(False), operator: Operator = Depends(require_operator)):
    """A4 PDF of the current screening report. Thumbnails only on request and only with image consent."""
    from component1.api import server
    from component1.reports.pdf_report import build_pdf

    session_dir, found = _session(session_id, operator)
    report = server._build_report(session_id)
    quality = {}
    if (session_dir / "quality_report.json").is_file():
        quality = json.loads((session_dir / "quality_report.json").read_text(encoding="utf-8"))
    answers = {r["question_id"]: r.get("answer") for r in report.get("questionnaire", {}).get("responses", [])}
    pictures = []
    if thumbnails and answers.get("REG07") == "yes":
        manifest = intake._manifest(session_dir)
        images_root = (session_dir / "images").resolve()
        for capture in manifest.get("captures", []):
            path = Path(capture.get("image_path", "")).resolve()
            if path.is_file() and path.is_relative_to(images_root):
                pictures.append((str(capture.get("modality", "")).replace("nails", "nail beds").title(), path))
    pdf = build_pdf(
        report,
        patient={"full_name": found["full_name"], "phone_display": display_phone(found["phone_e164"])} if found else None,
        include_contact=True,
        generated_at=datetime.now(timezone.utc),
        quality_images=quality.get("results"),
        ppg_duration_s=_ppg_duration(report["modalities"]["ppg"].get("recording_id")),
        thumbnails=pictures,
    )
    return Response(pdf, media_type="application/pdf", headers={
        "Cache-Control": "no-store",
        # File name uses the session ID only: never the patient's name.
        "Content-Disposition": f'attachment; filename="AyurAI-C1-report-{session_id}.pdf"',
    })
