
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfiltfilt

# Component 1 root directory
ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data" / "external" / "bidmc_01_Signals.csv"
OUTPUT_DIR = ROOT / "data" / "processed"

# Load public PPG dataset
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"PPG dataset not found: {INPUT_FILE}")

df = pd.read_csv(INPUT_FILE)
df.columns = df.columns.str.strip()

required_columns = {"Time [s]", "PLETH"}
if not required_columns.issubset(df.columns):
    raise ValueError("Required PPG columns are missing.")

# Select the first 15 seconds
ppg_data = df.loc[
    df["Time [s]"] <= 15,
    ["Time [s]", "PLETH"]
].dropna()

time = ppg_data["Time [s]"].to_numpy(dtype=float)
raw_ppg = ppg_data["PLETH"].to_numpy(dtype=float)

if len(raw_ppg) < 100:
    raise ValueError("Not enough PPG samples for filtering.")

# Calculate sampling frequency from timestamps
time_diff = np.diff(time)

if np.any(time_diff <= 0):
    raise ValueError("Timestamps must be increasing.")

fs = 1.0 / np.median(time_diff)

print("Dataset loaded successfully")
print("Total selected samples:", len(raw_ppg))
print(f"Sampling frequency: {fs:.2f} Hz")

# Apply third-order Butterworth bandpass filter
# Preliminary passband for pulse waveform processing
lowcut = 0.5
highcut = 5.0

if fs <= 2 * highcut:
    raise ValueError("Sampling frequency is too low.")

sos = butter(
    3,
    [lowcut, highcut],
    btype="bandpass",
    fs=fs,
    output="sos"
)

filtered_ppg = sosfiltfilt(sos, raw_ppg)

# Save processed data
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

processed_df = pd.DataFrame({
    "time": time,
    "raw_ppg": raw_ppg,
    "filtered_ppg": filtered_ppg
})

processed_df.to_csv(
    OUTPUT_DIR / "ppg_filtered.csv",
    index=False
)

# Compare raw and filtered signals
plt.figure(figsize=(12, 5))

plt.plot(
    time,
    raw_ppg - np.mean(raw_ppg),
    label="Raw PPG (mean removed)",
    alpha=0.5
)

plt.plot(
    time,
    filtered_ppg,
    label="Filtered PPG (0.5-5 Hz)",
    linewidth=1.5
)

plt.title("AyurAI Component 1 - PPG Preprocessing")
plt.xlabel("Time (seconds)")
plt.ylabel("PPG amplitude (relative units)")
plt.legend()
plt.grid(True)
plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "ppg_filter_comparison.png",
    dpi=150
)

print("PPG filtering completed successfully")
print("Filtered CSV and comparison graph saved.")

plt.show()

#loads the public PPG recording, estimates the sampling rate, applies a Butterworth bandpass filter, and compares the raw and filtered waveforms.
#The 0.5–5 Hz range is a preliminary setting; we'll evaluate whether it is suitable for your data later.
