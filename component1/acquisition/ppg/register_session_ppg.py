"""Link real MAX30102 recordings and preliminary quality reports to the session SQLite DB.

Local research prototype only. Does not calculate Hb or anaemia risk.
"""
import argparse
import csv
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[3].parent / "datasets"
DB_PATH = DATA_ROOT / "screening_sessions.sqlite3"

def find_recording(session):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid session ID")
    folder = DATA_ROOT / "live_sessions" / session / "ppg"
    if not folder.is_dir():
        raise FileNotFoundError(f"PPG session folder missing: {folder}")
    # Prefer the newest recording that ALREADY has a quality report.
    for file in sorted(folder.glob("ppg_red_ir_*.csv"), reverse=True):
        report = folder / (file.stem + "_quality.json")
        if report.is_file():
            return file, report
    raise FileNotFoundError("No matching CSV + quality JSON. Run assess_live_ppg.py first.")

def read_inputs(csv_file, report_file):
    with report_file.open(encoding="utf-8") as f:
        report = json.load(f)
    if report.get("input_file") != csv_file.name:
        raise ValueError("Quality report refers to a different CSV")
    if report.get("status") not in ("candidate_for_pulse_validation", "retake_or_review"):
        raise ValueError("Unexpected quality status")

    rows = []
    with csv_file.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"host_elapsed_s", "esp32_readout_ms", "red", "ir"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing columns: {required - set(reader.fieldnames or [])}")
        previous = -1.0
        for line in reader:
            elapsed = float(line["host_elapsed_s"])
            ms, red, ir = (int(line[key]) for key in ("esp32_readout_ms", "red", "ir"))
            if (not math.isfinite(elapsed) or elapsed <= previous or ms < 0
                    or not (0 <= red <= 262143 and 0 <= ir <= 262143)):
                raise ValueError("Invalid or unsorted sample data")
            previous = elapsed
            rows.append((len(rows), elapsed, ms, red, ir))
    if not rows or report.get("sample_count") != len(rows):
        raise ValueError("Missing samples or quality-report sample count mismatch")
    return report, rows

def save(session, csv_file, report_file, db=DB_PATH):
    if not db.is_file():
        raise FileNotFoundError(f"Questionnaire screening database missing: {db}")
    report, samples = read_inputs(csv_file, report_file)
    rate = report.get("observed_receive_rate_hz")
    if rate is not None and (not isinstance(rate, (float, int)) or not math.isfinite(rate)):
        raise ValueError("Invalid receive rate")

    # Keep database changes together; repeating the command updates the same recording.
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ppg_live_recordings (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                recording_file TEXT NOT NULL,
                quality_status TEXT NOT NULL,
                observed_receive_rate_hz REAL,
                sample_count INTEGER NOT NULL,
                quality_report_json TEXT NOT NULL,
                imported_at_utc TEXT NOT NULL,
                UNIQUE (session_id, recording_file)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ppg_live_samples (
                recording_id INTEGER NOT NULL,
                sample_index INTEGER NOT NULL,
                host_elapsed_s REAL NOT NULL,
                esp32_readout_ms INTEGER NOT NULL,
                red INTEGER NOT NULL,
                ir INTEGER NOT NULL,
                PRIMARY KEY (recording_id, sample_index),
                FOREIGN KEY (recording_id)
                    REFERENCES ppg_live_recordings(id) ON DELETE CASCADE
            )
        """)
        entry = (
            session, csv_file.name, report["status"], rate, len(samples),
            json.dumps(report, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
        conn.execute("""
            INSERT INTO ppg_live_recordings (
                session_id, recording_file, quality_status,
                observed_receive_rate_hz, sample_count,
                quality_report_json, imported_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, recording_file) DO UPDATE SET
                quality_status=excluded.quality_status,
                observed_receive_rate_hz=excluded.observed_receive_rate_hz,
                sample_count=excluded.sample_count,
                quality_report_json=excluded.quality_report_json,
                imported_at_utc=excluded.imported_at_utc
        """, entry)
        recording_id = conn.execute(
            "SELECT id FROM ppg_live_recordings "
            "WHERE session_id=? AND recording_file=?",
            (session, csv_file.name)
        ).fetchone()[0]
        conn.execute("DELETE FROM ppg_live_samples WHERE recording_id=?", (recording_id,))
        conn.executemany(
            "INSERT INTO ppg_live_samples VALUES (?, ?, ?, ?, ?, ?)",
            [(recording_id, *row) for row in samples]
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM ppg_live_samples WHERE recording_id=?",
            (recording_id,)
        ).fetchone()[0]
        if count != len(samples):
            raise RuntimeError("Incomplete insert, rolling back")
    print("AYURAI SESSION PPG SQLITE — VERIFIED")
    print("Session:", session)
    print("Recording ID:", recording_id)
    print("Samples stored:", count)
    print("Technical status:", report["status"])
    print("Clinical risk category: NONE")
    print("Database:", db)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--session", required=True)
    args = p.parse_args()
    csv_file, report_file = find_recording(args.session)
    save(args.session, csv_file, report_file)

if __name__ == "__main__":
    main()
