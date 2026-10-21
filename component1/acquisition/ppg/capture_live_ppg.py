
"""Capture live MAX30102 RED/IR PPG and experimental HR/SpO2.

ESP32-S3 -> USB Serial -> Python -> Local CSV files.

Research prototype only.
No direct Hb measurement or clinical diagnosis.
"""

import argparse
import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt

try:
    import serial
except ImportError:
    raise SystemExit(
        "Missing pyserial. Install using: python -m pip install pyserial"
    )


DATA_ROOT = Path(__file__).resolve().parents[3].parent / "datasets"

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_sensor_line(line):
    """Parse ESP32 RED/IR data: time_ms,red,ir."""

    parts = line.strip().split(",")

    if len(parts) != 3:
        return None

    try:
        millis, red, ir = (
            int(part.strip()) for part in parts
        )
    except ValueError:
        return None

    if millis < 0:
        return None

    if not (0 <= red <= 262143 and 0 <= ir <= 262143):
        return None

    return millis, red, ir


def parse_metrics_line(line):
    """Parse experimental HR, SpO2, temperature and finger status."""

    parts = [part.strip() for part in line.split(",")]

    if len(parts) != 6 or parts[0] != "#METRICS":
        return None

    try:
        timestamp = int(parts[1])

        heart_rate = (
            None if parts[2].lower() == "null"
            else int(parts[2])
        )

        spo2 = (
            None if parts[3].lower() == "null"
            else int(parts[3])
        )

        temperature = (
            None if parts[4].lower() == "null"
            else float(parts[4])
        )

        finger_present = int(parts[5])

        if timestamp < 0 or finger_present not in (0, 1):
            return None

        if heart_rate is not None and not (0 <= heart_rate <= 300):
            return None

        if spo2 is not None and not (0 <= spo2 <= 100):
            return None

        return (
            timestamp,
            heart_rate,
            spo2,
            temperature,
            finger_present
        )

    except ValueError:
        return None


