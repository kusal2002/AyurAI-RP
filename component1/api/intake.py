"""AyurAI Component 1: clinical intake routes for the shared frontend.

FICTIONAL DEMO SESSIONS ONLY (demo_XXXXXXXX). Every route reuses the existing
Component 1 acquisition, quality, model and fusion code; nothing is reimplemented.

Consent and safety are enforced here, server-side:
- images require questionnaire image consent (image_acquisition_allowed);
- PPG requires PPG consent plus the finger-comfort check at the sensor.

Hardware: local USB serial only (ESP32-S3 + MAX30102). Port and baud come from
component1/.env (C1_SERIAL_PORT, C1_SERIAL_BAUD), defaulting to COM11 / 115200.

PPG capture paths (environment first, then component1/.env):
- C1_SERIAL_ENABLED (default true): this API opens the ESP32's COM port itself (localhost workflow).
- C1_PPG_UPLOAD_ENABLED (default false): the browser records over Web Serial and uploads the recording.
  Enable ONLY when /api/c1 is behind authenticated access (this API has no user authentication of its own).
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from contextlib import closing
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
C1_ROOT = REPO_ROOT / "component1"
DATA_ROOT = REPO_ROOT.parent / "datasets"
SESSIONS_ROOT = DATA_ROOT / "live_sessions"
DB_PATH = DATA_ROOT / "screening_sessions.sqlite3"
MODALITIES = ("conjunctiva", "nails", "tongue")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
PPG_COMFORT_IDS = ("P02", "P03", "P05", "P06", "P07")
# Accepted profile values: the same options as the questionnaire form (questionnaire_assistant_app).
SEX_VALUES = ("not_recorded", "female", "male", "intersex", "prefer_not_to_answer")
PREGNANCY_VALUES = ("not_applicable", "pregnant", "not_pregnant", "unknown", "prefer_not_to_answer")
# From this age reliability_fusion.who_hb_threshold picks the WHO cut-off by sex, so sex must be recorded.
SEX_REQUIRED_FROM_MONTHS = 180
REFERRAL_STATUS = "safety_referral"  # Same value as server.REFERRAL_STATUS (completion_status column).

# Reuse the existing questionnaire logic (streamlit is imported only inside its app()).
sys.path.insert(0, str(C1_ROOT / "acquisition" / "questionnaire"))
import questionnaire_assistant_app as questionnaire  # noqa: E402
from questionnaire_engine import get_status, validate_answers  # noqa: E402

router = APIRouter(prefix="/api/c1")
_serial_lock = threading.Lock()


def _env() -> dict[str, str]:
    """Minimal KEY=VALUE reader for component1/.env (no secrets are needed here)."""
    path = C1_ROOT / ".env"
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _setting(name: str, default: str) -> str:
    """Process environment first (deployment), then component1/.env (local), then the default."""
    return os.environ.get(name, "").strip() or _env().get(name, "").strip() or default


def _flag(name: str, default: bool) -> bool:
    value = _setting(name, "true" if default else "false").lower()
    if value not in ("true", "false", "1", "0", "yes", "no"):
        raise RuntimeError(f"{name} must be true or false")
    return value in ("true", "1", "yes")


SERIAL_ENABLED = _flag("C1_SERIAL_ENABLED", True)
PPG_UPLOAD_ENABLED = _flag("C1_PPG_UPLOAD_ENABLED", False)
SERIAL_DISABLED_MESSAGE = "This server does not record from a USB sensor (C1_SERIAL_ENABLED=false)."


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session_dir(session_id: str) -> Path:
    if not questionnaire.SESSION_PATTERN.fullmatch(session_id):
        raise HTTPException(400, "Only demo_XXXXXXXX sessions are available in this prototype")
    path = SESSIONS_ROOT / session_id
    if not path.is_dir():
        raise HTTPException(404, "Session not found")
    return path


def _question(qid: str) -> dict[str, Any]:
    q = questionnaire.QUESTION_BY_ID[qid]
    return {"id": qid, "prompt": q["prompt"], "type": q["type"], "options": q.get("options"), "section": q["section"]}


def _questionnaire_row(session_id: str, routine: bool = True) -> dict[str, Any]:
    """Saved questionnaire for a session. routine=True refuses safety-referral sessions."""
    row = None
    if DB_PATH.is_file():
        with closing(sqlite3.connect(DB_PATH)) as conn, conn:
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='questionnaire_responses'"
            ).fetchone():
                row = conn.execute(
                    "SELECT is_fictional_demo, profile_json, answers_json, status_json, completion_status "
                    "FROM questionnaire_responses WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
    if row is None:
        raise HTTPException(409, "Complete the questionnaire first")
    if row[0] != 1:
        raise HTTPException(403, "Patient data requires authenticated clinical API")
    if routine and row[4] == REFERRAL_STATUS:
        raise HTTPException(409, "Safety-referral session: routine screening is stopped. Start a new session for another patient.")
    return {
        "profile": json.loads(row[1]),
        "answers": json.loads(row[2]),
        "status": json.loads(row[3]),
        "completion_status": row[4],
    }


def _manifest(session_dir: Path) -> dict[str, Any]:
    return json.loads((session_dir / "manifest.json").read_text(encoding="utf-8"))


def _capture_counts(manifest: dict) -> dict[str, int]:
    return {m: sum(c.get("modality") == m for c in manifest.get("captures", [])) for m in MODALITIES}


# ---------------------------------------------------------------- sessions


@router.post("/sessions")
def create_session():
    """Create a coded fictional session folder with the webcam manifest schema."""
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        session_id = f"demo_{uuid.uuid4().hex[:8]}"
        session_dir = SESSIONS_ROOT / session_id
        try:
            session_dir.mkdir()
        except FileExistsError:
            continue
        manifest = {"session_id": session_id, "created_utc": _utc(), "created_by": "ayurai-client", "captures": []}
        (session_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"session_id": session_id, "fictional_demo": True}
    raise HTTPException(500, "Could not allocate a session ID")


@router.get("/sessions/{session_id}/captures")
def captures(session_id: str):
    return {"session_id": session_id, "captures": _capture_counts(_manifest(_session_dir(session_id)))}


# ---------------------------------------------------------------- questionnaire


class ProfileIn(BaseModel):
    age_months: int = Field(ge=0, le=1440)
    sex: str = "not_recorded"
    pregnancy_status: str = "not_applicable"


class FollowupsIn(BaseModel):
    profile: ProfileIn
    answers: dict[str, Any] = {}


class QuestionnaireIn(BaseModel):
    profile: ProfileIn
    consent: bool
    consent_ppg: bool
    consent_images: bool
    guardian_permission: bool = False
    answers: dict[str, Any]
    medications: str = ""
    herbals: str = ""
    allergies: str = ""
    no_medications: bool = False
    no_allergies: bool = False


class ComfortIn(BaseModel):
    answers: dict[str, str]


def _profile(profile: ProfileIn, routine: bool = True) -> dict:
    """Validated profile. routine=False (safety referral) never blocks on a missing sex value."""
    if profile.sex not in SEX_VALUES:
        raise HTTPException(422, "Unsupported sex value; choose one of: " + ", ".join(SEX_VALUES))
    if profile.pregnancy_status not in PREGNANCY_VALUES:
        raise HTTPException(422, "Unsupported pregnancy status; choose one of: " + ", ".join(PREGNANCY_VALUES))
    if profile.sex == "male" and profile.pregnancy_status == "pregnant":
        raise HTTPException(422, "Sex 'male' cannot be combined with pregnancy status 'pregnant'; correct one of the two fields")
    if routine and profile.age_months >= SEX_REQUIRED_FROM_MONTHS and profile.sex == "not_recorded":
        raise HTTPException(
            422, "Select the patient's sex for patients aged 15 or older ('intersex' or 'prefer_not_to_answer' are accepted)"
        )
    try:
        return questionnaire.profile_for(profile.age_months, profile.sex, profile.pregnancy_status)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/questionnaire/questions")
def questionnaire_questions():
    return {
        "version": questionnaire.BANK["version"],
        "approval_status": questionnaire.BANK.get("approval_status"),
        "common": [_question(qid) for qid in questionnaire.COMMON_IDS],
        "pregnancy_safety": _question("PR06"),
        "safety_ids": [*questionnaire.COMMON_IDS[:4], "PR06"],
        "ppg_comfort": [_question(qid) for qid in PPG_COMFORT_IDS],
    }


@router.post("/questionnaire/followups")
def questionnaire_followups(body: FollowupsIn):
    """Adaptive follow-ups chosen by the existing rule engine from the common answers."""
    ids = questionnaire.select_followups(_profile(body.profile), body.answers)
    return {"followups": [_question(qid) for qid in ids]}


def _completion_status(session_id: str) -> str | None:
    try:
        return _questionnaire_row(session_id, routine=False)["completion_status"]
    except HTTPException as exc:
        if exc.status_code == 409:
            return None
        raise


@router.post("/sessions/{session_id}/questionnaire")
def save_questionnaire(session_id: str, body: QuestionnaireIn):
    _session_dir(session_id)
    if _completion_status(session_id) == REFERRAL_STATUS:
        raise HTTPException(409, "Safety-referral session: the questionnaire is closed. Start a new session for another patient.")
    profile = _profile(body.profile)
    answers = dict(body.answers)
    if profile["age_months"] < 216:
        if not body.guardian_permission:
            raise HTTPException(422, "Guardian permission must be confirmed for a child")
        answers["CH02"] = "yes"
    status = questionnaire.safety_state(profile, {**answers, "REG05": "yes" if body.consent else "no"})
    if status["urgent_clinician_review"] or status["safety_unresolved"]:
        raise HTTPException(409, {
            "message": "Urgent or unresolved safety answer: stop routine screening and request clinician review.",
            "urgent_response_ids": status["urgent_response_ids"],
            "safety_unresolved": status["safety_unresolved"],
        })
    try:
        final = questionnaire.finalize_answers(
            profile["age_months"], body.consent_ppg, body.consent_images, body.consent, answers,
            body.medications, body.herbals, body.allergies, body.no_medications, body.no_allergies,
        )
        result = questionnaire.save_demo(session_id, profile, final, DATA_ROOT)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"session_id": session_id, "answers_saved": result["answers_saved"], "status": result["status"]}


class ReferralIn(BaseModel):
    profile: ProfileIn
    consent: bool
    consent_ppg: bool = False
    consent_images: bool = False
    guardian_permission: bool = False
    answers: dict[str, Any]


@router.post("/sessions/{session_id}/referral")
def save_referral(session_id: str, body: ReferralIn):
    """Stop and refer: keep the answers given so far as a referral-only record (no routine screening).

    Accepted only when a safety question (SAF01-SAF04, PR06 in pregnancy) is answered "yes" (urgent)
    or left unresolved ("not_sure"/"prefer_not_to_answer"/unanswered), using the existing safety_state rules.
    """
    session_dir = _session_dir(session_id)
    from component1.api.server import save_session_outputs

    if _completion_status(session_id) == REFERRAL_STATUS:
        return save_session_outputs(session_id)
    if not body.consent:
        raise HTTPException(422, "Consent was not given; nothing is saved")
    profile = _profile(body.profile, routine=False)  # An urgent referral is never delayed by a missing sex value.
    answers = {key: value for key, value in body.answers.items() if value not in (None, "")}
    answers.update({
        "REG02": profile["age_months"],
        "REG05": "yes",
        "REG06": "yes" if body.consent_ppg else "no",
        "REG07": "yes" if body.consent_images else "no",
    })
    if profile["age_months"] < 216 and body.guardian_permission:
        answers["CH02"] = "yes"
    try:
        validate_answers(questionnaire.BANK, answers)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    status = questionnaire.safety_state(profile, answers)
    # safety_state counts unanswered safety questions as unresolved; keep "not sure" and "not asked" apart.
    status["safety_not_asked"] = [qid for qid in status["safety_unresolved"] if qid not in answers]
    status["safety_unresolved"] = [qid for qid in status["safety_unresolved"] if qid in answers]
    if not (status["urgent_clinician_review"] or status["safety_unresolved"]):
        raise HTTPException(422, "No urgent or unresolved safety answer: continue the routine questionnaire instead")
    status["safety_referral"] = True

    referred = _utc()
    scenario = "child" if profile["age_months"] < 216 else "pregnancy" if profile["pregnancy_status"] == "pregnant" else "adult"
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        # Same schema as questionnaire_assistant_app.save_demo; only completion_status differs.
        conn.execute('''CREATE TABLE IF NOT EXISTS questionnaire_responses (
            session_id TEXT PRIMARY KEY,
            question_bank_version TEXT NOT NULL,
            scenario TEXT NOT NULL,
            is_fictional_demo INTEGER NOT NULL CHECK(is_fictional_demo=1),
            profile_json TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            status_json TEXT NOT NULL,
            completion_status TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL)''')
        conn.execute(
            '''INSERT INTO questionnaire_responses
               (session_id, question_bank_version, scenario, is_fictional_demo,
                profile_json, answers_json, status_json, completion_status, updated_at_utc)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 scenario=excluded.scenario, profile_json=excluded.profile_json,
                 answers_json=excluded.answers_json, status_json=excluded.status_json,
                 completion_status=excluded.completion_status, updated_at_utc=excluded.updated_at_utc
               WHERE questionnaire_responses.is_fictional_demo=1''',
            (session_id, questionnaire.BANK["version"], scenario, json.dumps(profile), json.dumps(answers),
             json.dumps(status), REFERRAL_STATUS, referred),
        )
    record = {
        "session_id": session_id,
        "record_type": "safety_referral",
        "referred_utc": referred,
        "urgent_response_ids": status["urgent_response_ids"],
        "unresolved_safety_ids": status["safety_unresolved"],
        "not_asked_safety_ids": status["safety_not_asked"],
        "reason": (
            "Urgent safety answer: immediate clinician assessment required."
            if status["urgent_clinician_review"]
            else "Safety question not resolved (not sure / not answered): clinician must clarify before any routine screening."
        ),
        "answers_recorded": len(answers),
        "routine_screening_performed": False,
        "ai_anaemia_risk_classification": None,
    }
    (session_dir / "safety_referral.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return save_session_outputs(session_id)


def _ppg_recordings(session_id: str) -> list[dict[str, Any]]:
    if not DB_PATH.is_file():
        return []
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppg_live_recordings'").fetchone():
            return []
        rows = conn.execute(
            "SELECT id, recording_file, sample_count, quality_status, observed_receive_rate_hz, imported_at_utc "
            "FROM ppg_live_recordings WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [
        {"recording_id": r[0], "recording_file": r[1], "sample_count": r[2], "quality_status": r[3],
         "observed_receive_rate_hz": r[4], "saved_utc": r[5]}
        for r in rows
    ]


@router.get("/sessions/{session_id}/intake-state")
def intake_state(session_id: str):
    """Everything needed to resume this session's intake after Back/Next or a page refresh."""
    session_dir = _session_dir(session_id)
    from component1.api.server import _db_questionnaire, workflow_state

    q = _db_questionnaire(session_id)
    manifest = _manifest(session_dir)
    return {
        "session_id": session_id,
        "created_utc": manifest.get("created_utc"),
        "workflow_state": workflow_state(session_dir, q),
        "questionnaire": None if q is None else {
            "profile": q["profile"],
            "answers": q["answers"],
            "status": q["status"],
            "completion_status": q["completion_status"],
        },
        "captures": _capture_counts(manifest),
        "images": _image_list(manifest),
        "ppg_recordings": _ppg_recordings(session_id),
        "record_saved": (session_dir / "screening_report.json").is_file(),
    }


