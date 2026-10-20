
# AyurAI - Reproducible image dataset splitting

from pathlib import Path
import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT.parent / "datasets"

DB_PATH = DATA_ROOT / "ayurai_image_catalog.sqlite3"
OUTPUT_DIR = DATA_ROOT / "splits"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = ["ghana_conjunctiva", "ghana_fingernail"]

with sqlite3.connect(DB_PATH) as conn:

    for source in SOURCES:

        df = pd.read_sql_query(
            """
            SELECT source, file_path, filename,
                   filename_family, anaemia_label
            FROM image_records
            WHERE source = ?
              AND anaemia_label IS NOT NULL
            """,
            conn,
            params=(source,)
        )

        if df.empty:
            raise ValueError(f"No records for {source}")

        if df["filename_family"].isna().any():
            raise ValueError("Missing filename family")

        # Ensure related filenames have consistent class labels
        label_counts = df.groupby(
            "filename_family"
        )["anaemia_label"].nunique()

        if (label_counts > 1).any():
            raise ValueError(
                f"Conflicting labels in {source}"
            )

        # Split filename families, not individual image rows
        families = df.groupby(
            "filename_family", as_index=False
        )["anaemia_label"].first()

        train_groups, remaining_groups = train_test_split(
            families,
            test_size=0.30,
            random_state=42,
            stratify=families["anaemia_label"]
        )

        val_groups, test_groups = train_test_split(
            remaining_groups,
            test_size=0.50,
            random_state=42,
            stratify=remaining_groups["anaemia_label"]
        )

        def assign_split(groups, name):
            selected = df[
                df["filename_family"].isin(
                    groups["filename_family"]
                )
            ].copy()

            selected["split"] = name
            return selected

        result = pd.concat([
            assign_split(train_groups, "train"),
            assign_split(val_groups, "validation"),
            assign_split(test_groups, "test")
        ], ignore_index=True)

        # Verify every image appears exactly once
        assert len(result) == len(df)
        assert result["file_path"].is_unique

        # Verify no filename family crosses splits
        assert (
            result.groupby("filename_family")["split"]
            .nunique().max() == 1
        )

        output_file = OUTPUT_DIR / f"{source}_split.csv"
        result.to_csv(output_file, index=False)

        print(f"\n{source.upper()}")
        print("------------------------------")
        print(result.groupby("split").size())
        print("\nClass distribution:")
        print(pd.crosstab(
            result["split"],
            result["anaemia_label"]
        ))
        print("Saved:", output_file)

print("\nDataset splitting completed!")
