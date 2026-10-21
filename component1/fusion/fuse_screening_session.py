
"""AyurAI Component 1: session-level reliability-aware evidence fusion.

Reads existing webcam JSON and local SQLite records.
Does not produce an unvalidated clinical anaemia-risk category.
"""

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

DATA_ROOT = Path(__file__).resolve().parents[2].parent / "datasets"
DB_PATH = DATA_ROOT / "screening_sessions.sqlite3"


def read_json(path):
    """Read a JSON file, or return an empty dictionary."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def decode_json(value):
    """Decode SQLite JSON without exposing questionnaire answers."""
    if not value:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def summarize_images(session_dir):
    """Collect technical quality and model votes by body region."""
    data = read_json(session_dir / "image_model_results.json")
    quality = read_json(session_dir / "quality_report.json")

    regions = {}

    for image in data.get("images", []):
        region = str(image.get("modality", "unknown")).lower()
        if region == "nail":
            region = "nails"

        info = regions.setdefault(region, {
            "captures": 0,
            "technical_passes": 0,
            "model_votes": [],
            "experimental_hb_estimates_g_dl": [],
        })

        info["captures"] += 1

        quality_ok = image.get("technical_quality_status") in {
            "technical_checks_passed", "passed"
        }

        if not quality_ok:
            continue

        info["technical_passes"] += 1
        evidence = image.get("regional_evidence") or {}

        for model in evidence.get("classification_evidence", []):
            vote = model.get("class_vote_at_0_5")

            if vote not in (0, 1):
                continue

            info["model_votes"].append({
                "source": model.get("source", "unknown"),
                "vote": int(vote),
                "score_uncalibrated": model.get(
                    "score_uncalibrated"
                ),
            })

        for model in evidence.get(
            "experimental_hb_estimates_g_dl", []
        ):
            info["experimental_hb_estimates_g_dl"].append({
                "source": model.get("source", "unknown"),
                "estimate_g_dl": model.get("estimate_g_dl"),
            })

    flags = []

    for region, info in regions.items():
        votes = info["model_votes"]
        sources = {vote["source"] for vote in votes}
        unique_votes = {vote["vote"] for vote in votes}

        info["cross_model_disagreement"] = (
            len(sources) > 1 and len(unique_votes) > 1
        )

        info["technical_pass_ratio"] = round(
            info["technical_passes"] / info["captures"], 3
        )

        if info["cross_model_disagreement"]:
            flags.append(f"{region}: model predictions disagree")

        if info["technical_passes"] < info["captures"]:
            flags.append(f"{region}: some images failed quality")

    if "tongue" in regions:
        flags.append(
            "Tongue image captured but no validated "
            "tongue anaemia classifier is available"
        )

    missing_files = quality.get("missing_files", 0)
    if missing_files:
        flags.append(
            "Some webcam manifest files are missing"
        )

    return {
        "regions": regions,
        "image_count": len(data.get("images", [])),
        "missing_manifest_files": missing_files,
    }, flags


def load_database_evidence(conn, session):
    """Retrieve only necessary questionnaire and PPG metadata."""
    questionnaire = {
        "available": False,
        "completion_status": None,
        "fictional_demo": None,
        "urgent_clinician_review": None,
    }

    if table_exists(conn, "questionnaire_responses"):
        row = conn.execute(
            """
            SELECT completion_status, is_fictional_demo,
                   status_json
            FROM questionnaire_responses
            WHERE session_id = ?
            """,
            (session,),
        ).fetchone()

        if row:
            status = decode_json(row["status_json"])

            questionnaire = {
                "available": True,
                "completion_status": row["completion_status"],
                "fictional_demo": bool(row["is_fictional_demo"]),
                "urgent_clinician_review": status.get(
                    "urgent_clinician_review"
                ),
                "capture_allowed_by_questionnaire": status.get(
                    "can_continue_prototype_capture"
                ),
            }

    ppg = {
        "available": False,
        "recording_id": None,
        "quality_status": None,
        "sample_count": 0,
        "quality_windows_passed": 0,
        "metrics_count": 0,
        "median_experimental_hr_bpm": None,
        "median_experimental_spo2_percent": None,
        "hb_model_applied": False,
    }

    if not table_exists(conn, "ppg_live_recordings"):
        return questionnaire, ppg

    row = conn.execute(
        """
        SELECT id, sample_count, quality_status,
               observed_receive_rate_hz,
               quality_report_json
        FROM ppg_live_recordings
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (session,),
    ).fetchone()

    if not row:
        return questionnaire, ppg

    report = decode_json(row["quality_report_json"])
    windows = report.get("window_checks") or []

    ppg.update({
        "available": True,
        "recording_id": row["id"],
        "quality_status": row["quality_status"],
        "sample_count": row["sample_count"],
        "observed_receive_rate_hz": row[
            "observed_receive_rate_hz"
        ],
        "quality_windows_passed": sum(
            window.get("candidate") is True
            for window in windows
        ),
        "quality_windows_checked": len(windows),
    })

    if table_exists(conn, "ppg_live_vitals"):
        vitals = conn.execute(
            """
            SELECT hr_bpm, spo2_percent, finger_present
            FROM ppg_live_vitals
            WHERE recording_id = ?
            ORDER BY metric_index
            """,
            (row["id"],),
        ).fetchall()

        heart_rates = [
            value["hr_bpm"] for value in vitals
            if value["hr_bpm"] is not None
        ]

        spo2_values = [
            value["spo2_percent"] for value in vitals
            if value["spo2_percent"] is not None
        ]

        ppg["metrics_count"] = len(vitals)
        ppg["valid_hr_count"] = len(heart_rates)
        ppg["valid_spo2_count"] = len(spo2_values)

        if heart_rates:
            ppg["median_experimental_hr_bpm"] = median(
                heart_rates
            )

        if spo2_values:
            ppg["median_experimental_spo2_percent"] = median(
                spo2_values
            )

    return questionnaire, ppg