@router.post("/sessions/{session_id}/ppg/comfort")
def ppg_comfort_check(session_id: str, body: ComfortIn):
    """Finger-comfort check at the sensor; the only step that can clear PPG acquisition."""
    _session_dir(session_id)
    row = _questionnaire_row(session_id)
    if set(body.answers) - set(PPG_COMFORT_IDS):
        raise HTTPException(422, "Unexpected comfort-check question")
    answers = {**row["answers"], **body.answers}
    try:
        validate_answers(questionnaire.BANK, answers)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    status = questionnaire.safety_state(row["profile"], answers)
    engine = get_status(row["profile"], answers)
    blocked = [qid for qid in ("P02", "P05", "P06") if answers.get(qid) != "no"]
    if answers.get("P07") != "yes":
        blocked.append("P07")
    status["ppg_pending_finger_comfort_check"] = False
    status["ppg_comfort_blocking_ids"] = blocked
    status["ppg_optical_obstruction_reported"] = answers.get("P03") == "yes"
    status["ppg_acquisition_allowed"] = bool(
        engine["ppg_acquisition_allowed"] and not blocked
        and not status["urgent_clinician_review"] and not status["safety_unresolved"]
    )
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            "UPDATE questionnaire_responses SET answers_json = ?, status_json = ?, updated_at_utc = ? "
            "WHERE session_id = ? AND is_fictional_demo = 1",
            (json.dumps(answers), json.dumps(status), _utc(), session_id),
        )
    return {"session_id": session_id, "status": status}


