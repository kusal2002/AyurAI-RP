
from pathlib import Path
import sqlite3
import pandas as pd

# Locate the local database outside GitHub
REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT.parent / "datasets" / "ayurai_image_catalog.sqlite3"

if not DB_PATH.exists():
    raise FileNotFoundError(f"Database not found: {DB_PATH}")

# Read image metadata
with sqlite3.connect(DB_PATH) as conn:
    df = pd.read_sql_query(
        "SELECT * FROM image_records",
        conn
    )

print("AYURAI IMAGE DATABASE AUDIT")
print("-" * 40)
print("Total records:", len(df))

# Count records by dataset
print("\nDataset summary:")
print(df.groupby(["source", "modality"]).agg(
    images=("filename", "count"),
    labelled=("anaemia_label", "count"),
    hb_available=("hb_g_dl", "count")
).to_string())

# Check binary label distribution
print("\nClass distribution (0=Non-anaemic, 1=Anaemic):")
print(pd.crosstab(
    df["source"],
    df["anaemia_label"],
    dropna=False
).to_string())

# Check whether image paths still exist
missing = df[
    ~df["file_path"].map(lambda path: Path(path).is_file())
]

print("\nMissing image files:", len(missing))

# Check repeated filename families within sources
family_counts = (
    df.dropna(subset=["filename_family"])
    .groupby(["source", "filename_family"])
    .size()
)

print("Repeated filename families:",
      int((family_counts > 1).sum()))

# Check identical file paths
print("Duplicate database file paths:",
      int(df["file_path"].duplicated().sum()))

if missing.empty:
    print("\nDatabase audit completed successfully!")
else:
    print("\nWARNING: Some image paths are missing.")
