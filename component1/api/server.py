"""AyurAI Component 1: localhost-only PP1 session API.

Run from repository root:
    component1\\.venv\\Scripts\\python.exe -m uvicorn component1.api.server:app --host 127.0.0.1 --port 8001

FastAPI routes are served under /api/c1/... (e.g. /api/c1/health). The browser stays
at http://localhost:5173 and calls /c1-api/...; the Vite dev server proxy
(ayurai-client/vite.config.ts) strips the /c1-api prefix and forwards to this
service, so /c1-api/api/c1/health -> http://127.0.0.1:8001/api/c1/health.
No Firebase, Groq, or Component 2 dependency.

This PP1 prototype exposes FICTIONAL DEMO SESSIONS ONLY. Add authentication,
access controls and approval before handling identifiable patient records.
"""

from __future__ import annotations

import json
from contextlib import closing
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT.parent / "datasets"
SESSIONS_ROOT = DATA_ROOT / "live_sessions"
DB_PATH = DATA_ROOT / "screening_sessions.sqlite3"
QUESTION_BANK = REPO_ROOT / "component1" / "acquisition" / "questionnaire" / "question_bank_v1.json"
DEMO_SESSION = re.compile(r"demo_[A-Za-z0-9]{8}\Z")
# Screening record files written into each session folder on analysis / re-run fusion.
SAVED_OUTPUTS = ("screening_report.json", "screening_result.json", "c2_payload.json")
SESSION_EVIDENCE_FILES = ("manifest.json", "quality_report.json", "image_model_results.json", "fusion_report.json")
# Urgent safety answers end routine screening; the session keeps a referral-only record.
REFERRAL_STATUS = "safety_referral"
REFERRAL_FILE = "safety_referral.json"
MODALITY_KEYS = ("conjunctiva", "nails", "tongue")

app = FastAPI(title="AyurAI Component 1 API", version="0.1.0")


def _session_dir(session_id: str) -> Path:
    if not DEMO_SESSION.fullmatch(session_id):
        raise HTTPException(400, "Only demo_XXXXXXXX sessions are available in this prototype")
    path = SESSIONS_ROOT / session_id
    if not path.is_dir():
        raise HTTPException(404, "Session not found")
    return path


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError) as exc:
        raise HTTPException(500, f"Cannot read {path.name}") from exc