# ---------------------------------------------------------------- images


IMAGE_ID = re.compile(r"(conjunctiva|nails|tongue)_[0-9A-Za-z_]+\.png")


def _write_manifest(session_dir: Path, manifest: dict) -> None:
    tmp = session_dir / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(session_dir / "manifest.json")


def _active_capture(session_dir: Path, manifest: dict, image_id: str) -> tuple[int, Path]:
    """Index and path of an ACTIVE capture in this session. Image IDs are file names, never paths."""
    if not IMAGE_ID.fullmatch(image_id):
        raise HTTPException(400, "Invalid image ID")
    images_root = (session_dir / "images").resolve()
    for index, capture in enumerate(manifest.get("captures", [])):
        path = Path(capture.get("image_path", "")).resolve()
        if path.name == image_id:
            try:
                path.relative_to(images_root)
            except ValueError:
                raise HTTPException(400, "Image is outside this session") from None
            return index, path
    raise HTTPException(404, "Image not found in this session")


def _image_list(manifest: dict) -> list[dict[str, Any]]:
    return [
        {"image_id": Path(c["image_path"]).name, "modality": c.get("modality"), "captured_utc": c.get("captured_utc"),
         "available": Path(c["image_path"]).is_file()}
        for c in manifest.get("captures", [])
    ]


