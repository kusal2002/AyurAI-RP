"""Reference-derived Component 1 sample outputs from NHANES public-use data.

No Component 1 model exists in this repository, and no public dataset
contains Component 1 outputs. To test the C1 -> C2 integration on real,
de-identified people, this module builds payloads in the provisional
`C1ScreeningPayload` contract from NHANES 2017-March 2020 files:

- risk tier: from **measured** laboratory haemoglobin (P_CBC LBXHGB) using
  the WHO 2024 severity cutoffs (Guideline on haemoglobin cutoffs to define
  anaemia, Table 3) for non-pregnant adults aged 15-65:

  | Group | No anaemia | Mild | Moderate | Severe |
  |---|---|---|---|---|
  | Non-pregnant women | >= 12.0 | 11.0-11.9 | 8.0-10.9 | < 8.0 g/dL |
  | Men | >= 13.0 | 11.0-12.9 | 8.0-10.9 | < 8.0 g/dL |

  Provisional tier mapping (to be confirmed by the Component 1 owner):
  no anaemia -> low, mild -> moderate, moderate or severe -> high.
- symptoms: "fatigue" from DPQ040 (feeling tired or having little energy,
  >= "several days" = present), "breathlessness" from CDQ010 (shortness of
  breath on stairs or inclines; asked at age 40+). Refused, don't-know and
  missing answers are listed in missing_data, never guessed.
- screening confidence: null. No model produced these cases.
- image and PPG modalities: not collected (listed in missing_data).

These payloads are **not Component 1 model outputs**. Their status is
`reference_derived_not_model_output`. They exercise the integration with
real symptom and haemoglobin combinations. Use of NHANES data follows the
NCHS Data User Agreement: statistical and analysis use only, no attempt
to identify any person, no linking with identifiable data. SEQN (the
public respondent number) is kept for traceability only.

Usage:
    python -m app.integration.c1_reference_samples corpus/raw/c1_reference/nhanes_2017_2020 \
        --out corpus/extracted/c1_samples/nhanes_reference_samples.json [--per-tier 20]
"""

import argparse
import json
import random
import struct
from pathlib import Path

from app.models.c1_screening_payload import C1ScreeningPayload


DERIVATION_VERSION = "1"
_RECORD = 80


# --- SAS XPORT (v5) reader ----------------------------------------------------

def _ibm_to_float(raw: bytes) -> float | None:
    """IBM System/360 8-byte float -> Python float; None for SAS missing."""
    # SAS missing values: '.', '._' or '.A'-'.Z' in the first byte, zeros after.
    is_missing_code = raw[0] in (0x2E, 0x5F) or 0x41 <= raw[0] <= 0x5A
    if is_missing_code and raw[1:] == b"\x00" * 7:
        return None
    if raw == b"\x00" * 8:
        return 0.0
    sign = -1.0 if raw[0] & 0x80 else 1.0
    exponent = (raw[0] & 0x7F) - 64
    mantissa = int.from_bytes(raw[1:8], "big") / float(1 << 56)
    return sign * mantissa * (16.0 ** exponent)


def read_xpt(path: str | Path, columns: set[str] | None = None) -> list[dict]:
    """Read a single-member SAS XPORT v5 file into a list of row dicts.

    Only the standard layout used by NHANES is supported: one member,
    140-byte NAMESTR records. Numeric values become floats or None
    (missing); character values are stripped strings.
    """
    data = Path(path).read_bytes()
    if not data.startswith(b"HEADER RECORD*******LIBRARY HEADER RECORD"):
        raise ValueError(f"{Path(path).name} is not a SAS XPORT file.")
    marker = b"HEADER RECORD*******NAMESTR HEADER RECORD"
    start = data.find(marker)
    if start < 0:
        raise ValueError("NAMESTR header not found.")
    header = data[start:start + _RECORD]
    count = int(header[54:58])
    offset = start + _RECORD
    variables = []
    for index in range(count):
        record = data[offset + index * 140: offset + (index + 1) * 140]
        ntype, _, length = struct.unpack(">hhh", record[0:6])
        name = record[8:16].decode("ascii").strip()
        position = struct.unpack(">i", record[84:88])[0]
        variables.append((name, ntype, length, position))
    offset += count * 140
    offset += (-offset) % _RECORD
    obs_marker = b"HEADER RECORD*******OBS     HEADER RECORD"
    if data[offset:offset + len(obs_marker)] != obs_marker:
        found = data.find(obs_marker, offset)
        if found < 0:
            raise ValueError("OBS header not found.")
        offset = found
    offset += _RECORD
    width = sum(length for _, _, length, _ in variables)
    wanted = [v for v in variables if columns is None or v[0] in columns]
    rows = []
    while offset + width <= len(data):
        chunk = data[offset:offset + width]
        offset += width
        if chunk.strip(b" ") == b"":
            break  # trailing padding
        row = {}
        for name, ntype, length, position in wanted:
            raw = chunk[position:position + length]
            if ntype == 1:
                row[name] = _ibm_to_float(raw.ljust(8, b"\x00"))
            else:
                row[name] = raw.decode("latin-1").strip()
        rows.append(row)
    return rows


# --- derivation -----------------------------------------------------------------

def who_2024_severity(hb_g_dl: float, sex: str) -> str:
    """WHO 2024 Table 3 severity for non-pregnant adults aged 15-65."""
    if hb_g_dl < 8.0:
        return "severe"
    if hb_g_dl < 11.0:
        return "moderate"
    threshold = 12.0 if sex == "female" else 13.0
    return "mild" if hb_g_dl < threshold else "none"


