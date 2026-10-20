
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# Component 1 project directory
ROOT = Path(__file__).resolve().parents[2]

# Public PPG dataset
input_file = ROOT / "data" / "external" / "bidmc_01_Signals.csv"
output_dir = ROOT / "data" / "processed"

if not input_file.exists():
    raise FileNotFoundError(f"Dataset not found: {input_file}")

# Load data
df = pd.read_csv(input_file)
df.columns = df.columns.str.strip()

# Check expected columns
required = {"Time [s]", "PLETH"}
if not required.issubset(df.columns):
    raise ValueError(f"Unexpected CSV columns: {df.columns.tolist()}")

# Select first 15 seconds
ppg = df.loc[df["Time [s]"] <= 15, ["Time [s]", "PLETH"]].dropna()

# Display information
print("Dataset loaded successfully")
print("Total samples:", len(df))
print("Preview samples:", len(ppg))
print("Columns:", df.columns.tolist())

# Plot PPG waveform
plt.figure(figsize=(11, 4))
plt.plot(ppg["Time [s]"], ppg["PLETH"])
plt.xlabel("Time (seconds)")
plt.ylabel("PPG amplitude (relative units)")
plt.title("AyurAI Component 1 - Public PPG Dataset Replay")
plt.grid(True)
plt.tight_layout()

# Save the output
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "ppg_waveform.png"
plt.savefig(output_file, dpi=150)

print("Waveform saved to:", output_file)

plt.show()
