"""Preliminary MAX30102 PPG technical-quality audit (NOT a clinical screening test)."""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt

DATA_ROOT = Path(__file__).resolve().parents[3].parent / "datasets"


def assess(csv_file, out_dir):
    data = pd.read_csv(csv_file)
    required = {"host_elapsed_s", "esp32_readout_ms", "red", "ir"}
    if not required.issubset(data.columns):
        raise ValueError(f"Missing columns: {required - set(data.columns)}")

    data = data[list(sorted(required))].apply(pd.to_numeric, errors="raise")
    if len(data) < 100 or not np.isfinite(data.to_numpy()).all():
        raise ValueError("Need at least 100 finite RED/IR sample pairs")

    t = data["host_elapsed_s"].to_numpy(dtype=float)
    red = data["red"].to_numpy(dtype=float)
    ir = data["ir"].to_numpy(dtype=float)
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("Host timestamps are not strictly increasing")
    fs = float(1 / np.median(dt))
    if fs <= 8 or fs >= 400:
        raise ValueError(f"Unexpected received-sample cadence: {fs:.2f} Hz")

    # Five-second windows: preliminary heuristic thresholds, not clinical SQI.
    windows = []
    for start in np.arange(0, t[-1] - 4.7, 5.0):
        idx = (t >= start) & (t < start + 5)
        if idx.sum() < 4 * fs:
            continue
        r, i = red[idx], ir[idx]
        ir_mean = float(np.median(i))
        ir_swing = float(np.ptp(i) / max(1, abs(ir_mean)))
        sos = butter(3, [0.6, 3.0], btype="bandpass", fs=fs, output="sos")
        fr, fi = sosfiltfilt(sos, r), sosfiltfilt(sos, i)
        corr = float(np.corrcoef(fr, fi)[0, 1]) if np.std(fr) and np.std(fi) else 0.0
        ac_fraction = float(np.std(fi) / max(1, abs(ir_mean)))
        candidate = (
            ir_mean > 5000
            and ir_swing < 0.05
            and corr > 0.65
            and 0.0002 < ac_fraction < 0.05
        )
        windows.append({
            "start_s": round(float(start), 1),
            "end_s": round(float(start + 5), 1),
            "samples": int(idx.sum()),
            "relative_ir_swing": round(ir_swing, 4),
            "red_ir_band_correlation": round(corr, 4),
            "candidate": bool(candidate),
        })

    candidates = [w for w in windows if w["candidate"]]
    best = min(candidates, key=lambda w: w["relative_ir_swing"]) if candidates else None
    state = "candidate_for_pulse_validation" if best else "retake_or_review"

    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "input_file": csv_file.name,
        "sample_count": len(data),
        "observed_receive_rate_hz": round(fs, 2),
        "duration_seconds": round(float(t[-1] - t[0]), 2),
        "status": state,
        "best_technical_window": best,
        "window_checks": windows,
        "clinical_risk_category": None,
        "caveats": [
            "Thresholds are only preliminary engineering heuristics.",
            "Host times are not verified sensor sample timestamps.",
            "Strong RED/IR agreement can be caused by shared motion.",
            "No confirmed pulse, Hb estimate, or anaemia-risk inference."
        ],
    }
    json_file = out_dir / f"{csv_file.stem}_quality.json"
    json_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(10, 6))
    axes[0].plot(t, red, label="RED raw")
    axes[0].plot(t, ir, label="IR raw")
    axes[0].legend()
    axes[0].set(xlabel="Host elapsed time (s)", ylabel="Raw counts",
                title="Original MAX30102 recording")
    if best:
        idx = (t >= best["start_s"]) & (t < best["end_s"])
        sos = butter(3, [0.6, 3.0], btype="bandpass", fs=fs, output="sos")
        axes[1].plot(t[idx], sosfiltfilt(sos, red[idx]), label="Filtered RED")
        axes[1].plot(t[idx], sosfiltfilt(sos, ir[idx]), label="Filtered IR")
        axes[1].legend()
        axes[1].set_title("Technical candidate: bandpass 0.6–3 Hz (not validated pulse)")
    else:
        axes[1].text(.5, .5, "No candidate window—retake or inspect",
                     ha="center", transform=axes[1].transAxes)
    axes[1].set(xlabel="Host elapsed time (s)", ylabel="Bandpassed counts")
    for ax in axes:
        ax.grid(alpha=.25)
    fig.tight_layout()
    png_file = out_dir / f"{csv_file.stem}_quality.png"
    fig.savefig(png_file, dpi=150)
    plt.close(fig)

    print("AYURAI - LIVE PPG QUALITY REVIEW")
    print(f"Samples: {len(data)} | Observed receive rate: {fs:.2f} Hz")
    for w in windows:
        print(f"{w['start_s']:.0f}-{w['end_s']:.0f}s: "
              f"IR swing {w['relative_ir_swing']*100:.1f}% | "
              f"candidate={w['candidate']}")
    print("Status:", state)
    print("JSON:", json_file)
    print("Graph:", png_file)
    print("Not a validated pulse or Hb/anaemia prediction.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.csv:
        csv_file = args.csv
    elif args.session:
        if not args.session.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid session ID")
        folder = DATA_ROOT / "live_sessions" / args.session / "ppg"
        matches = sorted(folder.glob("ppg_red_ir_*.csv"))
        if not matches:
            raise FileNotFoundError(f"No PPG recordings found under {folder}")
        csv_file = matches[-1]
    else:
        parser.error("Provide --session or --csv")
    assess(csv_file, args.output_dir or csv_file.parent)


if __name__ == "__main__":
    main()
