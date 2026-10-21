
"""Store MAX30102 experimental vital-sign metrics in AyurAI SQLite."""

import argparse
import csv
import math
import re
import sqlite3
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[3].parent / "datasets"
DB_PATH = DATA_ROOT / "screening_sessions.sqlite3"


def optional_number(value, conversion):
    """Preserve missing measurements as database NULL."""
    if value is None or str(value).strip().lower() in ("", "null"):
        return None

    number = conversion(value)

    if not math.isfinite(number):
        raise ValueError("Non-finite vital-sign value")

    return number


def register_vitals(session):
    """Link the latest vitals CSV to its existing PPG recording."""

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid session ID")

    folder = DATA_ROOT / "live_sessions" / session / "ppg"
    files = sorted(folder.glob("ppg_metrics_*.csv"))

    if not files:
        raise FileNotFoundError("No metrics CSV found")

    metrics_file = files[-1]

    # Use the timestamp shared by both CSV files.
    timestamp = metrics_file.name.removeprefix("ppg_metrics_")
    raw_filename = "ppg_red_ir_" + timestamp

    if not (folder / raw_filename).is_file():
        raise FileNotFoundError("Matching raw PPG CSV is missing")

    rows = []

    with metrics_file.open(
        newline="", encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        required = {
            "time_ms", "hr_bpm", "spo2_percent",
            "temperature_c", "finger_present"
        }

        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Unexpected metrics CSV columns")

        for index, row in enumerate(reader):
            timestamp_ms = int(row["time_ms"])

            hr = optional_number(row["hr_bpm"], int)
            spo2 = optional_number(row["spo2_percent"], int)
            temperature = optional_number(
                row["temperature_c"], float
            )
            finger = int(row["finger_present"])

            if timestamp_ms < 0 or finger not in (0, 1):
                raise ValueError("Invalid timestamp or finger status")

            if hr is not None and not 0 <= hr <= 300:
                raise ValueError("Invalid HR value")

            if spo2 is not None and not 0 <= spo2 <= 100:
                raise ValueError("Invalid SpO2 value")

            if temperature is not None and not -40 <= temperature <= 100:
                raise ValueError("Invalid temperature value")

            rows.append((
                index, timestamp_ms, hr,
                spo2, temperature, finger
            ))

    if not rows:
        raise ValueError("No vital-sign records found")

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("PRAGMA foreign_keys = ON")

        recording = conn.execute(
            """
            SELECT id FROM ppg_live_recordings
            WHERE session_id = ? AND recording_file = ?
            """,
            (session, raw_filename)
        ).fetchone()

        if recording is None:
            raise RuntimeError(
                "Raw recording is not yet registered. "
                "Run PPG quality assessment and "
                "register_session_ppg.py first."
            )

        recording_id = recording[0]

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ppg_live_vitals (
                recording_id INTEGER NOT NULL,
                metric_index INTEGER NOT NULL,
                esp32_readout_ms INTEGER NOT NULL,
                hr_bpm INTEGER,
                spo2_percent INTEGER,
                temperature_c REAL,
                finger_present INTEGER NOT NULL,
                PRIMARY KEY (recording_id, metric_index),
                FOREIGN KEY (recording_id)
                    REFERENCES ppg_live_recordings(id)
                    ON DELETE CASCADE
            )
        """)

        # Safe to rerun: replace only this recording's metrics.
        conn.execute(
            "DELETE FROM ppg_live_vitals WHERE recording_id = ?",
            (recording_id,)
        )

        conn.executemany(
            """
            INSERT INTO ppg_live_vitals (
                recording_id, metric_index,
                esp32_readout_ms, hr_bpm,
                spo2_percent, temperature_c,
                finger_present
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [(recording_id, *row) for row in rows]
        )

    print("AYURAI - VITAL SIGNS SQLITE SAVED")
    print("Session:", session)
    print("Recording ID:", recording_id)
    print("Metrics CSV:", metrics_file.name)
    print("Vital-sign records:", len(rows))
    print("HR values present:", sum(r[2] is not None for r in rows))
    print("SpO2 values present:", sum(r[3] is not None for r in rows))
    print("Database:", DB_PATH)
    print("Research-only estimates; no clinical risk calculated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)

    args = parser.parse_args()
    register_vitals(args.session)