def fuse_session(session):
    """Assemble research evidence without manufacturing risk scores."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid session ID")

    session_dir = DATA_ROOT / "live_sessions" / session

    if not session_dir.is_dir():
        raise FileNotFoundError(session_dir)

    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    images, flags = summarize_images(session_dir)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        questionnaire, ppg = load_database_evidence(
            conn, session
        )

        missing = []

        for region in ("conjunctiva", "nails", "tongue"):
            if region not in images["regions"]:
                missing.append(region)

        if not questionnaire["available"]:
            missing.append("questionnaire")

        if not ppg["available"]:
            missing.append("ppg")

        if questionnaire["fictional_demo"]:
            flags.append(
                "Questionnaire contains fictional demo responses"
            )

        if ppg["available"]:
            if ppg["quality_status"] != (
                "candidate_for_pulse_validation"
            ):
                flags.append(
                    "PPG recording needs technical review"
                )

            flags.append(
                "Live PPG has no validated Hb inference"
            )

        if questionnaire["urgent_clinician_review"] is True:
            decision = "urgent_clinician_review_required"
        elif questionnaire.get(
            "capture_allowed_by_questionnaire"
        ) is False:
            decision = "capture_not_cleared"
        else:
            decision = "insufficient_validated_fusion_evidence"

        report = {
            "session_id": session,
            "generated_utc": datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds"),
            "research_prototype": True,
            "clinical_risk_category": None,
            "decision_status": decision,
            "images": images,
            "ppg": ppg,
            "questionnaire": questionnaire,
            "missing_inputs": missing,
            "reliability_flags": flags,
            "limitations": [
                "Image model scores are not calibrated.",
                "Cross-dataset predictions have not been "
                "validated as one multimodal model.",
                "Technical PPG quality does not establish "
                "Hb prediction accuracy.",
                "No trained, validated questionnaire-to-Hb model.",
                "Low/Moderate/High clinical risk is not "
                "estimable from the current evidence.",
            ],
        }

        # Save the combined report locally.
        report_path = session_dir / "fusion_report.json"
        report_text = json.dumps(report, indent=2)
        report_path.write_text(
            report_text, encoding="utf-8"
        )

        # Also make it retrievable by session ID in SQLite.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fusion_reports (
                session_id TEXT PRIMARY KEY,
                generated_utc TEXT NOT NULL,
                report_json TEXT NOT NULL
            )
        """)

        conn.execute(
            """
            INSERT INTO fusion_reports
                (session_id, generated_utc, report_json)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                generated_utc = excluded.generated_utc,
                report_json = excluded.report_json
            """,
            (
                session,
                report["generated_utc"],
                report_text,
            ),
        )

    print("AYURAI - SESSION FUSION REPORT SAVED")
    print("Session:", session)
    print("Webcam images:", images["image_count"])
    print("PPG samples:", ppg["sample_count"])
    print("PPG metrics:", ppg["metrics_count"])
    print("Questionnaire available:", questionnaire["available"])
    print("Missing inputs:", missing)
    print("Decision:", decision)
    print("Clinical risk:", "NOT ESTIMATED")
    print("Report:", report_path)
    print("Database:", DB_PATH)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    args = parser.parse_args()
    fuse_session(args.session)
