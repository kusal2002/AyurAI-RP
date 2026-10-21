
"""AyurAI C1: run image models on quality-checked webcam captures.

Supported:
- Conjunctiva: experimental classification
- Nails: experimental classification and Hb regression
- Tongue: exploratory ImageHB Hb regression

All results are model evidence, not a clinical diagnosis.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from regional_image_evidence import summarize_region
from unified_image_inference import infer_image
from predict_tongue_hb import predict as predict_tongue_hb


REPO_ROOT = Path(__file__).resolve().parents[3]
SESSION_ROOT = REPO_ROOT.parent / "datasets" / "live_sessions"

CLASSIFICATION_REGIONS = {"conjunctiva", "nails"}
SUPPORTED = CLASSIFICATION_REGIONS | {"tongue"}


def run_tongue_inference(image_path: Path) -> dict:
    """Convert tongue Hb inference into the common evidence format."""

    prediction = predict_tongue_hb(
        image_path,
        verbose=False,
    )

    if not isinstance(prediction, dict):
        raise RuntimeError(
            "Tongue predictor did not return a result. "
            "Check that predict_tongue_hb.py returns its dictionary."
        )

    hb_estimate = prediction.get(
        "estimated_hb_g_dl_experimental"
    )

    if hb_estimate is None:
        raise RuntimeError(
            "Tongue model returned no Hb estimate"
        )

    return {
        "region": "tongue",
        "image_quality_assessed": True,
        "model_status": "exploratory_hb_regression",
        "classification_evidence": [],
        "experimental_hb_estimates_g_dl": [
            {
                "source": prediction.get(
                    "source", "imagehb_sample"
                ),
                "model": prediction.get(
                    "model", "efficientnet_b0"
                ),
                "estimate_g_dl": float(hb_estimate),
            }
        ],
        "limitations": [
            "Tongue model trained on 26 Hb-linked participants.",
            "Held-out test MAE was 1.2243 g/dL on five participants.",
            "Hb estimate is not a measured laboratory value.",
        ],
    }


def evaluate_session(session_id: str) -> dict:
    """Run region-specific inference on technically accepted images."""

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
        raise ValueError("Invalid session ID")

    session_dir = SESSION_ROOT / session_id
    quality_file = session_dir / "quality_report.json"

    if not quality_file.is_file():
        raise FileNotFoundError(
            f"Run assess_webcam_quality.py first: {quality_file}"
        )

    quality = json.loads(
        quality_file.read_text(encoding="utf-8")
    )

    if quality.get("session_id") != session_id:
        raise ValueError("Quality report session ID mismatch")

    outputs = []

    for entry in quality.get("results", []):
        image_path = Path(entry["image_path"]).resolve()

        try:
            image_path.relative_to(session_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Image outside session: {image_path}"
            ) from exc

        modality = entry["modality"]

        record = {
            "modality": modality,
            "image_path": str(image_path),
            "technical_quality_status": entry["status"],
            "technical_quality_flags": entry.get(
                "flags", []
            ),
            "clinical_risk_category": None,
        }

        if not image_path.is_file():

            record["status"] = (
                "image_missing_after_quality_check"
            )

        elif entry["status"] != "technical_checks_passed":

            record["status"] = (
                "retake_suggested_no_inference"
            )

        elif modality == "tongue":

            region = run_tongue_inference(image_path)

            record["status"] = (
                "experimental_inference_completed"
            )

            record["regional_evidence"] = region

        elif modality in CLASSIFICATION_REGIONS:

            inference = infer_image(
                image_path, modality
            )

            region = summarize_region(inference)

            region["image_quality_assessed"] = True

            record["status"] = (
                "experimental_inference_completed"
            )

            record["regional_evidence"] = region

        else:

            record["status"] = "unsupported_modality"

        outputs.append(record)

        print(
            f"{modality:<12} {record['status']}"
        )

        if (
            modality == "tongue"
            and record["status"]
            == "experimental_inference_completed"
        ):
            estimate = (
                record["regional_evidence"]
                ["experimental_hb_estimates_g_dl"][0]
                ["estimate_g_dl"]
            )

            print(
                f"  Tongue Hb estimate: "
                f"{estimate:.3f} g/dL"
            )

    report = {
        "session_id": session_id,
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds"),
        "processed_image_count": len(outputs),
        "missing_manifest_images": quality.get(
            "missing_files", 0
        ),
        "images": outputs,
        "limitations": (
            "Image predictions are experimental. "
            "Technical quality checks do not establish "
            "clinical validity. "
            "Conjunctiva and nail classifiers and "
            "Hb regression models were trained on "
            "different datasets. "
            "Fusion and clinical risk assessment "
            "require separate evaluation."
        ),
    }

    output_file = (
        session_dir / "image_model_results.json"
    )

    tmp_file = (
        session_dir / "image_model_results.json.tmp"
    )

    tmp_file.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    tmp_file.replace(output_file)

    print(f"\nSaved: {output_file}")

    counts = {
        modality: sum(
            result["modality"] == modality
            and result["status"]
            == "experimental_inference_completed"
            for result in outputs
        )
        for modality in SUPPORTED
    }

    print("\nIMAGE MODEL SUMMARY")

    for modality in (
        "conjunctiva", "nails", "tongue"
    ):
        print(
            f"{modality:<12}: "
            f"{counts[modality]} predictions"
        )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate quality-checked "
            "AyurAI webcam captures"
        )
    )

    parser.add_argument(
        "--session", required=True
    )

    args = parser.parse_args()

    print(
        "AYURAI - MULTI-REGION WEBCAM INFERENCE"
    )

    evaluate_session(args.session)


if __name__ == "__main__":
    main()
