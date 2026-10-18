
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_DIR.parent / "datasets"
DB_PATH = DATA_ROOT / "ayurai_image_catalog.sqlite3"
SPLIT_DIR = DATA_ROOT / "splits"

# source: (previous relative folder, new relative folder)
FOLDER_MAP = {
    "cp_anemic_v2": (
        "Cp-Anameic Dataset V2",
        "conjunctiva/Cp-Anameic Dataset V2",
    ),
    "ghana_conjunctiva": (
        "Conjunctiva image Dataset from Ghana",
        "conjunctiva/Conjunctiva image Dataset from Ghana",
    ),
    "ghana_fingernail": (
        "Fingernails",
        "nailbeds/Ghana_Fingernails",
    ),
    "tongue_segmentation": (
        "TongueImage",
        "tongue/TongueImage",
    ),
}

SPLIT_SOURCES = ("ghana_conjunctiva", "ghana_fingernail")


def migrate_path(source, file_path):
    """Preserve a file's relative subpath when changing its dataset root."""
    old_name, new_name = FOLDER_MAP[source]
    old_root = DATA_ROOT / old_name
    new_root = DATA_ROOT / new_name
    original = Path(file_path)

    try:
        suffix = original.relative_to(new_root)
    except ValueError:
        try:
            suffix = original.relative_to(old_root)
        except ValueError as exc:
            raise ValueError(
                f"Unexpected path in {source}: {original}"
            ) from exc

    replacement = new_root / suffix
    if not replacement.is_file():
        raise FileNotFoundError(
            f"Moved file missing; no changes made: {replacement}"
        )
    return str(replacement)


def main():
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    # Check ALL source paths before writing any changes.
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT source, file_path FROM image_records"
        ).fetchall()

    unknown_sources = {source for source, _ in rows} - set(FOLDER_MAP)
    if unknown_sources:
        raise ValueError(f"Unrecognized sources (not modified): {unknown_sources}")

    replacements = []
    by_source = {source: set() for source in FOLDER_MAP}
    for source, file_path in rows:
        new_path = migrate_path(source, file_path)
        replacements.append((new_path, source, file_path))
        if new_path in by_source[source]:
            raise ValueError(f"Duplicate destination path: {new_path}")
        by_source[source].add(new_path)

    split_updates = {}
    for source in SPLIT_SOURCES:
        split_file = SPLIT_DIR / f"{source}_split.csv"
        df = pd.read_csv(split_file)
        required = {"file_path", "filename_family", "split"}
        if not required.issubset(df.columns):
            raise ValueError(f"Unexpected split CSV columns: {split_file}")

        df["file_path"] = [
            migrate_path(source, path) for path in df["file_path"]
        ]
        if df["file_path"].duplicated().any():
            raise ValueError(f"Duplicate split paths: {split_file}")
        if set(df["file_path"]) != by_source[source]:
            raise ValueError(f"Split/database paths do not match: {source}")
        if df.groupby("filename_family")["split"].nunique().max() != 1:
            raise ValueError(f"Family split overlap detected: {source}")
        split_updates[split_file] = df

    # Backup old DB and CSVs after all validations have passed.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup = DATA_ROOT / f"ayurai_image_catalog.before_move_{stamp}.sqlite3"
    with sqlite3.connect(DB_PATH) as original, sqlite3.connect(db_backup) as backup:
        original.backup(backup)
    for csv_file in split_updates:
        shutil.copy2(csv_file, csv_file.with_name(csv_file.name + f".backup_{stamp}"))

    # Change only file paths: retain source, labels, Hb, groups and all splits.
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """UPDATE image_records SET file_path = ?
               WHERE source = ? AND file_path = ?""",
            replacements,
        )

    for csv_file, df in split_updates.items():
        temporary = csv_file.with_name(csv_file.name + ".tmp")
        df.to_csv(temporary, index=False)
        temporary.replace(csv_file)

    print("AYURAI DATASET PATH MIGRATION COMPLETE")
    for source, paths in by_source.items():
        print(f"{source}: {len(paths)} paths verified")
    for csv_file, df in split_updates.items():
        print(f"{csv_file.name}: {df['split'].value_counts().to_dict()}")
    print("Previous split membership preserved. Backup:", db_backup)
    print("Next run audit_image_db.py, then make_split_loaders.py (do not rebuild the catalogue yet).")


if __name__ == "__main__":
    main()