def _retire(session_dir: Path, manifest: dict, index: int, path: Path, reason: str, replaced_by: str | None = None) -> Path | None:
    """Move a capture out of active evidence (kept under images/_removed for audit); returns the new file path."""
    capture = manifest["captures"].pop(index)
    retired = None
    if path.is_file():
        retired_dir = session_dir / "images" / "_removed"
        retired_dir.mkdir(parents=True, exist_ok=True)
        retired = retired_dir / path.name
        path.replace(retired)
    manifest.setdefault("removed_captures", []).append({
        **capture, "image_path": str(retired) if retired else capture.get("image_path"),
        "removed_utc": _utc(), "reason": reason, "replaced_by": replaced_by,
    })
    return retired


@router.get("/sessions/{session_id}/images")
def list_images(session_id: str):
    """Active (non-removed) captures for the gallery; file names only, no filesystem paths."""
    manifest = _manifest(_session_dir(session_id))
    return {"session_id": session_id, "images": _image_list(manifest), "captures": _capture_counts(manifest)}


@router.get("/sessions/{session_id}/images/{image_id}")
def image_file(session_id: str, image_id: str):
    session_dir = _session_dir(session_id)
    _, path = _active_capture(session_dir, _manifest(session_dir), image_id)
    if not path.is_file():
        raise HTTPException(404, "Image file missing")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.delete("/sessions/{session_id}/images/{image_id}")
def delete_image(session_id: str, image_id: str):
    """Remove ONE image from active evidence. Other images, answers and PPG are untouched."""
    session_dir = _session_dir(session_id)
    manifest = _manifest(session_dir)
    index, path = _active_capture(session_dir, manifest, image_id)
    _retire(session_dir, manifest, index, path, reason="removed_by_operator")
    manifest["evidence_changed_utc"] = datetime.now(timezone.utc).isoformat(timespec="microseconds")  # marks earlier analysis as outdated
    _write_manifest(session_dir, manifest)
    return {"session_id": session_id, "removed": image_id, "images": _image_list(manifest), "captures": _capture_counts(manifest)}


