
from pathlib import Path
import re
import sqlite3
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_DIR.parent / "datasets"
DB_PATH = DATA_ROOT / "ayurai_image_catalog.sqlite3"
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

if not DATA_ROOT.exists():
    raise FileNotFoundError(f"Expected datasets folder at {DATA_ROOT}")


def is_augmented(filename):
    # Ghana archives contain variants called ' (2).png', ' (3).png', etc.
    return bool(re.search(r"\s\(\d+\)(?=\.[^.]+$)|\bcopy\b", filename, re.I))


def class_from_name(filename):
    s = filename.lower()
    if s.startswith("non"):
        return 0
    if s.startswith("an"):  # Includes 'Anemic' and dataset typo 'Anmeic'
        return 1
    return None


def group_from_name(filename):
    # A conservative *filename family* only. NOT a verified patient identifier.
    stem = Path(filename).stem
    stem = re.sub(r"\s\(\d+\)$", "", stem)
    stem = re.sub(r"(?i)(fv|ra)$", "", stem)
    return stem


records = []

# CP-AnemiC: metadata includes laboratory Hb values.
cp_dir = DATA_ROOT / "Cp-Anameic Dataset V2"
if cp_dir.is_dir():
    spreadsheets = list(cp_dir.glob("*.xlsx"))
    if spreadsheets:
        metadata = pd.read_excel(spreadsheets[0], sheet_name=0)
        for _, r in metadata.iterrows():
            label = class_from_name(str(r["Folder_Label"]))
            if label is None:
                raise ValueError(f"Unknown CP-AnemiC label: {r['Folder_Label']}")
            folder = "Anaemic" if label == 1 else "Non-Anaemic"
            path = cp_dir / folder / str(r["File_Name"])
            if not path.is_file():
                raise FileNotFoundError(f"Missing CP-AnemiC file: {path}")
            records.append(("cp_anemic_v2", "conjunctiva", str(path.resolve()),
                            path.name, label, float(r["Hb_g_dl"]), str(r["Image_ID"]),
                            "hb_labeled_classification"))

# Ghana datasets: class is available in the filename but numeric Hb is not
# present in the uploaded archives. Exclude apparent augmented variants.
for source, foldername, modality in (
    ("ghana_conjunctiva", "Conjunctiva image Dataset from Ghana", "conjunctiva"),
    ("ghana_fingernail", "Fingernails", "nails"),
):
    folder = DATA_ROOT / foldername
    if not folder.is_dir():
        print(f"WARNING: Missing folder: {folder}")
        continue
    for path in folder.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        if is_augmented(path.name):
            continue
        label = class_from_name(path.name)
        if label is None:
            print(f"WARNING: Unknown filename label, skipped: {path.name}")
            continue
        records.append((source, modality, str(path.resolve()), path.name,
                        label, None, group_from_name(path.name),
                        "provided_class_only"))

# Tongue images have segmentation masks, NOT anaemia/Hb class labels.
tongue_root = DATA_ROOT / "TongueImage"
tongue_count = 0
if tongue_root.is_dir():
    for path in tongue_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS \
                and path.parent.name.lower() in {"image", "test"}:
            records.append(("tongue_segmentation", "tongue", str(path.resolve()),
                            path.name, None, None, path.stem, "segmentation_only"))
            tongue_count += 1
    if tongue_count == 0:
        print("NOTE: Tongue images not indexed yet. Extract the nested "
              "'tongue data.zip' inside your TongueImage folder first.")

if not records:
    raise RuntimeError("No records found. Check dataset folder names and extraction.")

with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""CREATE TABLE IF NOT EXISTS image_records (
        source TEXT NOT NULL,
        modality TEXT NOT NULL,
        file_path TEXT NOT NULL,
        filename TEXT NOT NULL,
        anaemia_label INTEGER,
        hb_g_dl REAL,
        filename_family TEXT,
        intended_task TEXT NOT NULL,
        PRIMARY KEY(source, file_path)
    )""")
    # Refresh only sources indexed in this run.
    for source in {row[0] for row in records}:
        conn.execute("DELETE FROM image_records WHERE source = ?", (source,))
    conn.executemany("""INSERT INTO image_records
        (source, modality, file_path, filename, anaemia_label,
         hb_g_dl, filename_family, intended_task)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", records)
    counts = conn.execute("""SELECT source, COUNT(*),
        SUM(CASE WHEN hb_g_dl IS NOT NULL THEN 1 ELSE 0 END)
        FROM image_records GROUP BY source ORDER BY source""").fetchall()

print("\nAYURAI LOCAL IMAGE CATALOG")
for source, count, hb_count in counts:
    print(f"{source}: {count} records ({hb_count or 0} with numeric Hb)")
print("Database:", DB_PATH)
print("Public research dataset index only; no patient-level linkage inferred.")
