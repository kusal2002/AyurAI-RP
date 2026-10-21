"""AyurAI Component 1: clinical intake routes for the shared frontend.

FICTIONAL DEMO SESSIONS ONLY (demo_XXXXXXXX). Every route reuses the existing
Component 1 acquisition, quality, model and fusion code; nothing is reimplemented.

Consent and safety are enforced here, server-side:
- images require questionnaire image consent (image_acquisition_allowed);
- PPG requires PPG consent plus the finger-comfort check at the sensor.

Hardware: local USB serial only (ESP32-S3 + MAX30102). Port and baud come from
component1/.env (C1_SERIAL_PORT, C1_SERIAL_BAUD), defaulting to COM11 / 115200.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
C1_ROOT = REPO_ROOT / "component1"
DATA_ROOT = REPO_ROOT.parent / "datasets"
SESSIONS_ROOT = DATA_ROOT / "live_sessions"
DB_PATH = DATA_ROOT / "screening_sessions.sqlite3"
MODALITIES = ("conjunctiva", "nails", "tongue")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
PPG_COMFORT_IDS = ("P02", "P03", "P05", "P06", "P07")

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


def _questionnaire_row(session_id: str) -> dict[str, Any]:
    if not DB_PATH.is_file():
        raise HTTPException(409, "Complete the questionnaire first")
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT is_fictional_demo, profile_json, answers_json, status_json "
            "FROM questionnaire_responses WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(409, "Complete the questionnaire first")
    if row[0] != 1:
        raise HTTPException(403, "Patient data requires authenticated clinical API")
    return {"profile": json.loads(row[1]), "answers": json.loads(row[2]), "status": json.loads(row[3])}


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


def _profile(profile: ProfileIn) -> dict:
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


@router.post("/sessions/{session_id}/questionnaire")
def save_questionnaire(session_id: str, body: QuestionnaireIn):
    _session_dir(session_id)
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE questionnaire_responses SET answers_json = ?, status_json = ?, updated_at_utc = ? "
            "WHERE session_id = ? AND is_fictional_demo = 1",
            (json.dumps(answers), json.dumps(status), _utc(), session_id),
        )
    return {"session_id": session_id, "status": status}


# ---------------------------------------------------------------- images


@router.post("/sessions/{session_id}/images")
async def upload_image(
    session_id: str,
    modality: str = Query(pattern="^(conjunctiva|nails|tongue)$"),
    image: UploadFile = File(...),
):
    """Store one browser webcam capture against the session (re-encoded PNG, metadata stripped)."""
    session_dir = _session_dir(session_id)
    if not _questionnaire_row(session_id)["status"].get("image_acquisition_allowed"):
        raise HTTPException(403, "Image capture is not permitted by the questionnaire consent")
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

    manifest = _manifest(session_dir)
    manifest["captures"].append({
        "modality": modality,
        "captured_utc": _utc(),
        "image_path": str(image_path),
        "camera_index": "browser",
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
    })
    tmp = session_dir / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(session_dir / "manifest.json")
    return {"session_id": session_id, "modality": modality, "captures": _capture_counts(manifest)}


# ---------------------------------------------------------------- PPG


class PpgRecordIn(BaseModel):
    seconds: int = Field(default=20, ge=5, le=60)


@router.get("/hardware/serial-ports")
def serial_ports():
    from serial.tools import list_ports

    config = _env()
    return {
        "configured_port": config.get("C1_SERIAL_PORT", "COM11"),
        "configured_baud": int(config.get("C1_SERIAL_BAUD", "115200")),
        "ports": [{"device": p.device, "description": p.description} for p in list_ports.comports()],
    }


def _latest_ppg_summary(session_id: str) -> dict[str, Any]:
    with sqlite3.connect(DB_PATH) as conn:
        rec = conn.execute(
            "SELECT id, sample_count, quality_status, observed_receive_rate_hz FROM ppg_live_recordings "
            "WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        vitals = conn.execute(
            "SELECT hr_bpm, spo2_percent, temperature_c FROM ppg_live_vitals WHERE recording_id = ?",
            (rec[0],),
        ).fetchall() if rec else []
    hr = [v[0] for v in vitals if v[0] is not None]
    spo2 = [v[1] for v in vitals if v[1] is not None]
    temp = [v[2] for v in vitals if v[2] is not None]
    return {
        "recording_id": rec[0] if rec else None,
        "sample_count": rec[1] if rec else 0,
        "quality_status": rec[2] if rec else None,
        "observed_receive_rate_hz": rec[3] if rec else None,
        "metrics_count": len(vitals),
        "median_experimental_hr_bpm": median(hr) if hr else None,
        "median_experimental_spo2_percent": median(spo2) if spo2 else None,
        # None (shown as N/A) unless a temperature sensor actually reported values.
        "median_temperature_c": median(temp) if temp else None,
        "hb_model_applied": False,
    }


@router.post("/sessions/{session_id}/ppg/record")
def record_ppg(session_id: str, body: PpgRecordIn):
    """Record RED/IR from the ESP32 over USB, then run the existing quality and SQLite steps."""
    _session_dir(session_id)
    status = _questionnaire_row(session_id)["status"]
    if status.get("ppg_pending_finger_comfort_check", True):
        raise HTTPException(403, "Complete the finger-comfort check before recording")
    if not status.get("ppg_acquisition_allowed"):
        raise HTTPException(403, "PPG recording is not permitted by consent or the comfort check")

    import matplotlib

    matplotlib.use("Agg")  # Figures are saved to files; no GUI window from a server thread.
    from component1.acquisition.ppg.capture_live_ppg import record
    from component1.acquisition.ppg.register_session_ppg import find_recording, save
    from component1.acquisition.ppg.register_session_vitals import register_vitals
    from component1.quality.ppg.assess_live_ppg import assess

    config = _env()
    port = config.get("C1_SERIAL_PORT", "COM11")
    baud = int(config.get("C1_SERIAL_BAUD", "115200"))
    if not _serial_lock.acquire(blocking=False):
        raise HTTPException(409, "A PPG recording is already in progress")
    try:
        try:
            record(port, body.seconds, session_id, baud)
        except SystemExit as exc:  # The recorder reports serial/data errors this way.
            raise HTTPException(503, str(exc)) from None
        folder = SESSIONS_ROOT / session_id / "ppg"
        latest = sorted(folder.glob("ppg_red_ir_*.csv"))[-1]
        try:
            assess(latest, folder)
            csv_file, report_file = find_recording(session_id)
            save(session_id, csv_file, report_file, DB_PATH)
            if sorted(folder.glob("ppg_metrics_*.csv")):
                register_vitals(session_id)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(422, f"Recording saved but processing failed: {exc}") from exc
    finally:
        _serial_lock.release()
    return {"session_id": session_id, "port": port, **_latest_ppg_summary(session_id)}


# ---------------------------------------------------------------- analysis


@router.post("/sessions/{session_id}/analyze")
def analyze(session_id: str):
    """Image quality checks + existing trained models (if images exist), then fusion; returns the report."""
    session_dir = _session_dir(session_id)
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

    from component1.api.server import save_session_outputs
    from component1.fusion.fuse_screening_session import fuse_session

    try:
        fuse_session(session_id)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return save_session_outputs(session_id)