@router.post("/sessions/{session_id}/images")
async def upload_image(
    session_id: str,
    modality: str = Query(pattern="^(conjunctiva|nails|tongue)$"),
    image: UploadFile = File(...),
    replaces: Annotated[str | None, Query()] = None,
):
    """Store one browser webcam capture (re-encoded PNG, metadata stripped).

    With `replaces`, the original is retired only after the new image is saved; on any failure it stays active.
    """
    session_dir = _session_dir(session_id)
    if not _questionnaire_row(session_id)["status"].get("image_acquisition_allowed"):
        raise HTTPException(403, "Image capture is not permitted by the questionnaire consent")
    manifest = _manifest(session_dir)
    original = _active_capture(session_dir, manifest, replaces) if replaces else None  # validate before writing
    raw = await image.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image larger than 10 MB")
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(422, "Upload is not a readable image")

    folder = session_dir / "images" / modality
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    image_path = folder / f"{modality}_{stamp}.png"
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise HTTPException(500, "Could not encode image")
    encoded.tofile(str(image_path))

    manifest["captures"].append({
        "modality": modality,
        "captured_utc": _utc(),
        "image_path": str(image_path),
        "camera_index": "browser",
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
    })
    retired = None
    try:
        if original:
            retired = _retire(session_dir, manifest, original[0], original[1], reason="replaced_by_retake",
                              replaced_by=image_path.name)
        manifest["evidence_changed_utc"] = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        _write_manifest(session_dir, manifest)
    except OSError as exc:  # undo: keep the original active and drop the new file
        if retired is not None and retired.is_file():
            retired.replace(original[1])
        image_path.unlink(missing_ok=True)
        raise HTTPException(500, "Could not save the image; the original image was kept") from exc
    return {"session_id": session_id, "modality": modality, "image_id": image_path.name, "replaced": replaces,
            "images": _image_list(manifest), "captures": _capture_counts(manifest)}


# ---------------------------------------------------------------- PPG


PPG_MIN_SECONDS, PPG_MAX_SECONDS = 5, 60


class PpgRecordIn(BaseModel):
    seconds: int = Field(default=20, ge=PPG_MIN_SECONDS, le=PPG_MAX_SECONDS)


def _recording_summary(session_id: str, recording_file: str) -> dict[str, Any]:
    """Saved SQLite record for one recording, with plain-language technical-quality reasons."""
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        rec = conn.execute(
            "SELECT id, sample_count, quality_status, observed_receive_rate_hz, quality_report_json "
            "FROM ppg_live_recordings WHERE session_id = ? AND recording_file = ?",
            (session_id, recording_file),
        ).fetchone()
        if rec is None:
            raise RuntimeError("Recording was not found in SQLite after saving")
        vitals = conn.execute(
            "SELECT hr_bpm, spo2_percent, temperature_c, finger_present FROM ppg_live_vitals WHERE recording_id = ?",
            (rec[0],),
        ).fetchall() if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppg_live_vitals'"
        ).fetchone() else []
    report = json.loads(rec[4]) if rec[4] else {}
    windows = report.get("window_checks") or []
    passed = sum(1 for w in windows if w.get("candidate"))
    reasons = [f"{passed} of {len(windows)} five-second windows passed the technical checks "
               "(IR level > 5000, IR baseline swing < 5%, RED/IR band correlation > 0.65, pulse amplitude in range)."]
    for w in windows:
        if w.get("candidate"):
            continue
        problems = []
        if w.get("relative_ir_swing", 0) >= 0.05:
            problems.append("IR baseline moved ≥5% (finger movement or pressure)")
        if w.get("red_ir_band_correlation", 1) <= 0.65:
            problems.append("weak RED/IR pulse agreement")
        if not problems:
            problems.append("IR level or pulse amplitude out of range (check finger contact)")
        reasons.append(f"{w.get('start_s')}–{w.get('end_s')} s: " + "; ".join(problems))
    hr = [v[0] for v in vitals if v[0] is not None]
    spo2 = [v[1] for v in vitals if v[1] is not None]
    temp = [v[2] for v in vitals if v[2] is not None]
    return {
        "session_id": session_id,
        "recording_id": rec[0],
        "recording_file": recording_file,
        "sample_count": rec[1],
        "quality_status": rec[2],
        "quality_passed": rec[2] == "candidate_for_pulse_validation",
        "quality_reasons": reasons,
        "observed_receive_rate_hz": rec[3],
        "metrics_count": len(vitals),
        "finger_present_fraction": round(sum(v[3] for v in vitals) / len(vitals), 2) if vitals else None,
        # Device-reported values only; None when the firmware sent "null".
        "median_experimental_hr_bpm": median(hr) if hr else None,
        "median_experimental_spo2_percent": median(spo2) if spo2 else None,
        "median_temperature_c": median(temp) if temp else None,  # Shown as N/A: no temperature sensor fitted.
        "hb_model_applied": False,
    }


# Single owner of the serial port: one background job at a time (recording or probe).
_job_lock = threading.Lock()
_stop_event = threading.Event()
_job: dict[str, Any] = {"state": "idle"}


def _job_update(**fields: Any) -> None:
    with _job_lock:
        _job.update(fields)


def _serial_error(port: str, text: str) -> tuple[str, str]:
    """Classify pyserial errors into states the UI can explain."""
    lowered = text.lower()
    if "filenotfounderror" in lowered or "cannot find" in lowered or "no such file" in lowered:
        return "port_not_found", f"{port} is not available. Plug in the ESP32 USB cable or check the COM port."
    if "permissionerror" in lowered or "access is denied" in lowered or "busy" in lowered:
        return "port_busy", (
            f"{port} is in use by another program. Close Arduino Serial Monitor, the Streamlit Live PPG page "
            "or any other serial tool, then try again."
        )
    if "no red/ir data" in lowered:
        return "no_samples", (
            f"{port} opened but no valid RED/IR rows arrived. Check that the AyurAI firmware is running "
            "(115200 baud) and the finger is on the sensor."
        )
    return "serial_error", text.splitlines()[0] if text else "Serial error"


