"""AyurAI Component 1: preliminary technical checks for webcam captures.

Run from repository root:
    python component1/quality/images/assess_webcam_quality.py --session demo_xxxxxxxx

Reads one existing session's manifest and writes quality_report.json alongside it.
Does not train models, identify anatomical regions, or assess clinical image validity.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
SESSION_ROOT = REPO_ROOT.parent / "datasets" / "live_sessions"


def assess_image(image_path: Path) -> dict:
    """Return preliminary technical quality metrics and retake suggestions."""
    raw_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable image: {image_path}")

    height, width = image.shape[:2]
    # Standardize blur calculations across different webcam resolutions.
    scale = min(1.0, 640.0 / max(width, height))
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    contrast = float(gray.std())
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    too_dark_fraction = float((gray <= 10).mean())
    too_bright_fraction = float((gray >= 245).mean())

    reasons = []
    if min(width, height) < 240:
        reasons.append("low_resolution")
    if brightness < 50:
        reasons.append("too_dark")
    elif brightness > 205:
        reasons.append("too_bright")
    if blur_variance < 60:
        reasons.append("possible_blur")
    if contrast < 18:
        reasons.append("low_contrast")
    if too_dark_fraction > 0.30:
        reasons.append("large_dark_region")
    if too_bright_fraction > 0.30:
        reasons.append("large_overexposed_region")

    return {
        "width": int(width),
        "height": int(height),
        "mean_brightness": round(brightness, 2),
        "contrast_std": round(contrast, 2),
        "blur_laplacian_variance": round(blur_variance, 2),
        "dark_fraction": round(too_dark_fraction, 3),
        "overexposed_fraction": round(too_bright_fraction, 3),
        "status": "retake_suggested" if reasons else "technical_checks_passed",
        "flags": reasons,
    }


def inspect_session(session_dir: Path) -> dict:
    """Assess every captured image listed in a session manifest."""
    session_dir = session_dir.resolve()
    manifest_path = session_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No session manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captures = manifest.get("captures", [])
    if not isinstance(captures, list):
        raise ValueError("Manifest captures must be a list")

    results = []
    missing_files = []
    for capture in captures:
        path = Path(capture["image_path"]).resolve()
        try:
            path.relative_to(session_dir)
        except ValueError as exc:
            raise ValueError(f"Capture path is outside session folder: {path}") from exc
        if not path.is_file():
            missing_files.append({
                "modality": capture["modality"],
                "image_path": str(path),
                "reason": "file_not_found",
            })
            print(f"WARNING: Missing {capture['modality']} image: {path.name}")
            continue
        result = assess_image(path)
        results.append({
            "modality": capture["modality"],
            "image_path": str(path),
            **result,
        })
        print(f"{capture['modality']:<12} {result['status']:<24} "
              f"blur={result['blur_laplacian_variance']:>8.1f} "
              f"brightness={result['mean_brightness']:>6.1f} "
              f"flags={','.join(result['flags']) or '-'}")

    report = {
        "session_id": manifest.get("session_id", session_dir.name),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_entries": len(captures),
        "total_images": len(results),
        "missing_files": len(missing_files),
        "missing_image_entries": missing_files,
        "technical_checks_passed": sum(
            r["status"] == "technical_checks_passed" for r in results
        ),
        "retake_suggested": sum(
            r["status"] == "retake_suggested" for r in results
        ),
        "results": results,
        "limitations": (
            "Heuristic technical checks only; these do not confirm proper "
            "conjunctiva, nail, or tongue framing, model suitability, or clinical validity."
        ),
    }
    output_path = session_dir / "quality_report.json"
    temp_path = session_dir / "quality_report.json.tmp"
    temp_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temp_path.replace(output_path)
    print(f"\nQuality report saved: {output_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit local webcam session images")
    parser.add_argument("--session", required=True, help="Existing pseudonymous session ID")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.session):
        parser.error("Session ID must contain only letters, digits, - or _")
    session_dir = SESSION_ROOT / args.session
    print("AYURAI - WEBCAM IMAGE QUALITY CHECK")
    print(f"Session: {args.session}\n")
    report = inspect_session(session_dir)
    print(f"\nImages: {report['total_images']} | "
          f"Technical checks passed: {report['technical_checks_passed']} | "
          f"Retake suggested: {report['retake_suggested']} | "
          f"Missing files: {report['missing_files']}")
    print("These checks do not verify clinical suitability or anatomical framing.")


if __name__ == "__main__":
    main()
