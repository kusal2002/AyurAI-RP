"""End-to-end Component 1 intake workflow tests in an ISOLATED temporary datasets folder.

Every module path constant is redirected to a temp directory, so the real
../datasets (sessions, SQLite, reports) is never read or written. The ESP32 is
replaced by a FAKE serial port that exists only inside these tests; images are
synthetic. Nothing here is a hardware or patient result.

Run from repository root (takes ~1 minute; the real image models run once):
    python -m unittest component1.tests.test_intake_workflow -v
"""

import asyncio
import io
import json
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import serial
from fastapi import HTTPException, UploadFile

from component1.acquisition.ppg import capture_live_ppg, register_session_ppg, register_session_vitals
from component1.api import intake, server
from component1.fusion import fuse_screening_session

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DATA_ROOT = REPO_ROOT.parent / "datasets"
sys.path.insert(0, str(REPO_ROOT / "component1" / "models" / "images"))
import evaluate_webcam_session  # noqa: E402

ADULT = {"age_months": 300, "sex": "female", "pregnancy_status": "not_pregnant"}
COMMON_NO_SAFETY = {"SAF01": "no", "SAF02": "no", "SAF03": "no", "SAF04": "no"}


class FakeEsp32:
    """Fake serial port streaming the AyurAI firmware protocol at ~25 Hz (tests only)."""

    def __init__(self, *args, **kwargs):
        self.t0 = time.monotonic()
        self.n = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def reset_input_buffer(self):
        pass

    def readline(self):
        time.sleep(0.04)
        self.n += 1
        ms = int((time.monotonic() - self.t0) * 1000)
        if self.n % 25 == 0:
            return f"#METRICS,{ms},72,98,null,1\n".encode()
        pulse = math.sin(2 * math.pi * 1.2 * self.n / 25)
        red = int(100000 * (1 + 0.004 * pulse))
        ir = int(120000 * (1 + 0.004 * pulse))
        return f"{ms},{red},{ir}\n".encode()


def failing_serial(message):
    def factory(*args, **kwargs):
        raise serial.SerialException(message)
    return factory