def _ports(port: str) -> dict[str, Any]:
    from serial.tools import list_ports

    listed = [{"device": p.device, "description": p.description} for p in list_ports.comports()]
    return {"ports": listed, "port_listed": any(p["device"] == port for p in listed)}


def _serial_config() -> tuple[str, int]:
    return _setting("C1_SERIAL_PORT", "COM11"), int(_setting("C1_SERIAL_BAUD", "115200"))


def _hardware(port: str) -> dict[str, Any]:
    """Port listing, or an explicit 'disabled' state when this server has no USB sensor (no server ports listed)."""
    if not SERIAL_ENABLED:
        return {"serial_enabled": False, "ports": [], "port_listed": False}
    return {"serial_enabled": True, **_ports(port)}


@router.get("/ppg/capture-options")
def ppg_capture_options():
    """Which PPG capture paths this server offers; the PPG step shows controls accordingly."""
    _, baud = _serial_config()
    return {"server_serial_enabled": SERIAL_ENABLED, "browser_upload_enabled": PPG_UPLOAD_ENABLED, "baud": baud,
            "min_seconds": PPG_MIN_SECONDS, "max_seconds": PPG_MAX_SECONDS}


@router.get("/hardware/serial-ports")
def serial_ports():
    port, baud = _serial_config()
    return {"configured_port": port, "configured_baud": baud, **_hardware(port)}


@router.get("/hardware/ppg-job")
def ppg_job():
    """Current or last serial job. 'port_listed' only means Windows lists the port, not that samples arrive."""
    with _job_lock:
        job = dict(_job)
    started = job.get("recording_started_monotonic")
    if job.get("state") in ("port_open", "receiving") and started:
        job["elapsed_s"] = round(min(time.monotonic() - started, job.get("seconds", 0)), 1)
    job.pop("recording_started_monotonic", None)
    port, baud = _serial_config()
    return {"configured_port": port, "configured_baud": baud, **_hardware(port), "job": job}


@router.post("/hardware/ppg-job/cancel")
def cancel_ppg_job():
    with _job_lock:
        running = _job.get("state") in ("opening", "port_open", "receiving")
    if running:
        _stop_event.set()
    return {"cancel_requested": running}


def _start_job(kind: str, target, **fields: Any) -> dict[str, Any]:
    if not SERIAL_ENABLED:
        raise HTTPException(503, SERIAL_DISABLED_MESSAGE)
    if not _serial_lock.acquire(blocking=False):
        raise HTTPException(409, "The PPG sensor is already in use by another recording or check")
    _stop_event.clear()
    port, baud = _serial_config()
    job_id = uuid.uuid4().hex[:8]
    with _job_lock:
        _job.clear()
        _job.update(job_id=job_id, kind=kind, state="opening", port=port, baud=baud, samples=0, metrics=0,
                    finger_present=None, last_hr_bpm=None, last_spo2_percent=None, started_utc=_utc(), **fields)

    def runner():
        try:
            target(port, baud)
        except Exception as exc:  # Never leave the job "running" after an unexpected error.
            _job_update(state="failed", error_kind="unexpected", error=str(exc))
        finally:
            _serial_lock.release()

    threading.Thread(target=runner, name=f"c1-ppg-{kind}", daemon=True).start()
    with _job_lock:
        return dict(_job)


def _on_progress(stage: str, samples: int, metrics: int, last: tuple | None) -> None:
    fields: dict[str, Any] = {"samples": samples, "metrics": metrics}
    if stage == "opening":
        fields["state"] = "opening"
    else:
        fields["state"] = "receiving" if samples else "port_open"
        if stage == "recording":
            with _job_lock:
                if not _job.get("recording_started_monotonic"):
                    fields["recording_started_monotonic"] = time.monotonic()
    if last is not None:
        _, hr, spo2, _, finger = last
        fields.update(finger_present=bool(finger), last_hr_bpm=hr, last_spo2_percent=spo2)
    _job_update(**fields)


@router.post("/sessions/{session_id}/ppg/record", status_code=202)
def record_ppg(session_id: str, body: PpgRecordIn):
    """Start recording RED/IR from the ESP32 (background job); poll GET /hardware/ppg-job for progress."""
    _session_dir(session_id)
    status = _questionnaire_row(session_id)["status"]
    if status.get("ppg_pending_finger_comfort_check", True):
        raise HTTPException(403, "Complete the finger-comfort check before recording")
    if not status.get("ppg_acquisition_allowed"):
        raise HTTPException(403, "PPG recording is not permitted by consent or the comfort check")

    import matplotlib

    matplotlib.use("Agg")  # Figures are saved to files; no GUI window from a server thread.
    from component1.acquisition.ppg import capture_live_ppg, register_session_ppg, register_session_vitals
    from component1.quality.ppg.assess_live_ppg import assess

    def run(port: str, baud: int) -> None:
        try:
            csv_path = capture_live_ppg.record(
                port, body.seconds, session_id, baud, on_progress=_on_progress, stop_event=_stop_event,
            )
        except capture_live_ppg.RecordingCancelled:
            _job_update(state="cancelled", error="Recording cancelled; nothing was saved.")
            return
        except SystemExit as exc:  # The recorder reports serial/data errors this way.
            kind, text = _serial_error(port, str(exc))
            _job_update(state="failed", error_kind=kind, error=text)
            return
        _job_update(state="processing")
        try:
            assess(csv_path, csv_path.parent)
            csv_file, report_file = register_session_ppg.find_recording(session_id)
            if csv_file.name != csv_path.name:
                raise RuntimeError("Newest quality-checked recording does not match this capture")
            register_session_ppg.save(session_id, csv_file, report_file, DB_PATH)
            metrics_file = csv_path.parent / csv_path.name.replace("ppg_red_ir_", "ppg_metrics_", 1)
            if metrics_file.is_file():  # Only link vitals that belong to THIS recording.
                register_session_vitals.register_vitals(session_id)
            result = _recording_summary(session_id, csv_path.name)
        except (ValueError, FileNotFoundError, RuntimeError, sqlite3.Error) as exc:
            _job_update(state="failed", error_kind="processing_failed",
                        error=f"Samples were saved to {csv_path.name} but processing failed: {exc}")
            return
        _job_update(state="saved", result=result)

    return _start_job("recording", run, session_id=session_id, seconds=body.seconds)


