"""Capture live MAX30102 RED/IR readings sent by an ESP32-S3 over USB serial.

For research demonstrations only. No Hb or anaemia prediction is produced.
Arduino sketch is expected to emit: time_ms,red,ir
"""
import argparse
import csv
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt

try:
    import serial
except ImportError:
    raise SystemExit("Missing pyserial. Install: python -m pip install pyserial")


DATA_ROOT = Path(__file__).resolve().parents[3].parent / "datasets"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_sensor_line(line):
    """Return (ESP32 readout milliseconds, RED, IR), or None for headers."""
    parts = line.strip().split(",")
    if len(parts) != 3:
        return None
    try:
        millis, red, ir = (int(part.strip()) for part in parts)
    except ValueError:
        return None
    if millis < 0 or not (0 <= red <= 262143 and 0 <= ir <= 262143):
        return None
    return millis, red, ir


def record(port, seconds, session, baud):
    """Read raw samples, then save CSV and a technical waveform preview."""
    if not SESSION_ID_PATTERN.fullmatch(session):
        raise ValueError("Invalid session ID (use letters, digits, _ or -)")
    if seconds <= 0 or seconds > 300:
        raise ValueError("--seconds must be between 1 and 300")

    session_root = DATA_ROOT / "live_sessions" / session
    if not session_root.is_dir():
        raise FileNotFoundError(
            f"Session folder not found: {session_root}\n"
            "Use an existing webcam session ID."
        )

    output_dir = session_root / "ppg"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = output_dir / f"ppg_red_ir_{stamp}.csv"
    figure_path = output_dir / f"ppg_waveform_{stamp}.png"

    print("AYURAI - LIVE MAX30102 USB CAPTURE")
    print(f"COM port: {port} | Baud: {baud} | Duration: {seconds} s")
    print(f"Session: {session}")
    print("Keep the finger gently and steadily on the sensor.")
    print("Reading... press Ctrl+C to stop early.")

    rows = []
    bad_lines = 0
    try:
        # Arduino Serial Monitor must be CLOSED before opening this port.
        with serial.Serial(port, baud, timeout=0.5) as ser:
            time.sleep(2.0)  # Give the ESP32 time if opening USB resets it.
            ser.reset_input_buffer()
            start = time.perf_counter()

            try:
                while time.perf_counter() - start < seconds:
                    raw_line = ser.readline().decode("ascii", errors="replace").strip()
                    if not raw_line:
                        continue
                    parsed = parse_sensor_line(raw_line)
                    if parsed is None:
                        if raw_line not in ("time_ms,red,ir", "AYURAI MAX30102 READY"):
                            bad_lines += 1
                        continue
                    esp32_ms, red, ir = parsed
                    rows.append((round(time.perf_counter() - start, 6),
                                 esp32_ms, red, ir))
            except KeyboardInterrupt:
                print("\nCapture stopped by user; saving collected samples.")
    except serial.SerialException as exc:
        raise SystemExit(
            f"Cannot read {port}: {exc}\n"
            "Close Arduino Serial Monitor and check the current COM port."
        )

    if not rows:
        raise SystemExit(
            "No RED/IR data received. Check that the sensor streaming sketch "
            "is running at 115200 baud, then reopen the port."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(("host_elapsed_s", "esp32_readout_ms", "red", "ir"))
        writer.writerows(rows)

    x = [row[0] for row in rows]
    red_values = [row[2] for row in rows]
    ir_values = [row[3] for row in rows]

    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(11, 6))
    axes[0].plot(x, red_values, linewidth=0.8)
    axes[0].set_ylabel("RED (raw)")
    axes[0].grid(alpha=0.3)
    axes[1].plot(x, ir_values, linewidth=0.8)
    axes[1].set_ylabel("IR (raw)")
    axes[1].set_xlabel("Host elapsed time (s; approximate receive time)")
    axes[1].grid(alpha=0.3)
    fig.suptitle(f"AyurAI MAX30102 raw PPG preview — {session}")
    fig.tight_layout()
    fig.savefig(figure_path, dpi=150)
    plt.close(fig)

    print(f"\nCaptured paired RED/IR samples: {len(rows)}")
    print(f"RED range: {min(red_values)}–{max(red_values)}")
    print(f"IR range:  {min(ir_values)}–{max(ir_values)}")
    if bad_lines:
        print(f"Skipped non-data lines: {bad_lines}")
    print("CSV saved:", csv_path)
    print("Waveform saved:", figure_path)
    print("IMPORTANT: timestamps are readout/receive times, not verified sample times.")
    print("Signal quality and clinical usefulness have NOT been established.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM11")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--session", required=True)
    args = parser.parse_args()
    record(args.port, args.seconds, args.session, args.baud)


if __name__ == "__main__":
    main()