def png_bytes(seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((480, 640, 3), (120, 110, 200), np.uint8)
    img = cv2.add(img, rng.integers(0, 60, img.shape, dtype=np.uint8))
    for x in range(0, 640, 16):
        cv2.line(img, (x, 0), (x, 479), (60, 60, 150), 2)
    return cv2.imencode(".png", img)[1].tobytes()


def upload(session_id, modality, seed=0, replaces=None, data=None):
    payload = png_bytes(seed) if data is None else data
    return asyncio.run(intake.upload_image(
        session_id, modality, UploadFile(file=io.BytesIO(payload), filename=f"{modality}.png"), replaces))


def wait_for_job(timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = intake.ppg_job()["job"]
        if job["state"] in ("saved", "failed", "cancelled", "probe_ok"):
            return job
        time.sleep(0.2)
    raise AssertionError("PPG job did not finish")


def questionnaire_body(answers, **overrides):
    body = {"profile": ADULT, "consent": True, "consent_ppg": True, "consent_images": True,
            "answers": answers, "no_medications": True, "no_allergies": True}
    body.update(overrides)
    return intake.QuestionnaireIn(**body)


class IsolatedDatasets(unittest.TestCase):
    """Redirects every Component 1 data path to a temporary folder (no tests of its own)."""

    @classmethod
    def setUpClass(cls):
        # Reused scripts open SQLite without closing; ignore_cleanup_errors avoids Windows file locks.
        cls.tmp = tempfile.TemporaryDirectory(prefix="c1_intake_test_", ignore_cleanup_errors=True)
        root = Path(cls.tmp.name) / "datasets"
        sessions = root / "live_sessions"
        sessions.mkdir(parents=True)
        db = root / "screening_sessions.sqlite3"
        assert root.resolve() != REAL_DATA_ROOT.resolve()
        cls.root, cls.sessions, cls.db = root, sessions, db
        patches = [
            (intake, "DATA_ROOT", root), (intake, "SESSIONS_ROOT", sessions), (intake, "DB_PATH", db),
            (server, "DATA_ROOT", root), (server, "SESSIONS_ROOT", sessions), (server, "DB_PATH", db),
            (fuse_screening_session, "DATA_ROOT", root), (fuse_screening_session, "DB_PATH", db),
            (capture_live_ppg, "DATA_ROOT", root),
            (register_session_ppg, "DATA_ROOT", root), (register_session_ppg, "DB_PATH", db),
            (register_session_vitals, "DATA_ROOT", root), (register_session_vitals, "DB_PATH", db),
            (evaluate_webcam_session, "SESSION_ROOT", sessions),
        ]
        cls.patchers = [mock.patch.object(module, name, value) for module, name, value in patches]
        for patcher in cls.patchers:
            patcher.start()

    @classmethod
    def tearDownClass(cls):
        for patcher in cls.patchers:
            patcher.stop()
        cls.tmp.cleanup()

    def new_session(self):
        return intake.create_session()["session_id"]


class IsolatedWorkflow(IsolatedDatasets):
    # ---------------------------------------------------------------- scenario 1

    def test_1_normal_patient_full_workflow_and_resume(self):
        sid = self.new_session()
        self.assertEqual(intake.intake_state(sid)["workflow_state"], "created")

        # Non-urgent symptom answers ("yes" to fatigue / breathlessness) must NOT stop screening.
        answers = {**COMMON_NO_SAFETY, "C01": "yes", "C02": "yes", "C03": "no", "C06": "not_sure",
                   "C08": "no", "C10": "no"}
        saved = intake.save_questionnaire(sid, questionnaire_body(answers))
        self.assertTrue(saved["status"]["image_acquisition_allowed"])
        self.assertFalse(saved["status"]["urgent_clinician_review"])
        self.assertEqual(intake.intake_state(sid)["workflow_state"], "images_in_progress")

        for modality, seed in (("conjunctiva", 1), ("conjunctiva", 2), ("nails", 3), ("tongue", 4)):
            counts = upload(sid, modality, seed)["captures"]
        self.assertEqual(counts, {"conjunctiva": 2, "nails": 1, "tongue": 1})
        self.assertEqual(intake.intake_state(sid)["workflow_state"], "ppg_in_progress")

        with self.assertRaises(HTTPException) as blocked:
            intake.record_ppg(sid, intake.PpgRecordIn(seconds=5))
        self.assertEqual(blocked.exception.status_code, 403)  # comfort check still pending

        comfort = intake.ppg_comfort_check(sid, intake.ComfortIn(
            answers={"P02": "no", "P03": "no", "P05": "no", "P06": "no", "P07": "yes"}))
        self.assertTrue(comfort["status"]["ppg_acquisition_allowed"])

        with mock.patch.object(capture_live_ppg.serial, "Serial", FakeEsp32):
            started = intake.record_ppg(sid, intake.PpgRecordIn(seconds=5))
            self.assertEqual(started["state"], "opening")
            with self.assertRaises(HTTPException) as busy:  # single owner of the serial port
                intake.record_ppg(sid, intake.PpgRecordIn(seconds=5))
            self.assertEqual(busy.exception.status_code, 409)
            job = wait_for_job()
        self.assertEqual(job["state"], "saved", job)
        result = job["result"]
        self.assertEqual(result["session_id"], sid)
        self.assertGreater(result["sample_count"], 80)
        self.assertTrue(result["quality_passed"], result["quality_reasons"])
        self.assertEqual(result["median_experimental_hr_bpm"], 72)  # device-reported, not estimated
        self.assertIsNone(result["median_temperature_c"])  # firmware sends null -> N/A
        self.assertFalse(result["hb_model_applied"])

        state = intake.intake_state(sid)
        self.assertEqual(state["workflow_state"], "ready_for_analysis")
        self.assertEqual(len(state["ppg_recordings"]), 1)
        self.assertEqual(state["ppg_recordings"][0]["recording_id"], result["recording_id"])

        report = intake.analyze(sid)
        self.assertEqual(report["outcome"], "screening")
        self.assertIn(report["screening_result"]["risk_level"], {"low", "moderate", "high", "insufficient_evidence"})
        self.assertFalse(report["screening_result"]["reliability_score_is_probability"])
        self.assertEqual(report["storage"]["saved_images"], {"conjunctiva": 2, "nails": 1, "tongue": 1})
        self.assertTrue(report["modalities"]["ppg"]["available"])
        for name in ("screening_report.json", "screening_result.json", "c2_payload.json"):
            self.assertTrue((self.sessions / sid / name).is_file(), name)

        # Resume: same session, nothing duplicated.
        resumed = intake.intake_state(sid)
        self.assertEqual(resumed["workflow_state"], "completed")
        self.assertEqual(resumed["captures"], {"conjunctiva": 2, "nails": 1, "tongue": 1})
        self.assertEqual(resumed["questionnaire"]["answers"]["C01"], "yes")
        self.assertEqual(len([s for s in server.sessions()["sessions"] if s["session_id"] == sid]), 1)

        # Retake keeps the original recording.
        with mock.patch.object(capture_live_ppg.serial, "Serial", FakeEsp32):
            intake.record_ppg(sid, intake.PpgRecordIn(seconds=5))
            retake = wait_for_job()
        self.assertEqual(retake["state"], "saved")
        ids = [r["recording_id"] for r in intake.intake_state(sid)["ppg_recordings"]]
        self.assertEqual(len(ids), 2)
        self.assertIn(result["recording_id"], ids)

    # ---------------------------------------------------------------- scenario 2

    def test_2_urgent_safety_answer_creates_referral_only_record(self):
        sid = self.new_session()
        answers = {**COMMON_NO_SAFETY, "SAF01": "yes", "C01": "yes"}  # current chest pain, partly answered
        with self.assertRaises(HTTPException) as routine:
            intake.save_questionnaire(sid, questionnaire_body(answers))
        self.assertEqual(routine.exception.status_code, 409)

        report = intake.save_referral(sid, intake.ReferralIn(
            profile=ADULT, consent=True, consent_ppg=True, consent_images=True, answers=answers))
        self.assertEqual(report["outcome"], "safety_referral")
        self.assertIsNone(report["screening_result"]["risk_level"])
        self.assertEqual(report["screening_result"]["decision_status"], "urgent_clinician_review_required")
        self.assertEqual(report["referral"]["urgent_response_ids"], ["SAF01"])
        responses = {r["question_id"]: r["answer"] for r in report["questionnaire"]["responses"]}
        self.assertEqual(responses["C01"], "yes")  # answers already given are preserved
        self.assertTrue((self.sessions / sid / "safety_referral.json").is_file())
        self.assertTrue((self.sessions / sid / "screening_report.json").is_file())
        self.assertFalse((self.sessions / sid / "c2_payload.json").exists())
        self.assertEqual(intake.intake_state(sid)["workflow_state"], "safety_referral")

        for blocked_call in (
            lambda: upload(sid, "nails"),
            lambda: intake.ppg_comfort_check(sid, intake.ComfortIn(answers={"P02": "no"})),
            lambda: intake.record_ppg(sid, intake.PpgRecordIn(seconds=5)),
            lambda: intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY)),
            lambda: server.component2_payload(sid),
        ):
            with self.assertRaises(HTTPException) as exc:
                blocked_call()
            self.assertIn(exc.exception.status_code, (403, 409))

        again = intake.analyze(sid)  # never runs models / fusion for a referral
        self.assertEqual(again["outcome"], "safety_referral")
        self.assertIsNone(again["screening_result"]["risk_level"])
        self.assertFalse((self.sessions / sid / "fusion_report.json").exists())

    def test_2b_unresolved_safety_answer_needs_clarification_or_referral(self):
        sid = self.new_session()
        answers = {**COMMON_NO_SAFETY, "SAF03": "not_sure"}
        with self.assertRaises(HTTPException):
            intake.save_questionnaire(sid, questionnaire_body(answers))
        report = intake.save_referral(sid, intake.ReferralIn(profile=ADULT, consent=True, answers=answers))
        self.assertEqual(report["referral"]["unresolved_safety_ids"], ["SAF03"])
        self.assertEqual(report["referral"]["urgent_response_ids"], [])

    def test_2d_unanswered_safety_questions_are_not_asked_not_unresolved(self):
        sid = self.new_session()
        report = intake.save_referral(sid, intake.ReferralIn(profile=ADULT, consent=True, answers={"SAF01": "yes"}))
        self.assertEqual(report["referral"]["urgent_response_ids"], ["SAF01"])
        self.assertEqual(report["referral"]["unresolved_safety_ids"], [])
        self.assertEqual(report["referral"]["not_asked_safety_ids"], ["SAF02", "SAF03", "SAF04"])

    def test_2e_blank_safety_answers_alone_do_not_justify_referral(self):
        sid = self.new_session()
        with self.assertRaises(HTTPException) as exc:
            intake.save_referral(sid, intake.ReferralIn(profile=ADULT, consent=True, answers={"C01": "yes"}))
        self.assertEqual(exc.exception.status_code, 422)

    def test_2c_referral_refused_without_a_safety_concern(self):
        sid = self.new_session()
        with self.assertRaises(HTTPException) as exc:
            intake.save_referral(sid, intake.ReferralIn(profile=ADULT, consent=True, answers=COMMON_NO_SAFETY))
        self.assertEqual(exc.exception.status_code, 422)

    # ---------------------------------------------------------------- scenario 3

    def test_3_missing_modalities_give_insufficient_evidence(self):
        sid = self.new_session()
        answers = {**COMMON_NO_SAFETY, "C01": "yes", "C02": "yes", "C03": "yes", "C06": "yes"}
        intake.save_questionnaire(sid, questionnaire_body(answers, consent_ppg=False, consent_images=False))
        report = intake.analyze(sid)
        self.assertEqual(report["screening_result"]["risk_level"], "insufficient_evidence")
        self.assertEqual(report["storage"]["saved_images"], {"conjunctiva": 0, "nails": 0, "tongue": 0})
        self.assertFalse(report["modalities"]["ppg"]["available"])
        self.assertIn("ppg", report["missing_inputs"])
        reasons = " ".join(report["fusion"]["reliability_aware_fusion"]["insufficient_reasons"])
        self.assertIn("physiological", reasons)

    # ---------------------------------------------------------------- scenario 4

    def test_4_port_missing_or_busy_reports_accurate_state(self):
        sid = self.new_session()
        intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY))
        intake.ppg_comfort_check(sid, intake.ComfortIn(
            answers={"P02": "no", "P03": "no", "P05": "no", "P06": "no", "P07": "yes"}))
        cases = {
            "port_not_found": "could not open port 'COM11': FileNotFoundError(2, 'The system cannot find the file specified.')",
            "port_busy": "could not open port 'COM11': PermissionError(13, 'Access is denied.', None, 5)",
        }
        for kind, text in cases.items():
            with mock.patch.object(capture_live_ppg.serial, "Serial", failing_serial(text)):
                intake.record_ppg(sid, intake.PpgRecordIn(seconds=5))
                job = wait_for_job()
            self.assertEqual(job["state"], "failed")
            self.assertEqual(job["error_kind"], kind)
            self.assertEqual(job["samples"], 0)
        self.assertEqual(intake.intake_state(sid)["ppg_recordings"], [])
        report = intake.analyze(sid)  # incomplete-modality screening is still allowed
        self.assertFalse(report["modalities"]["ppg"]["available"])

    def test_4b_cancel_saves_nothing(self):
        sid = self.new_session()
        intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY))
        intake.ppg_comfort_check(sid, intake.ComfortIn(
            answers={"P02": "no", "P03": "no", "P05": "no", "P06": "no", "P07": "yes"}))
        with mock.patch.object(capture_live_ppg.serial, "Serial", FakeEsp32):
            intake.record_ppg(sid, intake.PpgRecordIn(seconds=30))
            time.sleep(3.0)
            self.assertTrue(intake.cancel_ppg_job()["cancel_requested"])
            job = wait_for_job()
        self.assertEqual(job["state"], "cancelled")
        self.assertEqual(intake.intake_state(sid)["ppg_recordings"], [])
        self.assertFalse(any((self.sessions / sid / "ppg").glob("*.csv")) if (self.sessions / sid / "ppg").exists() else False)