@router.post("/hardware/ppg-probe", status_code=202)
def probe_ppg():
    """~4 s live-signal check: opens the port and counts valid RED/IR rows. Nothing is saved."""
    import serial

    from component1.acquisition.ppg.capture_live_ppg import parse_metrics_line, parse_sensor_line

    def run(port: str, baud: int) -> None:
        rows = metrics = 0
        last = None
        try:
            with serial.Serial(port, baud, timeout=0.5) as ser:
                _job_update(state="port_open")
                time.sleep(2.0)  # The ESP32 restarts when the port opens.
                ser.reset_input_buffer()
                end = time.monotonic() + 4.0
                while time.monotonic() < end and not _stop_event.is_set():
                    line = ser.readline().decode("ascii", errors="replace").strip()
                    if line.startswith("#METRICS,"):
                        parsed = parse_metrics_line(line)
                        if parsed:
                            metrics += 1
                            last = parsed
                    elif parse_sensor_line(line):
                        rows += 1
                    _on_progress("probe", rows, metrics, last)
        except serial.SerialException as exc:
            kind, text = _serial_error(port, str(exc))
            _job_update(state="failed", error_kind=kind, error=text)
            return
        if rows == 0:
            kind, text = _serial_error(port, "No RED/IR data")
            _job_update(state="failed", error_kind=kind, error=text, samples=0)
            return
        _job_update(state="probe_ok", result={"valid_rows": rows, "rows_per_second": round(rows / 4.0, 1),
                                               "metrics": metrics, "saved": False})

    return _start_job("probe", run)


# ---------------------------------------------------------------- PPG upload (browser Web Serial)

# Same CSV columns capture_live_ppg writes; same RED/IR range as capture_live_ppg.parse_sensor_line.
PPG_SAMPLE_COLUMNS = ["host_elapsed_s", "esp32_readout_ms", "red", "ir"]
PPG_METRIC_COLUMNS = ["time_ms", "hr_bpm", "spo2_percent", "temperature_c", "finger_present"]
PPG_ADC_MAX = 262143
MAX_PPG_SAMPLES_CSV = 400_000  # 60 s at 100 rows/s is about 240 kB; the firmware sends about 25 rows/s.
MAX_PPG_METRICS_CSV = 20_000
UPLOAD_REGISTRY = "browser_uploads.json"
_upload_lock = threading.Lock()


class PpgUploadIn(BaseModel):
    upload_id: str = Field(pattern=r"^[0-9a-f]{32}$")  # One per captured recording: retries are idempotent.
    seconds: int = Field(ge=PPG_MIN_SECONDS, le=PPG_MAX_SECONDS)
    samples_csv: str = Field(max_length=MAX_PPG_SAMPLES_CSV)
    metrics_csv: str = Field(default="", max_length=MAX_PPG_METRICS_CSV)


def _csv_rows(text: str, columns: list[str], label: str) -> list[list[str]]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or [c.strip() for c in rows[0]] != columns:
        raise HTTPException(422, f"{label}: the first line must be {','.join(columns)}")
    if any(len(row) != len(columns) for row in rows[1:]):
        raise HTTPException(422, f"{label}: every row needs {len(columns)} values")
    return rows[1:]


def _optional_int(value: str, low: int, high: int) -> int | None:
    if value.strip() == "":
        return None
    number = int(value)
    if not low <= number <= high:
        raise ValueError(f"{number} outside {low}-{high}")
    return number