def _db_questionnaire(session_id: str) -> dict[str, Any] | None:
    if not DB_PATH.is_file():
        return None
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.row_factory = sqlite3.Row
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='questionnaire_responses'"
        ).fetchone()
        if not exists:
            return None
        row = conn.execute(
            """SELECT is_fictional_demo, scenario, profile_json, answers_json,
                      status_json, completion_status, updated_at_utc
               FROM questionnaire_responses WHERE session_id = ?""",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    if row["is_fictional_demo"] != 1:
        raise HTTPException(403, "Patient data requires authenticated clinical API")

    def parsed(column):
        try:
            return json.loads(row[column]) if row[column] else {}
        except ValueError:
            return {}

    return {
        "scenario": row["scenario"],
        "profile": parsed("profile_json"),
        "answers": parsed("answers_json"),
        "status": parsed("status_json"),
        "completion_status": row["completion_status"],
        "updated_at_utc": row["updated_at_utc"],
        "fictional_demo": True,
    }


def _question_items(answers: dict) -> list[dict]:
    bank = _json(QUESTION_BANK)
    labels = {
        q["id"]: {"question": q.get("prompt", q["id"]), "section": q.get("section", "other")}
        for q in bank.get("questions", []) if isinstance(q, dict) and q.get("id")
    }
    # Suppress registration identifiers, even in demo output.
    return [
        {"question_id": code, **labels.get(code, {"question": code, "section": "other"}), "answer": value}
        for code, value in answers.items()
        if code not in {"REG01", "CH01"}
    ]


def _workflow(questionnaire: dict | None, session_dir: Path, fusion: dict) -> list[dict]:
    image_report = _json(session_dir / "image_model_results.json")
    quality = _json(session_dir / "quality_report.json")
    manifest = _json(session_dir / "manifest.json")
    image_count = len(image_report.get("images", []))
    captures = manifest.get("captures")
    manifest_count = len(captures) if isinstance(captures, list) else 0
    ppg = fusion.get("ppg", {})
    steps = [
        ("registration", "Create coded patient session", bool(manifest) or bool(questionnaire)),
        ("questionnaire", "Consent and guided clinical interview", questionnaire is not None),
        ("webcam", "Capture conjunctiva, tongue and nail images", bool(quality) or manifest_count > 0),
        ("image_ai", "Image quality checks and trained model inference", image_count > 0),
        ("ppg", "Record RED/IR and experimental vital signs", bool(ppg.get("available"))),
        ("fusion", "Build multimodal screening evidence", bool(fusion)),
        ("clinician", "Review patient-wise screening report", False),
    ]
    return [
        {"key": key, "label": label, "status": "complete" if done else "pending"}
        for key, label, done in steps
    ]


def _doctor_narrative(fusion: dict, questionnaire: dict | None) -> dict[str, Any]:
    images = fusion.get("images", {})
    ppg = fusion.get("ppg", {})
    observations = []
    if images.get("image_count", 0):
        observations.append(f"{images['image_count']} webcam photographs reviewed by the image pipeline.")
    for name, region in images.get("regions", {}).items():
        observations.append(
            f"{name.title()}: {region.get('technical_passes', 0)}/{region.get('captures', 0)} technical checks passed; "
            f"{len(region.get('model_votes', []))} classification output(s), "
            f"{len(region.get('experimental_hb_estimates_g_dl', []))} Hb regression output(s)."
        )
    if ppg.get("available"):
        observations.append(
            f"PPG: {ppg.get('sample_count', 0)} RED/IR samples, {ppg.get('metrics_count', 0)} metrics; "
            f"technical status {ppg.get('quality_status', 'unknown')}."
        )
        if ppg.get("median_experimental_hr_bpm") is not None:
            observations.append(f"Experimental median heart rate: {ppg['median_experimental_hr_bpm']} bpm.")
        if ppg.get("median_experimental_spo2_percent") is not None:
            observations.append(f"Experimental median SpO2: {ppg['median_experimental_spo2_percent']}%.")
    if questionnaire:
        observations.append(f"Guided interview: {len(questionnaire['answers'])} responses stored; status {questionnaire['completion_status']}.")
    screening = fusion.get("screening", {})
    tier = fusion.get("experimental_risk_tier")
    if tier:
        summary = (
            f"Experimental tier: {TIER_LABELS.get(tier, tier)} "
            f"(reliability score {fusion.get('reliability_score')}, a heuristic, not a probability). "
            "Unvalidated rules; review evidence and limitations before acting."
        )
    else:
        summary = "No experimental tier generated yet; re-run fusion and review safety flags."
    return {
        "headline": "Component 1 experimental anaemia screening — clinician review",
        "summary": summary,
        "observations": observations,
        "rationale": screening.get("rationale", []),
        "safety_flags": screening.get("safety_flags", []),
        "recommendations": screening.get("doctor_review_recommendations", []),
        "reliability_flags": fusion.get("reliability_flags", []),
        "limitations": fusion.get("limitations", []),
        "clinical_action": "This report is screening research evidence; do not use as a diagnosis or replace laboratory Hb testing.",
    }


def _is_referral(questionnaire: dict | None) -> bool:
    return bool(questionnaire) and questionnaire.get("completion_status") == REFERRAL_STATUS


def _saved_images(session_dir: Path) -> dict[str, int]:
    captures = _json(session_dir / "manifest.json").get("captures")
    captures = captures if isinstance(captures, list) else []
    return {m: sum(c.get("modality") == m for c in captures if isinstance(c, dict)) for m in MODALITY_KEYS}


def workflow_state(session_dir: Path, questionnaire: dict | None) -> str:
    """Derived from persisted evidence only (no separate state table)."""
    if questionnaire is None:
        return "created"
    if _is_referral(questionnaire):
        return REFERRAL_STATUS
    record = session_dir / SAVED_OUTPUTS[0]
    evidence = [session_dir / "manifest.json", *(session_dir / "ppg").glob("ppg_red_ir_*.csv")]
    newest_evidence = max((p.stat().st_mtime for p in evidence if p.is_file()), default=0)
    if record.is_file() and record.stat().st_mtime >= newest_evidence:
        return "completed"
    status = questionnaire.get("status", {})
    answers = questionnaire.get("answers", {})
    if status.get("image_acquisition_allowed") and sum(_saved_images(session_dir).values()) == 0:
        return "images_in_progress"
    ppg_saved = any((session_dir / "ppg").glob("ppg_red_ir_*.csv"))
    ppg_possible = answers.get("REG06") == "yes" and (
        status.get("ppg_pending_finger_comfort_check", True) or status.get("ppg_acquisition_allowed")
    )
    if ppg_possible and not ppg_saved:
        return "ppg_in_progress"
    return "ready_for_analysis"


def _referral_report(session_id: str, session_dir: Path, questionnaire: dict) -> dict[str, Any]:
    """Referral-only outcome: no images, PPG, models or fusion; no anaemia-risk tier."""
    status = questionnaire.get("status", {})
    referral = _json(session_dir / REFERRAL_FILE)
    profile = questionnaire.get("profile", {})
    urgent = status.get("urgent_response_ids", [])
    unresolved = status.get("safety_unresolved", [])
    summary = (
        "SAFETY REFERRAL — routine screening stopped before image or PPG acquisition. "
        "Immediate clinician assessment required. No AI anaemia-risk classification was produced."
    )
    return {
        "schema_version": "c1.screening.v1",
        "session_id": session_id,
        "outcome": REFERRAL_STATUS,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "patient": {
            "reference": session_id,
            "fictional_demo": True,
            "age_months": profile.get("age_months"),
            "sex": profile.get("sex") or profile.get("sex_reported_for_demo"),
            "pregnancy_status": profile.get("pregnancy_status"),
        },
        "workflow_state": REFERRAL_STATUS,
        "workflow": [
            {"key": "registration", "label": "Create coded patient session", "status": "complete"},
            {"key": "questionnaire", "label": "Consent and guided clinical interview", "status": "complete"},
            {"key": "safety", "label": "Urgent safety answer: stop and refer", "status": "complete"},
            {"key": "routine_screening", "label": "Routine image/PPG screening", "status": "not_performed"},
        ],
        "questionnaire": {
            "available": True,
            "completion_status": REFERRAL_STATUS,
            "status": status,
            "responses": _question_items(questionnaire.get("answers", {})),
        },
        "referral": {
            "urgent_response_ids": urgent,
            "unresolved_safety_ids": unresolved,
            "not_asked_safety_ids": status.get("safety_not_asked", []),
            "referred_utc": referral.get("referred_utc") or questionnaire.get("updated_at_utc"),
            "reason": referral.get("reason") or "Urgent or unresolved safety answer.",
        },
        "modalities": {"images": {"image_count": 0}, "ppg": {"available": False}},
        "screening_result": {
            "risk_level": None,
            "risk_level_validated": False,
            "clinical_risk_category": None,
            "decision_status": "urgent_clinician_review_required",
            "reliability_score": None,
            "reliability_score_is_probability": False,
            "fusion_version": None,
            "contributing_factors": [f"Urgent safety answer: {qid}" for qid in urgent]
            + [f"Unresolved safety answer: {qid}" for qid in unresolved],
            "experimental": True,
        },
        "fusion": {},
        "missing_inputs": ["images", "ppg", "fusion (not performed: safety referral)"],
        "doctor_report": {
            "headline": "Component 1 — safety referral record",
            "summary": summary,
            "observations": [f"Guided interview: {len(questionnaire.get('answers', {}))} responses stored before referral."],
            "recommendations": ["Immediate clinician assessment for the urgent safety answer(s).",
                                "Do not continue routine AI screening for this session."],
            "reliability_flags": [],
            "limitations": ["Referral-only record: this is not an anaemia-risk classification."],
            "clinical_action": "Clinician review is required now; this record is not a diagnosis.",
        },
        "storage": _storage(session_dir),
    }


def _build_report(session_id: str) -> dict[str, Any]:
    session_dir = _session_dir(session_id)
    questionnaire = _db_questionnaire(session_id)
    if _is_referral(questionnaire):
        return _referral_report(session_id, session_dir, questionnaire)
    fusion = _json(session_dir / "fusion_report.json")
    img = _json(session_dir / "image_model_results.json")
    profile = (questionnaire or {}).get("profile", {})
    screening = fusion.get("screening", {})
    patient = {
        "reference": session_id,
        "fictional_demo": True,
        "age_months": profile.get("age_months"),
        "sex": profile.get("sex") or profile.get("sex_reported_for_demo"),
        "pregnancy_status": profile.get("pregnancy_status"),
    }
    return {
        "schema_version": "c1.screening.v1",
        "session_id": session_id,
        "outcome": "screening",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "patient": patient,
        "workflow_state": workflow_state(session_dir, questionnaire),
        "workflow": _workflow(questionnaire, session_dir, fusion),
        "questionnaire": {
            "available": questionnaire is not None,
            "completion_status": questionnaire.get("completion_status") if questionnaire else None,
            "status": questionnaire.get("status", {}) if questionnaire else {},
            "responses": _question_items(questionnaire["answers"]) if questionnaire else [],
        },
        "modalities": {
            "images": fusion.get("images", {"image_count": len(img.get("images", []))}),
            "ppg": fusion.get("ppg", {"available": False}),
        },
        "screening_result": {
            "risk_level": fusion.get("experimental_risk_tier"),
            "risk_level_validated": False,
            "clinical_risk_category": fusion.get("clinical_risk_category"),
            "decision_status": fusion.get("decision_status", "not_generated"),
            "reliability_score": fusion.get("reliability_score"),
            "reliability_score_is_probability": False,
            "fusion_version": screening.get("fusion_version"),
            "contributing_factors": fusion.get("reliability_flags", []),
            "experimental": True,
        },
        "fusion": screening,
        "missing_inputs": fusion.get("missing_inputs", []),
        "doctor_report": _doctor_narrative(fusion, questionnaire),
        "analysis_outdated": analysis_outdated(session_dir),
        "storage": _storage(session_dir),
    }


def analysis_outdated(session_dir: Path) -> bool:
    """True when images were added, removed or replaced after the last fusion run."""
    # Sub-second comparison: generated_utc has one-second resolution, so use the report file's mtime.
    changed = _json(session_dir / "manifest.json").get("evidence_changed_utc")
    fusion = session_dir / "fusion_report.json"
    if not changed or not fusion.is_file():
        return False
    try:
        return datetime.fromisoformat(changed).timestamp() > fusion.stat().st_mtime
    except ValueError:
        return False


def image_results_outdated(session_dir: Path) -> bool:
    """True when per-image model results predate an image change (they may include removed photos)."""
    changed = _json(session_dir / "manifest.json").get("evidence_changed_utc")
    results = session_dir / "image_model_results.json"
    if not changed:
        return False
    try:
        return not results.is_file() or datetime.fromisoformat(changed).timestamp() > results.stat().st_mtime
    except ValueError:
        return False


def _storage(session_dir: Path) -> dict[str, Any]:
    """Where this session's record lives on disk (local datasets folder, outside Git)."""
    record = session_dir / SAVED_OUTPUTS[0]
    return {
        "folder": str(session_dir),
        "record_saved": record.is_file(),
        "record_saved_utc": (
            datetime.fromtimestamp(record.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            if record.is_file() else None
        ),
        "files": [
            name for name in (*SESSION_EVIDENCE_FILES, *SAVED_OUTPUTS, REFERRAL_FILE) if (session_dir / name).is_file()
        ],
        "image_files": sum(
            1 for p in (session_dir / "images").rglob("*.png") if "_removed" not in p.parts
        ) if (session_dir / "images").is_dir() else 0,
        "saved_images": _saved_images(session_dir),
        "ppg_recordings": sum(1 for _ in (session_dir / "ppg").glob("ppg_red_ir_*.csv")) if (session_dir / "ppg").is_dir() else 0,
    }


TIER_LABELS = {
    "low": "Low",
    "moderate": "Moderate",
    "high": "High",
    "insufficient_evidence": "Insufficient Evidence",
}

# Plain names for Component 2's knowledge-graph lookup; unresolved names are reported by C2.
C2_SYMPTOM_NAMES = {
    "fatigue_or_weakness": "fatigue",
    "breathlessness_on_exertion": "breathlessness",
    "dizziness_or_faintness": "dizziness",
    "palpitations": "palpitations",
    "frequent_headaches": "headache",
    "reported_pallor": "pallor",
    "cold_hands_or_feet": "cold extremities",
    "previous_anaemia_or_low_hb": "history of anaemia",
    "recent_or_recurring_blood_loss": "blood loss",
    "blood_in_stool_or_urine": "blood in stool or urine",
    "heavy_or_prolonged_menstruation": "heavy menstrual bleeding",
    # Pandu type signs: names match Component 2's Symptom names or aliases.
    "tremor": "tremor",
    "hard_or_dry_stools": "hard or dry stool",
    "bloating": "bloating",
    "burning_sensation": "burning sensation",
    "excessive_thirst": "excessive thirst",
    "bitter_taste": "bitter taste in the mouth",
    "loose_stools": "loose stools",
    "excessive_sweating": "excessive sweating",
    "daytime_drowsiness": "drowsiness",
    "vomiting": "vomiting",
    "cough": "cough",
    "hoarse_or_weak_voice": "hoarse or weak voice",
    "eating_clay_or_soil": "eating clay or soil",
    "worms_in_stool": "worms in the stool",
}


def _mean(values: list) -> float | None:
    numbers = [v for v in values if isinstance(v, (int, float))]
    return round(sum(numbers) / len(numbers), 4) if numbers else None


def _c2_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Map the C1 report onto Component 2's provisional C1ScreeningPayload (extra keys forbidden)."""
    regions = report["modalities"]["images"].get("regions", {})
    ppg = report["modalities"]["ppg"]
    fusion = report["fusion"]
    result = report["screening_result"]

    def scores(name, source=None):
        return [v.get("score_uncalibrated") for v in regions.get(name, {}).get("model_votes", [])
                if source is None or v.get("source") == source]

    conj = regions.get("conjunctiva", {})
    nails = regions.get("nails", {})
    tongue = regions.get("tongue", {})
    windows = ppg.get("quality_windows_checked") or 0
    symptoms = fusion.get("questionnaire_evidence") or {}

    return {
        "screening_id": report["session_id"],
        "session_id": report["session_id"],
        "screening_result": {
            "condition": "anaemia",
            "risk_level": result["risk_level"] or "insufficient_evidence",
            "screening_confidence": None,  # Uncalibrated: no probability is claimed.
            "evidence_strength": (
                f"experimental; heuristic reliability score {result['reliability_score']} (not a probability)"
            ),
            "status": result["decision_status"],
            "requires_clinician_review": True,
        },
        "hemoglobin": {
            "estimated_g_dl": None,
            "measured_lab_g_dl": None,
            "source": "no fused Hb estimate; per-modality experimental values in modality_results",
            "clinically_validated": False,
        },
        "modality_results": {
            "conjunctiva": {
                "model_predictions": [
                    {"model": source, "class_score": _mean(scores("conjunctiva", source))}
                    for source in sorted({v["source"] for v in conj.get("model_votes", [])})
                ],
                "quality_score": conj.get("technical_pass_ratio", 0.0),
                "agreement": not conj.get("cross_model_disagreement", False),
            },
            "nailbeds": {
                "anaemia_class_score": _mean(scores("nails")),
                "estimated_hb_g_dl": _mean(
                    [e.get("estimate_g_dl") for e in nails.get("experimental_hb_estimates_g_dl", [])]
                ),
                "quality_score": nails.get("technical_pass_ratio"),
            },
            "tongue": {
                "quality_status": (
                    f"{tongue.get('technical_passes', 0)}/{tongue.get('captures', 0)} technical checks passed"
                    if tongue else "not_captured"
                ),
                "anaemia_prediction": None,
            },
            "ppg": {
                "estimated_hb_g_dl": None,
                "signal_quality": round(ppg.get("quality_windows_passed", 0) / windows, 3) if windows else None,
                "status": ppg.get("quality_status") or "not_recorded",
            },
        },
        "symptoms": [
            {"name": C2_SYMPTOM_NAMES.get(name, name), "present": present}
            for key, present in (
                ("present_symptoms", True), ("pandu_type_signs_present", True),
                ("absent_symptoms", False), ("pandu_type_signs_absent", False),
            )
            for name in symptoms.get(key, [])
        ],
        "clinical_findings": [],
        "contributing_factors": fusion.get("rationale", []) + fusion.get("safety_flags", []),
        "missing_data": report.get("missing_inputs", []),
        "recommendation": " ".join(fusion.get("doctor_review_recommendations", []))
        or "Clinician review and laboratory Hb confirmation required.",
        "model_version": fusion.get("fusion_version") or "c1.fusion.v1-aggregation",
        "disclaimer": (
            "AyurAI Component 1 research prototype. Experimental, unvalidated screening evidence "
            "from fictional demo sessions; not a diagnosis. Confirm with laboratory haemoglobin."
        ),
    }


@app.get("/api/c1/health")
def health():
    return {"service": "ayurai-component1", "status": "ok", "demo_only": True}


@app.get("/api/c1/sessions")
def sessions():
    """Sessions stored under datasets/live_sessions, newest first, with what each one contains."""
    if not SESSIONS_ROOT.is_dir():
        return {"sessions": []}
    result = []
    for directory in SESSIONS_ROOT.iterdir():
        if not directory.is_dir() or not DEMO_SESSION.fullmatch(directory.name):
            continue
        try:
            q = _db_questionnaire(directory.name)
            fusion = _json(directory / "fusion_report.json")
            manifest = _json(directory / "manifest.json")
        except HTTPException:
            continue
        captures = manifest.get("captures")
        referral = _is_referral(q)
        result.append({
            "session_id": directory.name,
            "created_utc": manifest.get("created_utc"),
            "workflow_state": workflow_state(directory, q),
            "analysis_outdated": analysis_outdated(directory),
            "questionnaire_available": q is not None,
            "image_count": len(captures) if isinstance(captures, list) else 0,
            "ppg_available": any((directory / "ppg").glob("ppg_red_ir_*.csv")),
            "record_saved": (directory / SAVED_OUTPUTS[0]).is_file(),
            "risk_level": None if referral else fusion.get("experimental_risk_tier"),
            "risk_level_validated": False,
            "decision_status": "urgent_clinician_review_required" if referral
            else fusion.get("decision_status", "not_generated"),
            "generated_utc": fusion.get("generated_utc"),
        })
    result.sort(key=lambda s: s["created_utc"] or "", reverse=True)
    return {"sessions": result}


@app.get("/api/c1/sessions/{session_id}/report")
def session_report(session_id: str):
    return _build_report(session_id)


def _screening_result(report: dict[str, Any]) -> dict[str, Any]:
    """Standalone, versioned Component 1 output. Component 2 team owns ingestion."""
    return {
        "schema_version": report["schema_version"],
        "session_id": report["session_id"],
        "generated_utc": report["generated_utc"],
        "patient_reference": report["patient"]["reference"],
        "research_prototype": True,
        "screening_result": report["screening_result"],
        "modality_evidence": report["modalities"],
        "questionnaire_status": report["questionnaire"]["status"],
        "doctor_summary": report["doctor_report"]["summary"],
    }


def save_session_outputs(session_id: str) -> dict[str, Any]:
    """Write the screening record files into the session folder; return the report with storage info.

    Referral sessions get the report and screening result only: no Component 2 payload,
    because no anaemia screening was performed.
    """
    session_dir = _session_dir(session_id)
    report = _build_report(session_id)
    if report.get("outcome") == REFERRAL_STATUS:
        outputs = dict(zip(SAVED_OUTPUTS[:2], (report, _screening_result(report))))
    else:
        outputs = dict(zip(SAVED_OUTPUTS, (report, _screening_result(report), _c2_payload(report))))
    for name, content in outputs.items():
        tmp = session_dir / f"{name}.tmp"
        tmp.write_text(json.dumps(content, indent=2), encoding="utf-8")
        tmp.replace(session_dir / name)
    return _build_report(session_id)


@app.get("/api/c1/sessions/{session_id}/screening-result")
def component2_json(session_id: str):
    return JSONResponse(_screening_result(_build_report(session_id)), headers={"Cache-Control": "no-store"})


@app.get("/api/c1/sessions/{session_id}/c2-payload")
def component2_payload(session_id: str):
    """Component 1 output shaped for Component 2's provisional C1ScreeningPayload."""
    report = _build_report(session_id)
    if report.get("outcome") == REFERRAL_STATUS:
        raise HTTPException(409, "Safety-referral session: no anaemia screening to hand over to Component 2")
    return JSONResponse(_c2_payload(report), headers={"Cache-Control": "no-store"})


@app.post("/api/c1/sessions/{session_id}/refresh")
def refresh_session(session_id: str):
    session_dir = _session_dir(session_id)
    if _is_referral(_db_questionnaire(session_id)):  # Also refuses non-demo rows.
        return save_session_outputs(session_id)  # Referral record only; never routine fusion.
    if image_results_outdated(session_dir):
        # Images changed since the image models ran: re-run quality checks and models before fusion,
        # so removed or replaced photos cannot reach the fused result.
        from component1.api.intake import analyze

        return analyze(session_id)
    from component1.fusion.fuse_screening_session import fuse_session
    try:
        fuse_session(session_id)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return save_session_outputs(session_id)


# Clinical intake routes (session creation, questionnaire, images, PPG, analysis).
from component1.api.intake import router as intake_router  # noqa: E402

app.include_router(intake_router)

# Patient registration, doctor-review summaries and PDF reports (protected; off unless C1_PATIENT_DATA_ACCESS is set).
from component1.api.patient_records import router as patient_router  # noqa: E402

app.include_router(patient_router)