class ImageDeleteAndRetake(IsolatedDatasets):
    """PP1 delete/retake of individual webcam images, in the same isolated temporary datasets folder."""

    def session_with_images(self):
        sid = self.new_session()
        intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY))
        ids = [upload(sid, m, seed)["image_id"] for m, seed in
               (("tongue", 11), ("tongue", 12), ("conjunctiva", 13), ("nails", 14))]
        return sid, ids

    def manifest(self, sid):
        return json.loads((self.sessions / sid / "manifest.json").read_text(encoding="utf-8"))

    def test_delete_one_image_only(self):
        sid, (tongue_a, tongue_b, conj, nail) = self.session_with_images()
        result = intake.delete_image(sid, tongue_a)
        self.assertEqual(result["captures"], {"conjunctiva": 1, "nails": 1, "tongue": 1})
        self.assertEqual({i["image_id"] for i in result["images"]}, {tongue_b, conj, nail})
        m = self.manifest(sid)
        self.assertEqual(len(m["captures"]), 3)
        self.assertEqual(m["removed_captures"][0]["reason"], "removed_by_operator")
        self.assertFalse((self.sessions / sid / "images" / "tongue" / tongue_a).exists())
        self.assertTrue((self.sessions / sid / "images" / "_removed" / tongue_a).is_file())  # audit copy kept
        self.assertEqual(intake.list_images(sid)["images"], result["images"])  # gallery == manifest
        self.assertEqual(intake.intake_state(sid)["questionnaire"]["answers"]["SAF01"], "no")  # answers untouched
        with self.assertRaises(HTTPException) as again:
            intake.delete_image(sid, tongue_a)
        self.assertEqual(again.exception.status_code, 404)

    def test_retake_replaces_only_after_successful_save(self):
        sid, (tongue_a, *_rest) = self.session_with_images()
        new = upload(sid, "tongue", 21, replaces=tongue_a)
        self.assertEqual(new["captures"]["tongue"], 2)
        ids = {i["image_id"] for i in new["images"]}
        self.assertNotIn(tongue_a, ids)
        self.assertIn(new["image_id"], ids)
        removed = self.manifest(sid)["removed_captures"][0]
        self.assertEqual((removed["reason"], removed["replaced_by"]), ("replaced_by_retake", new["image_id"]))

    def test_retake_can_correct_the_category(self):
        sid, (tongue_a, *_rest) = self.session_with_images()
        new = upload(sid, "nails", 22, replaces=tongue_a)  # wrong-category photo re-saved as a nail image
        self.assertEqual(new["captures"], {"conjunctiva": 1, "nails": 2, "tongue": 1})

    def test_failed_replacement_keeps_original(self):
        sid, (tongue_a, *_rest) = self.session_with_images()
        before = self.manifest(sid)
        with self.assertRaises(HTTPException) as bad:
            upload(sid, "tongue", replaces=tongue_a, data=b"not an image")
        self.assertEqual(bad.exception.status_code, 422)
        self.assertEqual(self.manifest(sid), before)
        self.assertTrue((self.sessions / sid / "images" / "tongue" / tongue_a).is_file())
        with mock.patch.object(intake, "_write_manifest", side_effect=OSError("disk full")):
            with self.assertRaises(HTTPException) as io_error:
                upload(sid, "tongue", 23, replaces=tongue_a)
        self.assertEqual(io_error.exception.status_code, 500)
        self.assertEqual(self.manifest(sid), before)
        self.assertTrue((self.sessions / sid / "images" / "tongue" / tongue_a).is_file())
        self.assertEqual(len(list((self.sessions / sid / "images" / "tongue").glob("*.png"))), 2)
        with self.assertRaises(HTTPException) as unknown:
            upload(sid, "tongue", 24, replaces="tongue_20990101T000000_000000Z.png")
        self.assertEqual(unknown.exception.status_code, 404)
        self.assertEqual(self.manifest(sid), before)

    def test_ids_are_validated_and_sessions_isolated(self):
        sid_a, (tongue_a, *_rest) = self.session_with_images()
        sid_b, _ = self.session_with_images()
        for bad in ("../manifest.json", "..\\manifest.json", "tongue_x.jpg", "manifest.json"):
            with self.assertRaises(HTTPException) as exc:
                intake.delete_image(sid_a, bad)
            self.assertEqual(exc.exception.status_code, 400)
        with self.assertRaises(HTTPException) as other:
            intake.delete_image(sid_b, tongue_a)  # an image ID from another session
        self.assertEqual(other.exception.status_code, 404)
        self.assertEqual(len(self.manifest(sid_a)["captures"]), 4)

    def test_change_after_analysis_marks_results_outdated(self):
        sid, (tongue_a, *_rest) = self.session_with_images()
        report = intake.analyze(sid)
        self.assertFalse(report["analysis_outdated"])
        intake.delete_image(sid, tongue_a)
        stale = server.session_report(sid)
        self.assertTrue(stale["analysis_outdated"])
        self.assertNotEqual(intake.intake_state(sid)["workflow_state"], "completed")
        self.assertTrue([s for s in server.sessions()["sessions"] if s["session_id"] == sid][0]["analysis_outdated"])
        fresh = intake.analyze(sid)
        self.assertFalse(fresh["analysis_outdated"])
        self.assertEqual(fresh["storage"]["saved_images"], {"conjunctiva": 1, "nails": 1, "tongue": 1})

    def test_rerun_fusion_after_image_change_reruns_image_models(self):
        sid, (tongue_a, *_rest) = self.session_with_images()
        intake.analyze(sid)
        intake.delete_image(sid, tongue_a)
        report = server.refresh_session(sid)  # "Re-run fusion" on Screening Records
        self.assertFalse(report["analysis_outdated"])
        results = json.loads((self.sessions / sid / "image_model_results.json").read_text(encoding="utf-8"))
        self.assertNotIn(tongue_a, " ".join(r["image_path"] for r in results["images"]))  # removed photo not used
        self.assertEqual(report["modalities"]["images"]["image_count"], 3)

    def test_removing_every_image_drops_old_image_results_from_fusion(self):
        sid, ids = self.session_with_images()
        intake.analyze(sid)
        for image_id in ids:
            intake.delete_image(sid, image_id)
        report = intake.analyze(sid)
        self.assertEqual(report["storage"]["saved_images"], {"conjunctiva": 0, "nails": 0, "tongue": 0})
        self.assertEqual(report["modalities"]["images"].get("image_count", 0), 0)
        self.assertFalse((self.sessions / sid / "image_model_results.json").exists())
        self.assertTrue(any((self.sessions / sid / "_superseded").glob("*image_model_results.json")))


