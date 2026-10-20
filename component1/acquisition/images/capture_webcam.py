"""AyurAI Component 1: local webcam capture for a research/demo session.

Run from the repository root:
    python component1/acquisition/images/capture_webcam.py --camera 0

Keys: 1 = conjunctiva, 2 = nails, 3 = tongue, C/SPACE = capture, Q/ESC = quit.
Captured images and the session manifest are stored outside the Git repository.
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT.parent / "datasets"
CAPTURE_ROOT = DATA_ROOT / "live_sessions"
MODALITIES = {ord("1"): "conjunctiva", ord("2"): "nails", ord("3"): "tongue"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_manifest(path, manifest):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(path)


def capture(camera_index: int, session_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
        raise ValueError("Session ID may contain only letters, digits, - and _ (max 64).")

    session_dir = CAPTURE_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = session_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"session_id": session_id, "created_utc": utc_now(), "captures": []}
        save_manifest(manifest_path, manifest)

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cam = cv2.VideoCapture(camera_index, backend)
    if not cam.isOpened():
        cam.release()
        raise RuntimeError(
            f"Cannot open camera {camera_index}. Close the Windows Camera app, "
            "check camera permissions, or try --camera 1."
        )

    modality = "conjunctiva"
    window = "AyurAI - Webcam Capture (Q to quit)"
    print(f"Session: {session_id}")
    print(f"Storage: {session_dir}")
    print("1=conjunctiva  2=nails  3=tongue  C/SPACE=capture  Q/ESC=quit")

    try:
        while True:
            ok, frame = cam.read()
            if not ok or frame is None:
                raise RuntimeError("Camera opened but did not return a frame.")

            display = frame.copy()
            cv2.putText(display, f"Modality: {modality} | Session: {session_id}",
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(display, "1 Eye | 2 Nails | 3 Tongue | C Save | Q Quit",
                        (12, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255), 1)
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q"), 27):
                break
            if key in MODALITIES:
                modality = MODALITIES[key]
            elif key in (ord("c"), ord("C"), 32):
                folder = session_dir / "images" / modality
                folder.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
                image_path = folder / f"{modality}_{stamp}.png"
                # Portable save, including Windows paths containing non-ASCII characters.
                encoded_ok, encoded = cv2.imencode(".png", frame)
                if not encoded_ok:
                    raise RuntimeError("Could not encode captured frame as PNG.")
                encoded.tofile(str(image_path))
                manifest["captures"].append({
                    "modality": modality,
                    "captured_utc": utc_now(),
                    "image_path": str(image_path),
                    "camera_index": camera_index,
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                })
                save_manifest(manifest_path, manifest)
                print(f"Saved {modality}: {image_path}")
    finally:
        cam.release()
        cv2.destroyAllWindows()

    print(f"Completed: {len(manifest['captures'])} images in session {session_id}")
    print(f"Manifest: {manifest_path}")


def main():
    parser = argparse.ArgumentParser(description="Capture research/demo images locally")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (0 or 1)")
    parser.add_argument("--session", default=f"demo_{uuid.uuid4().hex[:8]}",
                        help="Pseudonymous session ID; do not enter patient name")
    args = parser.parse_args()
    capture(args.camera, args.session)


if __name__ == "__main__":
    main()