def _age_band(age: int) -> str:
    """Five-year band, capped at the sample's upper age of 65."""
    low = (age // 5) * 5
    high = min(low + 4, 65)
    return str(low) if low == high else f"{low}-{high}"


TIER_BY_SEVERITY = {"none": "low", "mild": "moderate", "moderate": "high", "severe": "high"}


def _answer(value: float | None, present_if) -> bool | None:
    if value is None or value in (7.0, 9.0, 77.0, 99.0):
        return None
    return present_if(value)


def build_payload(seqn: int, sex: str, age: int, hb: float,
                  dpq040: float | None, cdq010: float | None) -> C1ScreeningPayload:
    severity = who_2024_severity(hb, sex)
    tier = TIER_BY_SEVERITY[severity]
    symptoms, missing = [], ["conjunctiva_image", "nailbed_image", "tongue_image", "ppg_signal"]
    fatigue = _answer(dpq040, lambda v: v >= 1.0)
    breathless = _answer(cdq010, lambda v: v == 1.0)
    if fatigue is None:
        missing.append("questionnaire:fatigue")
    else:
        symptoms.append({"name": "fatigue", "present": fatigue})
    if breathless is None:
        missing.append("questionnaire:breathlessness")
    else:
        symptoms.append({"name": "breathlessness", "present": breathless})
    return C1ScreeningPayload.model_validate({
        "screening_id": f"nhanes-p-{int(seqn)}",
        "session_id": f"nhanes-2017-2020-ref-v{DERIVATION_VERSION}",
        "screening_result": {
            "condition": "anemia",
            "risk_level": tier,
            "screening_confidence": None,
            "evidence_strength": "reference_standard_laboratory_haemoglobin",
            "status": "reference_derived_not_model_output",
            "requires_clinician_review": True,
        },
        "hemoglobin": {
            "estimated_g_dl": None,
            "measured_lab_g_dl": round(hb, 1),
            "source": "NHANES 2017-March 2020 laboratory CBC (LBXHGB)",
            "clinically_validated": True,
        },
        "modality_results": {
            "conjunctiva": {"model_predictions": [], "quality_score": 0.0, "agreement": False},
            "nailbeds": {"anaemia_class_score": None, "estimated_hb_g_dl": None, "quality_score": None},
            "tongue": {"quality_status": "not_collected", "anaemia_prediction": None},
            "ppg": {"estimated_hb_g_dl": None, "signal_quality": None, "status": "not_collected"},
        },
        "symptoms": symptoms,
        "clinical_findings": [{"finding": "who_2024_anaemia_severity", "value": severity}],
        "contributing_factors": [f"sex:{sex}", f"age_band:{_age_band(age)}"],
        "missing_data": missing,
        "recommendation": "Reference-derived test case for integration testing; not a screening result.",
        "model_version": f"none (NHANES reference derivation v{DERIVATION_VERSION})",
        "disclaimer": ("Derived from NHANES public-use data under the NCHS Data User Agreement. "
                       "Not a Component 1 model output and not a diagnosis."),
    })


def derive_samples(nhanes_dir: str | Path, per_tier: int = 20, seed: int = 2026) -> dict:
    nhanes_dir = Path(nhanes_dir)
    demo = {r["SEQN"]: r for r in read_xpt(nhanes_dir / "P_DEMO.xpt", {"SEQN", "RIAGENDR", "RIDAGEYR", "RIDEXPRG"})}
    cbc = {r["SEQN"]: r for r in read_xpt(nhanes_dir / "P_CBC.xpt", {"SEQN", "LBXHGB"})}
    dpq = {r["SEQN"]: r for r in read_xpt(nhanes_dir / "P_DPQ.xpt", {"SEQN", "DPQ040"})}
    cdq = {r["SEQN"]: r for r in read_xpt(nhanes_dir / "P_CDQ.xpt", {"SEQN", "CDQ010"})}

    counts = {"demographic_records": len(demo), "eligible": 0}
    by_tier: dict[str, list] = {"low": [], "moderate": [], "high": []}
    for seqn in sorted(demo):
        person = demo[seqn]
        age, hb = person.get("RIDAGEYR"), (cbc.get(seqn) or {}).get("LBXHGB")
        if age is None or hb is None or not 40 <= age <= 65:
            continue
        if person.get("RIDEXPRG") == 1.0:
            continue  # pregnancy cutoffs depend on an unrecorded trimester
        sex = {1.0: "male", 2.0: "female"}.get(person.get("RIAGENDR"))
        if sex is None:
            continue
        counts["eligible"] += 1
        payload = build_payload(seqn, sex, int(age), hb,
                                (dpq.get(seqn) or {}).get("DPQ040"),
                                (cdq.get(seqn) or {}).get("CDQ010"))
        by_tier[payload.screening_result.risk_level].append(payload)

    rng = random.Random(seed)
    selected = []
    for tier, items in by_tier.items():
        counts[f"eligible_{tier}"] = len(items)
        selected += rng.sample(items, min(per_tier, len(items)))
    return {
        "derivation_version": DERIVATION_VERSION,
        "source": "NHANES 2017-March 2020 pre-pandemic public-use files P_DEMO, P_CBC, P_DPQ, P_CDQ",
        "method": ("risk tier from measured Hb by WHO 2024 Table 3 (non-pregnant adults 40-65); "
                   "symptoms from DPQ040 and CDQ010; confidence null; stratified sample, seed "
                   f"{seed}, {per_tier} per tier"),
        "not_model_output": True,
        "counts": counts,
        "payloads": [p.model_dump(mode="json") for p in selected],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.integration.c1_reference_samples")
    parser.add_argument("nhanes_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-tier", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)
    result = derive_samples(args.nhanes_dir, args.per_tier, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"]))
    print(f"Wrote {len(result['payloads'])} reference-derived payloads to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