def _parse_ppg_upload(body: PpgUploadIn) -> tuple[list[tuple], list[tuple]]:
    """Validate an uploaded recording; returns rows in capture_live_ppg's own types."""
    samples, last_elapsed = [], 0.0
    for index, row in enumerate(_csv_rows(body.samples_csv, PPG_SAMPLE_COLUMNS, "PPG samples"), start=2):
        try:
            elapsed, esp32_ms, red, ir = float(row[0]), int(row[1]), int(row[2]), int(row[3])
        except ValueError:
            raise HTTPException(422, f"PPG samples line {index}: values must be numbers") from None
        if not math.isfinite(elapsed) or elapsed < last_elapsed or esp32_ms < 0 \
                or not (0 <= red <= PPG_ADC_MAX and 0 <= ir <= PPG_ADC_MAX):
            raise HTTPException(422, f"PPG samples line {index}: value out of range or time going backwards")
        last_elapsed = elapsed
        samples.append((round(elapsed, 6), esp32_ms, red, ir))
    if len(samples) < 50:
        raise HTTPException(422, "Too few RED/IR samples; record again with the finger on the sensor")
    if not body.seconds * 0.75 <= last_elapsed <= body.seconds + 2:
        raise HTTPException(422, f"Recording lasts {last_elapsed:.1f} s; expected about {body.seconds} s")
    if not 5 <= len(samples) / max(last_elapsed, 1e-6) <= 150:
        raise HTTPException(422, "Implausible sample rate; check the firmware and baud rate")

    metrics = []
    rows = _csv_rows(body.metrics_csv, PPG_METRIC_COLUMNS, "PPG metrics") if body.metrics_csv.strip() else []
    for index, row in enumerate(rows, start=2):
        try:
            time_ms = int(row[0])
            temperature = None if row[3].strip() == "" else float(row[3])
            finger = int(row[4])
            metric = (time_ms, _optional_int(row[1], 0, 300), _optional_int(row[2], 0, 100), temperature, finger)
        except ValueError:
            raise HTTPException(422, f"PPG metrics line {index}: invalid value") from None
        if time_ms < 0 or finger not in (0, 1) or (temperature is not None and not math.isfinite(temperature)):
            raise HTTPException(422, f"PPG metrics line {index}: value out of range")
        metrics.append(metric)
    return samples, metrics


@router.post("/sessions/{session_id}/ppg/upload", status_code=201)
def upload_ppg(session_id: str, body: PpgUploadIn):
    """Save a recording captured in the browser over Web Serial; processed exactly like a USB recording.

    Disabled unless C1_PPG_UPLOAD_ENABLED=true. Same consent, safety-referral and finger-comfort rules as
    /ppg/record. Retrying with the same upload_id returns the recording already saved (no duplicate).
    """
    if not PPG_UPLOAD_ENABLED:
        raise HTTPException(503, "Browser PPG upload is not enabled on this server")
    session_dir = _session_dir(session_id)
    status = _questionnaire_row(session_id)["status"]  # Refuses safety-referral and non-demo sessions.
    if status.get("ppg_pending_finger_comfort_check", True):
        raise HTTPException(403, "Complete the finger-comfort check before recording")
    if not status.get("ppg_acquisition_allowed"):
        raise HTTPException(403, "PPG recording is not permitted by consent or the comfort check")
    samples, metrics = _parse_ppg_upload(body)

    import matplotlib

    matplotlib.use("Agg")
    from component1.acquisition.ppg import capture_live_ppg, register_session_ppg, register_session_vitals
    from component1.quality.ppg.assess_live_ppg import assess

    ppg_dir = session_dir / "ppg"
    with _upload_lock:
        registry_path = ppg_dir / UPLOAD_REGISTRY
        registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
        if body.upload_id in registry:
            return {**_recording_summary(session_id, registry[body.upload_id]), "duplicate": True}
        ppg_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            csv_path = capture_live_ppg.save_recording(ppg_dir, session_id, samples, metrics, stamp)
        except FileExistsError:
            raise HTTPException(409, "Another recording was saved this second; retry the upload") from None
        registered = False
        try:
            assess(csv_path, csv_path.parent)
            csv_file, report_file = register_session_ppg.find_recording(session_id)
            if csv_file.name != csv_path.name:
                raise RuntimeError("Newest quality-checked recording does not match this upload")
            register_session_ppg.save(session_id, csv_file, report_file, DB_PATH)
            registered = True
            if metrics:
                register_session_vitals.register_vitals(session_id)
            result = _recording_summary(session_id, csv_path.name)
        except (ValueError, FileNotFoundError, RuntimeError, sqlite3.Error) as exc:
            if not registered:  # Nothing reached SQLite: remove this upload's files so a retry starts clean.
                for leftover in ppg_dir.glob(f"*{stamp}*"):
                    leftover.unlink(missing_ok=True)
            raise HTTPException(422, f"PPG processing failed: {exc}") from exc
        registry[body.upload_id] = csv_path.name
        tmp = registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        tmp.replace(registry_path)
    return {**result, "duplicate": False}


# ---------------------------------------------------------------- analysis


@router.post("/sessions/{session_id}/analyze")
def analyze(session_id: str):
    """Image quality checks + existing trained models (if images exist), then fusion; returns the report.

    Safety-referral sessions never run models or fusion: their referral record is (re)saved instead.
    """
    session_dir = _session_dir(session_id)
    if _completion_status(session_id) == REFERRAL_STATUS:
        from component1.api.server import save_session_outputs

        return save_session_outputs(session_id)
    _questionnaire_row(session_id)
    if _manifest(session_dir).get("captures"):
        from component1.quality.images.assess_webcam_quality import inspect_session

        sys.path.insert(0, str(C1_ROOT / "models" / "images"))
        from evaluate_webcam_session import evaluate_session

        try:
            inspect_session(session_dir)
            evaluate_session(session_id)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(422, f"Image analysis failed: {exc}") from exc
    else:
        # All images were removed: keep earlier per-image results for audit, but out of fusion's inputs.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for name in ("quality_report.json", "image_model_results.json"):
            if (session_dir / name).is_file():
                (session_dir / "_superseded").mkdir(exist_ok=True)
                (session_dir / name).replace(session_dir / "_superseded" / f"{stamp}_{name}")

    from component1.api.server import save_session_outputs
    from component1.fusion.fuse_screening_session import fuse_session

    try:
        fuse_session(session_id)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return save_session_outputs(session_id)
