"""One-time step: CP-AnemiC images + lab Hb -> features CSV with a clinic per patient.

Usage:  python component4/federated/prepare_data.py
Reads   <C4_DATA_DIR>/Cp-Anameic Dataset V2/...   (images + Excel with Hb)
Writes  <C4_DATA_DIR>/processed/cpanemic_features.csv   (outside the repo)

Each row is one patient (the dataset has one image per patient, identified by
group_id), so no patient can end up in two clinics or in both train and test.
"""

import csv
import sys

import numpy as np
import pandas as pd

from config import (
    CLINIC_PROFILES,
    DATA_DIR,
    FEATURES_FILE,
    HB_HIGH_RISK_BELOW,
    HB_LOW_RISK_FROM,
    TIER_NAMES,
)
from features import FEATURE_NAMES, colour_features

SPLIT_SEED = 42   # fixed, so every run assigns the same patients to the same clinic


def risk_tier(hb):
    """Lab haemoglobin (g/dL) -> class 0 Low, 1 Moderate, 2 High."""
    if hb < HB_HIGH_RISK_BELOW:
        return 2
    if hb < HB_LOW_RISK_FROM:
        return 1
    return 0


def assign_clinics(rows):
    """Non-IID split: send each tier's patients to clinics in the configured shares."""
    rng = np.random.default_rng(SPLIT_SEED)
    clinic_ids = sorted(CLINIC_PROFILES)
    for tier in range(len(TIER_NAMES)):
        members = [row for row in rows if row["tier"] == tier]
        rng.shuffle(members)
        start = 0
        for i, clinic_id in enumerate(clinic_ids):
            share = CLINIC_PROFILES[clinic_id]["tier_shares"][tier]
            # the last clinic takes the remainder, so rounding never drops a patient
            end = len(members) if i == len(clinic_ids) - 1 else start + round(share * len(members))
            for row in members[start:end]:
                row["clinic_id"] = clinic_id
            start = end


if __name__ == "__main__":
    if DATA_DIR is None:
        sys.exit("Set C4_DATA_DIR in component4/.env (folder that contains the datasets).")
    base = DATA_DIR / "Cp-Anameic Dataset V2" / "Cp-Anameic Dataset V2"
    excel = base / "Cp-Anaemic Dataset.xlsx"

    rows = []
    # The Excel has one sheet per image folder, each with the patient's group_id and lab Hb
    for sheet, folder in [("Anaemic", "Anaemic"), ("Non-Anaemic", "Non-Anaemic")]:
        for record in pd.read_excel(excel, sheet_name=sheet).to_dict("records"):
            hb = float(record["hb_g_dl"])
            rows.append({
                "group_id": int(record["group_id"]),
                "filename": record["filename"],
                "hb_g_dl": hb,
                "tier": risk_tier(hb),
                **dict(zip(FEATURE_NAMES, colour_features(base / folder / record["filename"]))),
            })

    if len({row["group_id"] for row in rows}) != len(rows):
        sys.exit("A patient (group_id) has more than one image; split by patient before continuing.")

    assign_clinics(rows)

    FEATURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    columns = ["group_id", "filename", "hb_g_dl", "tier", "clinic_id"] + FEATURE_NAMES
    with open(FEATURES_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} patients -> {FEATURES_FILE}")
    table = pd.DataFrame(rows)
    print(pd.crosstab(table["clinic_id"], table["tier"].map(dict(enumerate(TIER_NAMES))), margins=True))