class ProfileValidation(IsolatedDatasets):
    """Patient profile checks on new submissions; saved profiles and the screening rules are unchanged."""

    def rejected(self, call, text):
        with self.assertRaises(HTTPException) as ctx:
            call()
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn(text, str(ctx.exception.detail))

    def save(self, profile, answers=COMMON_NO_SAFETY, **overrides):
        sid = self.new_session()
        return sid, intake.save_questionnaire(sid, questionnaire_body(answers, profile=profile, **overrides))

    def threshold_after_analysis(self, sid):
        intake.analyze(sid)
        fusion = json.loads((self.sessions / sid / "fusion_report.json").read_text(encoding="utf-8"))
        return fusion["screening"]["hb_threshold_g_dl"]

    def test_valid_15_year_old_female_reaches_unchanged_who_cutoff(self):
        profile = {"age_months": 180, "sex": "female", "pregnancy_status": "not_pregnant"}
        self.assertTrue(intake.questionnaire_followups(intake.FollowupsIn(profile=profile, answers=COMMON_NO_SAFETY)))
        sid, saved = self.save(profile, guardian_permission=True)
        self.assertTrue(saved["status"]["image_acquisition_allowed"])
        self.assertEqual(self.threshold_after_analysis(sid), 12.0)  # existing WHO rule, women >= 15 years

    def test_pandu_type_sign_questions_are_offered_and_saved(self):
        profile = {"age_months": 300, "sex": "female", "pregnancy_status": "not_pregnant"}
        followups = intake.questionnaire_followups(intake.FollowupsIn(profile=profile, answers=COMMON_NO_SAFETY))["followups"]
        signs = [q["id"] for q in followups if q["section"] == "pandu_type_signs"]
        self.assertEqual(signs, [f"PT{n:02d}" for n in range(1, 15)])
        _, saved = self.save(profile, answers={**COMMON_NO_SAFETY, "PT04": "yes", "PT11": "no"})
        self.assertGreater(saved["answers_saved"], 0)

    def test_valid_adult_male(self):
        sid, saved = self.save({"age_months": 360, "sex": "male", "pregnancy_status": "not_applicable"})
        self.assertTrue(saved["status"]["image_acquisition_allowed"])
        self.assertEqual(self.threshold_after_analysis(sid), 13.0)  # existing WHO rule, men >= 15 years

    def test_missing_sex_rejected_from_age_15_without_substitution(self):
        for profile in ({"age_months": 300, "sex": "not_recorded", "pregnancy_status": "not_applicable"},
                        {"age_months": 180, "pregnancy_status": "not_applicable"}):  # omitted -> not_recorded
            sid = self.new_session()
            self.rejected(lambda: intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY, profile=profile)),
                          "aged 15 or older")
            self.rejected(lambda: intake.questionnaire_followups(intake.FollowupsIn(profile=profile)), "aged 15 or older")
            self.assertIsNone(intake.intake_state(sid)["questionnaire"])  # nothing saved, nothing invented

    def test_explicit_non_binary_answers_accepted_without_cutoff(self):
        for sex in ("intersex", "prefer_not_to_answer"):
            sid, saved = self.save({"age_months": 300, "sex": sex, "pregnancy_status": "not_applicable"})
            self.assertGreater(saved["answers_saved"], 0)
            self.assertIsNone(self.threshold_after_analysis(sid))  # existing rule: no adult cut-off, unchanged

    def test_unsupported_sex_value_rejected(self):
        sid = self.new_session()
        profile = {"age_months": 300, "sex": "F", "pregnancy_status": "not_pregnant"}
        self.rejected(lambda: intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY, profile=profile)),
                      "Unsupported sex value")
        self.assertIsNone(intake.intake_state(sid)["questionnaire"])

    def test_invalid_pregnancy_status_rejected(self):
        sid = self.new_session()
        profile = {"age_months": 300, "sex": "female", "pregnancy_status": "maybe"}
        self.rejected(lambda: intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY, profile=profile)),
                      "Unsupported pregnancy status")
        self.assertIsNone(intake.intake_state(sid)["questionnaire"])

    def test_male_and_pregnant_rejected_everywhere(self):
        sid = self.new_session()
        profile = {"age_months": 300, "sex": "male", "pregnancy_status": "pregnant"}
        self.rejected(lambda: intake.save_questionnaire(sid, questionnaire_body(COMMON_NO_SAFETY, profile=profile)),
                      "cannot be combined")
        self.rejected(lambda: intake.questionnaire_followups(intake.FollowupsIn(profile=profile)), "cannot be combined")
        self.rejected(lambda: intake.save_referral(sid, intake.ReferralIn(
            profile=profile, consent=True, answers={**COMMON_NO_SAFETY, "SAF01": "yes"})), "cannot be combined")
        self.assertIsNone(intake.intake_state(sid)["questionnaire"])

    def test_under_15_follows_existing_rules(self):
        # Under 15 the WHO child cut-offs do not use sex, so "not recorded" stays allowed.
        sid, _ = self.save({"age_months": 168, "sex": "not_recorded", "pregnancy_status": "not_applicable"},
                           guardian_permission=True)
        self.assertEqual(self.threshold_after_analysis(sid), 12.0)  # WHO children 12-14 years
        # Questionnaire spec: the pregnancy branch is independent of age (clinician handles special situations).
        profile = {"age_months": 168, "sex": "female", "pregnancy_status": "pregnant"}
        sid, saved = self.save(profile, answers={**COMMON_NO_SAFETY, "PR06": "no"}, guardian_permission=True)
        self.assertTrue(saved["status"]["image_acquisition_allowed"])
        self.assertEqual(intake.intake_state(sid)["questionnaire"]["profile"]["pregnancy_status"], "pregnant")
        # Guardian rule is unchanged.
        self.rejected(lambda: self.save(profile, answers={**COMMON_NO_SAFETY, "PR06": "no"}), "Guardian permission")

    def test_safety_referral_not_blocked_by_missing_sex(self):
        sid = self.new_session()
        profile = {"age_months": 300, "sex": "not_recorded", "pregnancy_status": "not_applicable"}
        report = intake.save_referral(sid, intake.ReferralIn(
            profile=profile, consent=True, answers={**COMMON_NO_SAFETY, "SAF01": "yes"}))
        self.assertEqual(report["outcome"], "safety_referral")

    def test_previously_saved_profile_still_loads_and_screens(self):
        # A profile saved before this validation (the Streamlit assistant allowed an adult "not_recorded").
        sid = self.new_session()
        q = intake.questionnaire
        legacy = q.profile_for(300, "not_recorded", "not_applicable")
        final = q.finalize_answers(300, True, True, True, dict(COMMON_NO_SAFETY), "", "", "", True, True)
        q.save_demo(sid, legacy, final, self.root)
        state = intake.intake_state(sid)
        self.assertEqual(state["questionnaire"]["profile"]["sex_reported_for_demo"], "not_recorded")
        self.assertEqual(state["workflow_state"], "images_in_progress")
        self.assertEqual(upload(sid, "nails", 7)["captures"]["nails"], 1)  # saved consent still honoured
        self.assertIsNone(self.threshold_after_analysis(sid))  # unchanged behaviour, no value invented
        self.assertEqual(server.session_report(sid)["outcome"], "screening")