def record(port, seconds, session, baud):
    """Record RED/IR samples and experimental vital-sign estimates."""

    if not SESSION_ID_PATTERN.fullmatch(session):
        raise ValueError("Invalid session ID")

    if not 0 < seconds <= 300:
        raise ValueError("--seconds must be between 1 and 300")

    session_root = DATA_ROOT / "live_sessions" / session

    if not session_root.is_dir():
        raise FileNotFoundError(
            f"Session folder not found: {session_root}"
        )

    output_dir = session_root / "ppg"

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    csv_path = output_dir / f"ppg_red_ir_{stamp}.csv"
    metrics_path = output_dir / f"ppg_metrics_{stamp}.csv"
    figure_path = output_dir / f"ppg_waveform_{stamp}.png"

    print("AYURAI - LIVE MAX30102 USB CAPTURE")
    print(f"COM port: {port}")
    print(f"Baud: {baud}")
    print(f"Duration: {seconds} seconds")
    print(f"Session: {session}")
    print("Place finger gently on the sensor.")
    print("Recording...")

    rows = []
    metrics_rows = []
    bad_lines = 0

    try:
        with serial.Serial(
            port,
            baud,
            timeout=0.5
        ) as ser:

            # Allow the ESP32 to initialize after USB connection.
            time.sleep(2.0)

            ser.reset_input_buffer()

            start = time.perf_counter()

            try:
                while time.perf_counter() - start < seconds:

                    raw_line = ser.readline().decode(
                        "ascii",
                        errors="replace"
                    ).strip()

                    if not raw_line:
                        continue

                    # ----------------------------------
                    # EXPERIMENTAL HR / SPO2 / TEMPERATURE
                    # ----------------------------------

                    if raw_line.startswith("#METRICS,"):

                        metrics = parse_metrics_line(raw_line)

                        if metrics is not None:
                            metrics_rows.append(metrics)
                        else:
                            bad_lines += 1

                        continue

                    # Ignore firmware information and headers.
                    if (
                        raw_line.startswith("#")
                        or raw_line == "time_ms,red,ir"
                    ):
                        continue

                    # ----------------------------------
                    # RAW RED AND IR SIGNALS
                    # ----------------------------------

                    parsed = parse_sensor_line(raw_line)

                    if parsed is None:
                        bad_lines += 1
                        continue

                    esp32_ms, red, ir = parsed

                    elapsed = round(
                        time.perf_counter() - start,
                        6
                    )

                    rows.append((
                        elapsed,
                        esp32_ms,
                        red,
                        ir
                    ))

            except KeyboardInterrupt:
                print("Recording stopped early.")

    except serial.SerialException as exc:
        raise SystemExit(
            f"Cannot read {port}: {exc}\n"
            "Close Arduino Serial Monitor and check COM port."
        )

    if not rows:
        raise SystemExit(
            "No RED/IR data received. "
            "Check the Arduino sketch and baud rate."
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # ----------------------------------
    # SAVE RAW PPG CSV
    # ----------------------------------

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "host_elapsed_s",
            "esp32_readout_ms",
            "red",
            "ir"
        ])

        writer.writerows(rows)

    # ----------------------------------
    # SAVE EXPERIMENTAL VITAL METRICS CSV
    # ----------------------------------

    if metrics_rows:

        with metrics_path.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "time_ms",
                "hr_bpm",
                "spo2_percent",
                "temperature_c",
                "finger_present"
            ])

            writer.writerows(metrics_rows)

        print(
            "Experimental vital-sign metrics saved:",
            metrics_path
        )
        print("Metrics records:", len(metrics_rows))

    else:
        print("No experimental vital-sign metrics received.")

    # ----------------------------------
    # GENERATE RAW PPG GRAPH
    # ----------------------------------

    x = [row[0] for row in rows]

    red_values = [row[2] for row in rows]
    ir_values = [row[3] for row in rows]

    fig, axes = plt.subplots(
        2,
        1,
        sharex=True,
        figsize=(11, 6)
    )

    axes[0].plot(
        x,
        red_values,
        linewidth=0.8
    )

    axes[0].set_ylabel("RED (raw)")
    axes[0].grid(alpha=0.3)

    axes[1].plot(
        x,
        ir_values,
        linewidth=0.8
    )

    axes[1].set_ylabel("IR (raw)")
    axes[1].set_xlabel(
        "Host elapsed time (s; approximate receive time)"
    )
    axes[1].grid(alpha=0.3)

    fig.suptitle(
        f"AyurAI MAX30102 raw PPG preview — {session}"
    )

    fig.tight_layout()

    fig.savefig(
        figure_path,
        dpi=150
    )

    plt.close(fig)

    # ----------------------------------
    # FINAL SUMMARY
    # ----------------------------------

    print()
    print("AYURAI PPG RECORDING COMPLETED")
    print("--------------------------------------")

    print("RED/IR samples:", len(rows))
    print("Experimental metrics records:", len(metrics_rows))

    print(
        f"RED range: {min(red_values)} - {max(red_values)}"
    )

    print(
        f"IR range: {min(ir_values)} - {max(ir_values)}"
    )

    if bad_lines:
        print("Skipped malformed lines:", bad_lines)

    print("Raw PPG CSV:", csv_path)
    print("Waveform graph:", figure_path)

    if metrics_rows:
        print("Vitals CSV:", metrics_path)

    print(
        "Timestamps are readout/receive times, "
        "not verified sensor sampling times."
    )
    print(
        "HR and SpO2 are experimental algorithm estimates."
    )
    print(
        "No Hb measurement or clinical risk prediction."
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--port",
        default="COM11"
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200
    )

    parser.add_argument(
        "--seconds",
        type=float,
        default=20.0
    )

    parser.add_argument(
        "--session",
        required=True
    )

    args = parser.parse_args()

    record(
        args.port,
        args.seconds,
        args.session,
        args.baud
    )


if __name__ == "__main__":
    main()
