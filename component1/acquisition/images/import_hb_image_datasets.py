"""Import Hb-linked public image metadata into AyurAI's local SQLite catalogue.

Keeps prior image_records and saved dataset splits unchanged.
Does not infer anaemia labels or use personal details from source CSVs.
"""

from pathlib import Path
import sqlite3
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT.parent / "datasets"
DB_PATH = DATA_ROOT / "ayurai_image_catalog.sqlite3"

REGION_MODALITY = {
    "left_eye": "eye", "right_eye": "eye",
    "left_nail": "nails", "right_nail": "nails",
    "tongue": "tongue", "palm_left": "palm", "palm_right": "palm",
}


def find_one(root, filename):
    """Find a metadata file even if the archive created an extra subfolder."""
    if not root.is_dir():
        raise FileNotFoundError(f"Dataset folder missing: {root}")
    matches = list(root.rglob(filename))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {filename} under {root}, found {len(matches)}. "
            "Check extraction and remove duplicate nested copies."
        )
    return matches[0]


def patient_id(value):
    """Convert numeric CSV identifiers without changing their values."""
    if pd.isna(value):
        raise ValueError("Missing participant identifier")
    return str(int(value))


def valid_hb(value, source, participant):
    hb = float(value)
    if not (2.0 <= hb <= 25.0):
        raise ValueError(f"Suspicious Hb in {source}, participant {participant}: {hb}")
    return hb


def collect_yakimov():
    root = DATA_ROOT / "nailbeds" / "Yakimov_Hb_2024"
    metadata_file = find_one(root, "metadata.csv")
    df = pd.read_csv(metadata_file)
    required = {"PATIENT_ID", "HB_LEVEL_GperL"}
    if not required.issubset(df):
        raise ValueError(f"Yakimov metadata missing: {required - set(df)}")
    if df.PATIENT_ID.isna().any() or df.PATIENT_ID.duplicated().any():
        raise ValueError("Yakimov IDs are missing or duplicated")

    photos = metadata_file.parent / "photo"
    records = []
    for row in df.itertuples(index=False):
        participant = patient_id(row.PATIENT_ID)
        path = photos / f"{participant}.jpg"
        if not path.is_file():
            raise FileNotFoundError(f"Yakimov photo missing: {path}")
        hb = valid_hb(row.HB_LEVEL_GperL / 10.0, "yakimov", participant)
        records.append((
            "yakimov_hb_2024", participant, "nails", "nail_photo",
            str(path.resolve()), hb, "measured_Hb_g_per_L_divided_by_10"
        ))
    return records


def collect_imagehb():
    root = DATA_ROOT / "multimodal" / "ImageHB"
    metadata_file = find_one(root, "DATASAMPLE.csv")
    df = pd.read_csv(metadata_file)
    required = {"Image ID", "Haemoglobin (gm/dL)"}
    if not required.issubset(df):
        raise ValueError(f"ImageHB metadata missing: {required - set(df)}")
    if df["Image ID"].isna().any() or df["Image ID"].duplicated().any():
        raise ValueError("ImageHB IDs are missing or duplicated")

    records = []
    for _, row in df.iterrows():
        participant = patient_id(row["Image ID"])
        hb = valid_hb(row["Haemoglobin (gm/dL)"], "imagehb", participant)
        for region, modality in REGION_MODALITY.items():
            path = metadata_file.parent / region / f"{participant}.jpeg"
            if not path.is_file():
                raise FileNotFoundError(f"ImageHB photo missing: {path}")
            records.append((
                "imagehb_sample", participant, modality, region,
                str(path.resolve()), hb, "measured_Hb_g_per_dL"
            ))
    return records


def main():
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Existing database not found: {DB_PATH}")

    # Validate every source file before making database changes.
    yakimov = collect_yakimov()
    imagehb = collect_imagehb()
    rows = yakimov + imagehb
    if len({(row[0], row[4]) for row in rows}) != len(rows):
        raise ValueError("Duplicate source/file_path pair")

    with sqlite3.connect(DB_PATH) as conn:
        original_count = conn.execute("SELECT COUNT(*) FROM image_records").fetchone()[0]
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hb_image_records (
                source TEXT NOT NULL,
                participant_id TEXT NOT NULL,
                modality TEXT NOT NULL,
                region TEXT NOT NULL,
                file_path TEXT NOT NULL,
                hb_g_dl REAL NOT NULL,
                hb_source TEXT NOT NULL,
                PRIMARY KEY(source, file_path)
            )
        """)
        # Only refresh new Hb-linked sources. Original training records are untouched.
        conn.execute("DELETE FROM hb_image_records WHERE source IN (?, ?)",
                     ("yakimov_hb_2024", "imagehb_sample"))
        conn.executemany("""
            INSERT INTO hb_image_records
                (source, participant_id, modality, region, file_path, hb_g_dl, hb_source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows)
        new_original_count = conn.execute("SELECT COUNT(*) FROM image_records").fetchone()[0]
        if new_original_count != original_count:
            raise RuntimeError("Original image_records count changed; aborting")

    print("AYURAI HB IMAGE IMPORT COMPLETE")
    print(f"Yakimov: {len(yakimov)} Hb-linked photographs / "
          f"{len(set(row[1] for row in yakimov))} participants")
    print(f"ImageHB sample: {len(imagehb)} Hb-linked photographs / "
          f"{len(set(row[1] for row in imagehb))} participants")
    print(f"Existing image_records preserved: {original_count}")
    print("Existing dataset splits unchanged.")
    print("Note: no anaemia thresholds or binary labels have been inferred.")
    print("Database:", DB_PATH)


if __name__ == "__main__":
    main()