class RealBaselineReadOnly(unittest.TestCase):
    """Scenario 5: the real reference session is only READ (GET routes); compare with its saved record."""

    def test_5_existing_session_unchanged_and_compatible(self):
        sid = "demo_e37082b4"
        folder = REAL_DATA_ROOT / "live_sessions" / sid
        if not folder.is_dir():
            self.skipTest("reference session not present on this machine")
        before = {p.name: p.stat().st_mtime_ns for p in folder.iterdir() if p.is_file()}
        report = server.session_report(sid)
        saved = json.loads((folder / "screening_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["screening_result"]["risk_level"], "moderate")
        self.assertEqual(report["screening_result"]["risk_level"], saved["screening_result"]["risk_level"])
        self.assertEqual(report["screening_result"]["reliability_score"], 0.656)
        self.assertEqual(report["storage"]["saved_images"], {"conjunctiva": 2, "nails": 2, "tongue": 1})
        self.assertEqual(report["modalities"]["ppg"]["sample_count"], 500)
        self.assertEqual(set(server._screening_result(report)), set(json.loads(
            (folder / "screening_result.json").read_text(encoding="utf-8"))))
        self.assertEqual(set(json.loads(server.component2_payload(sid).body)), set(json.loads(
            (folder / "c2_payload.json").read_text(encoding="utf-8"))))
        after = {p.name: p.stat().st_mtime_ns for p in folder.iterdir() if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
