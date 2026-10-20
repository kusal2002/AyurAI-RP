"""AyurAI C1: summarize outputs of dataset-specific image models for one region.

This is agreement/availability reporting, NOT calibrated ensemble fusion or clinical diagnosis.

Run from the repo root:
    python component1/models/images/regional_image_evidence.py --modality conjunctiva --image PATH
    python component1/models/images/regional_image_evidence.py --modality nails --image PATH
"""

import argparse
import json
from pathlib import Path

from unified_image_inference import infer_image


def summarize_region(inference):
    """Report source agreement without mixing Hb estimates with class scores."""
    modality = inference["modality"]
    results = inference["results"]

    classifiers = [
        entry for entry in results
        if entry.get("task") == "classification"
        and "predicted_class_at_0_5" in entry
    ]
    regression = [
        entry for entry in results
        if entry.get("task") == "hb_regression"
        and "estimated_hb_g_dl_experimental" in entry
    ]
    unavailable = [
        entry.get("source", "unknown") for entry in results
        if "task" not in entry
    ]

    summary = {
        "modality": modality,
        "image_quality_assessed": False,
        "models_available": len(classifiers) + len(regression),
        "models_unavailable": unavailable,
        "clinical_risk_category": None,
        "classification_evidence": [
            {
                "source": entry["source"],
                "class_vote_at_0_5": entry["predicted_class_at_0_5"],
                "score_uncalibrated": entry["anaemia_class_score_uncalibrated"],
            }
            for entry in classifiers
        ],
    }

    if modality == "conjunctiva":
        if len(classifiers) < 2:
            summary["status"] = "insufficient_model_outputs"
        else:
            votes = {entry["predicted_class_at_0_5"] for entry in classifiers}
            summary["status"] = (
                "classifier_agreement" if len(votes) == 1
                else "classifier_disagreement"
            )
            summary["agreed_class_vote"] = (
                next(iter(votes)) if len(votes) == 1 else None
            )
    elif modality == "nails":
        summary["status"] = "mixed_output_types_not_calibrated_for_fusion"
        summary["experimental_hb_estimates_g_dl"] = [
            {"source": entry["source"], "estimate_g_dl": entry["estimated_hb_g_dl_experimental"]}
            for entry in regression
        ]
    else:
        raise ValueError(f"Unsupported modality: {modality}")

    summary["interpretation"] = (
        "Experimental evidence only. Scores are uncalibrated and images have not "
        "passed a quality check. No clinical screening conclusion can be drawn."
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modality", required=True, choices=["conjunctiva", "nails"])
    parser.add_argument("--image", required=True, type=Path)
    args = parser.parse_args()

    inference = infer_image(args.image, args.modality)
    print(json.dumps(summarize_region(inference), indent=2))


if __name__ == "__main__":
    main()
