"""AyurAI C1: run existing image models on technically accepted webcam captures.

Usage from repo root:
  python component1/models/images/evaluate_webcam_session.py --session demo_XXXXXXXX

The resulting JSON is experimental image-model evidence, not a diagnosis.
Tongue photographs are recorded as quality-only until a validated model exists.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from regional_image_evidence import summarize_region
from unified_image_inference import infer_image

REPO_ROOT = Path(__file__).resolve().parents[3]
SESSION_ROOT = REPO_ROOT.parent / "datasets" / "live_sessions"
SUPPORTED = {"conjunctiva", "nails"}


def evaluate_session(session_id: str) -> dict:
    """Attach separate model outputs to images that passed technical checks."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
        raise ValueError("Invalid session ID")

    session_dir = SESSION_ROOT / session_id
    quality_file = session_dir / "quality_report.json"
    if not quality_file.is_file():
        raise FileNotFoundError(
            f"Run assess_webcam_quality.py first: {quality_file}"
        )

    quality = json.loads(quality_file.read_text(encoding="utf-8"))
    if quality.get("session_id") != session_id:
        raise ValueError("Quality report session ID mismatch")

    outputs = []
    for entry in quality.get("results", []):
        image_path = Path(entry["image_path"]).resolve()
        try:
            image_path.relative_to(session_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"Image outside session: {image_path}") from exc

        modality = entry["modality"]
        record = {
            "modality": modality,
            "image_path": str(image_path),
            "technical_quality_status": entry["status"],
            "technical_quality_flags": entry.get("flags", []),
            "clinical_risk_category": None,
        }

        if not image_path.is_file():
            record["status"] = "image_missing_after_quality_check"
        elif entry["status"] != "technical_checks_passed":
            record["status"] = "retake_suggested_no_inference"
        elif modality == "tongue":
            record["status"] = "tongue_quality_only_no_anaemia_model"
        elif modality in SUPPORTED:
            inference = infer_image(image_path, modality)
            region = summarize_region(inference)
            region["image_quality_assessed"] = True
            # 'Passed' applies to simple technical checks only, not anatomy/clinical validity.
            record["status"] = "experimental_inference_completed"
            record["regional_evidence"] = region
        else:
            record["status"] = "unsupported_modality"

        outputs.append(record)
        print(f"{modality:<12} {record['status']}")

    report = {
        "session_id": session_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "processed_image_count": len(outputs),
        "missing_manifest_images": quality.get("missing_files", 0),
        "images": outputs,
        "limitations": (
            "Experimental uncalibrated outputs; technical quality checks do not "
            "establish anatomical validity, clinical reliability, or diagnosis. "
            "Different output types are not combined into a risk score."
        ),
    }

    output_file = session_dir / "image_model_results.json"
    tmp_file = session_dir / "image_model_results.json.tmp"
    tmp_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tmp_file.replace(output_file)
    print(f"\nSaved: {output_file}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate quality-checked webcam captures")
    parser.add_argument("--session", required=True)
    args = parser.parse_args()
    print("AYURAI - WEBCAM IMAGE MODEL INFERENCE")
    evaluate_session(args.session)


if __name__ == "__main__":
    main()
