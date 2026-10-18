"""Save fictional AyurAI questionnaire examples against an existing demo session.

Question Bank v1 is a DRAFT. This module intentionally does not collect real
patient responses; clinical collection needs approved protocol and safeguards.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from questionnaire_engine import (
    get_status,
    get_visible_questions,
    load_bank,
    validate_answers,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPO_ROOT.parent / "datasets"
SCENARIOS = ("adult", "child", "pregnancy", "urgent")


def fictional_example(scenario: str) -> tuple[dict, dict]:
    """Return clearly artificial demonstration answers, never real patient data."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown demo scenario: {scenario}")

    profile = {
        "age_months": 360,
        "pregnancy_status": "not_pregnant",
        "collect_ppg": True,
        "collect_images": True,
        "include_asthavidha": False,
        "include_review": True,
        "demo": True,
    }
    answers = {
        "REG01": "FICTIONAL-PATIENT-001",
        "REG02": 360,
        "REG03": "English",
        "REG04": "patient",
        "REG05": "yes",
        "REG06": "yes",
        "REG07": "yes",
        "SAF01": "no",
        "SAF02": "no",
        "SAF03": "no",
        "SAF04": "no",
        "C01": "yes",
        "C08": "no",
        "C09": "no",
        "C10": "no",
        "C15": "yes",
        "C16": "yes",
        "C17": "yes",
        "C20": "no",
        "MED01": [{"name": "FICTIONAL-MEDICINE-EXAMPLE", "dose": "example only"}],
        "MED02": [{"name": "FICTIONAL-HERBAL-PRODUCT", "ingredients": "not specified"}],
        "ALG01": [{"substance": "FICTIONAL-ALLERGY-EXAMPLE", "reaction": "example only"}],
        "P02": "no",
        "P05": "no",
        "P06": "no",
        "IMG05": "no",
    }

    if scenario == "child":
        profile["age_months"] = 120
        profile["pregnancy_status"] = "not_applicable"
        answers.update({
            "REG01": "FICTIONAL-CHILD-001",
            "REG02": 120,
            "REG04": "parent_or_guardian",
            "CH01": "coded guardian",
            "CH02": "yes",
        })
    elif scenario == "pregnancy":
        profile["age_months"] = 324
        profile["pregnancy_status"] = "pregnant"
        answers.update({
            "REG01": "FICTIONAL-PREGNANCY-001",
            "REG02": 324,
            "C20": "yes",
            "PR01": "example: second trimester",
            "PR06": "no",
        })
    elif scenario == "urgent":
        answers["REG01"] = "FICTIONAL-URGENT-001"
        answers["SAF01"] = "yes"
        # No extraneous responses should be recorded after an urgent-stop flag.
        permitted = {"REG01", "REG02", "REG03", "REG04", "REG05", "REG06", "REG07", "SAF01", "SAF02", "SAF03", "SAF04"}
        answers = {qid: value for qid, value in answers.items() if qid in permitted}

    return profile, answers


def save_fictional_session(
    session_id: str,
    scenario: str,
    data_root: Path = DEFAULT_DATA_ROOT,
) -> dict:
    """Validate, save and read back an incomplete fictional questionnaire."""
    if not re.fullmatch(r"demo_[a-fA-F0-9]{8}", session_id):
        raise ValueError("Only existing demo_XXXXXXXX session IDs are accepted.")

    data_root = Path(data_root)
    if not (data_root / "live_sessions" / session_id / "manifest.json").is_file():
        raise FileNotFoundError(f"Cannot find captured demo session: {session_id}")

    bank = load_bank()
    profile, answers = fictional_example(scenario)
    validate_answers(bank, answers)
    visible = get_visible_questions(bank, profile, answers)
    permitted_ids = {q["id"] for q in visible}
    unexpected = set(answers) - permitted_ids
    if unexpected:
        raise ValueError(f"Example supplied answers to hidden questions: {sorted(unexpected)}")

    status = get_status(profile, answers)
    status["clinical_risk_category"] = None
    now = datetime.now(timezone.utc).isoformat()

    db = data_root / "screening_sessions.sqlite3"
    data_root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questionnaire_responses (
                session_id TEXT PRIMARY KEY,
                question_bank_version TEXT NOT NULL,
                scenario TEXT NOT NULL,
                is_fictional_demo INTEGER NOT NULL CHECK(is_fictional_demo = 1),
                profile_json TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                status_json TEXT NOT NULL,
                completion_status TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO questionnaire_responses (
                session_id, question_bank_version, scenario, is_fictional_demo,
                profile_json, answers_json, status_json, completion_status,
                updated_at_utc
            ) VALUES (?, ?, ?, 1, ?, ?, ?, 'partial_demo', ?)
            ON CONFLICT(session_id) DO UPDATE SET
                question_bank_version=excluded.question_bank_version,
                scenario=excluded.scenario,
                is_fictional_demo=1,
                profile_json=excluded.profile_json,
                answers_json=excluded.answers_json,
                status_json=excluded.status_json,
                completion_status='partial_demo',
                updated_at_utc=excluded.updated_at_utc
        """, (
            session_id, bank["version"], scenario,
            json.dumps(profile, sort_keys=True),
            json.dumps(answers, sort_keys=True),
            json.dumps(status, sort_keys=True), now,
        ))
        saved = conn.execute("""
            SELECT session_id, question_bank_version, scenario,
                   is_fictional_demo, completion_status, answers_json
            FROM questionnaire_responses WHERE session_id = ?
        """, (session_id,)).fetchone()

    assert saved is not None and saved[3] == 1
    return {
        "session_id": saved[0],
        "question_bank_version": saved[1],
        "scenario": saved[2],
        "fictional_demo": bool(saved[3]),
        "completion_status": saved[4],
        "answered": len(json.loads(saved[5])),
        "applicable_questions": len(visible),
        "urgent_clinician_review": status["urgent_clinician_review"],
        "ppg_acquisition_allowed": status["ppg_acquisition_allowed"],
        "image_acquisition_allowed": status["image_acquisition_allowed"],
        "clinical_risk_category": status["clinical_risk_category"],
        "database": str(db),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Save an AyurAI FICTIONAL questionnaire demo")
    parser.add_argument("--session", required=True, help="Existing demo_XXXXXXXX webcam session ID")
    parser.add_argument("--demo", required=True, choices=SCENARIOS)
    args = parser.parse_args()

    result = save_fictional_session(args.session, args.demo)
    print("AYURAI - QUESTIONNAIRE SQLITE DEMO SAVED")
    print(json.dumps(result, indent=2))
    print("Only fictional examples are supported. No real patient history recorded.")
    print("Unanswered questions remain unanswered; this is not a completed clinical intake.")


if __name__ == "__main__":
    main()
