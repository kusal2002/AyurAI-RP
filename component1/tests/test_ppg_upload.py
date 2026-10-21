"""Browser (Web Serial) PPG upload and the C1_SERIAL_ENABLED / C1_PPG_UPLOAD_ENABLED switches.

Runs in the ISOLATED temporary datasets folder from test_intake_workflow; recordings are synthetic
(firmware format, about 25 rows/s with a pulse), never hardware or patient results.

Run from repository root:
    python -m unittest component1.tests.test_ppg_upload -v
"""

import csv
import io
import math
import unittest
import uuid
from unittest import mock

from fastapi import HTTPException

from component1.api import intake
from component1.tests.test_intake_workflow import COMMON_NO_SAFETY, IsolatedDatasets, questionnaire_body

COMFORT_OK = {"P02": "no", "P03": "no", "P05": "no", "P06": "no", "P07": "yes"}


def recording(seconds=20, rate=25.0, red=100000, ir=120000):
    """Synthetic recording in capture_live_ppg's CSV format (same columns the browser uploads)."""
    samples = io.StringIO()
    writer = csv.writer(samples)
    writer.writerow(intake.PPG_SAMPLE_COLUMNS)
    for n in range(int(seconds * rate)):
        t = n / rate
        pulse = math.sin(2 * math.pi * 1.2 * t)
        writer.writerow([round(t + 0.03, 6), 14000 + int(t * 1000), int(red * (1 + 0.004 * pulse)),
                         int(ir * (1 + 0.004 * pulse))])
    metrics = io.StringIO()
    writer = csv.writer(metrics)
    writer.writerow(intake.PPG_METRIC_COLUMNS)
    for second in range(seconds):
        writer.writerow([15000 + second * 1000, 72 if second > 3 else None, 98 if second > 3 else None, None, 1])
    return samples.getvalue(), metrics.getvalue()


def body(seconds=20, samples=None, metrics=None, upload_id=None):
    default_samples, default_metrics = recording(seconds)
    return intake.PpgUploadIn(upload_id=upload_id or uuid.uuid4().hex, seconds=seconds,
                              samples_csv=default_samples if samples is None else samples,
                              metrics_csv=default_metrics if metrics is None else metrics)


class BrowserPpgUpload(IsolatedDatasets):
    def setUp(self):
        patcher = mock.patch.object(intake, "PPG_UPLOAD_ENABLED", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cleared_session(self, **overrides):
        sid = self.new_session()
        intake.save_questionnaire(sid, questionnaire_body(dict(COMMON_NO_SAFETY), **overrides))
        intake.ppg_comfort_check(sid, intake.ComfortIn(answers=COMFORT_OK))
        return sid

    def refused(self, call, status, text=""):
        with self.assertRaises(HTTPException) as ctx:
            call()
        self.assertEqual(ctx.exception.status_code, status)
        self.assertIn(text, str(ctx.exception.detail))

    def test_disabled_by_default(self):
        with mock.patch.object(intake, "PPG_UPLOAD_ENABLED", False):
            self.refused(lambda: intake.upload_ppg(self.cleared_session(), body()), 503, "not enabled")

    def test_upload_is_processed_like_a_usb_recording_and_used_in_analysis(self):
        sid = self.cleared_session(consent_images=False)  # PPG is then the last step before analysis
        result = intake.upload_ppg(sid, body())
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["sample_count"], 500)
        self.assertTrue(result["quality_passed"], result["quality_reasons"])
        self.assertEqual(result["median_experimental_hr_bpm"], 72)  # device-reported metrics stored
        self.assertFalse(result["hb_model_applied"])
        ppg = self.sessions / sid / "ppg"
        stem = result["recording_file"][: -len(".csv")]
        for name in (f"{stem}.csv", f"{stem}_quality.json", stem.replace("ppg_red_ir_", "ppg_metrics_") + ".csv",
                     stem.replace("ppg_red_ir_", "ppg_waveform_") + ".png"):
            self.assertTrue((ppg / name).is_file(), name)
        header = (ppg / f"{stem}.csv").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(header, ",".join(intake.PPG_SAMPLE_COLUMNS))  # same file format as the USB recorder
        state = intake.intake_state(sid)
        self.assertEqual([r["recording_id"] for r in state["ppg_recordings"]], [result["recording_id"]])
        self.assertEqual(state["workflow_state"], "ready_for_analysis")
        report = intake.analyze(sid)
        self.assertTrue(report["modalities"]["ppg"]["available"])
        self.assertEqual(report["modalities"]["ppg"]["recording_id"], result["recording_id"])

    def test_retry_with_same_upload_id_does_not_duplicate(self):
        sid = self.cleared_session()
        first = body()
        saved = intake.upload_ppg(sid, first)
        again = intake.upload_ppg(sid, first)
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["recording_id"], saved["recording_id"])
        self.assertEqual(len(intake.intake_state(sid)["ppg_recordings"]), 1)
        self.assertEqual(len(list((self.sessions / sid / "ppg").glob("ppg_red_ir_*.csv"))), 1)

    def test_consent_comfort_and_referral_rules_apply(self):
        sid = self.new_session()
        intake.save_questionnaire(sid, questionnaire_body(dict(COMMON_NO_SAFETY)))
        self.refused(lambda: intake.upload_ppg(sid, body()), 403, "finger-comfort")
        intake.ppg_comfort_check(sid, intake.ComfortIn(answers={**COMFORT_OK, "P06": "yes"}))  # discomfort
        self.refused(lambda: intake.upload_ppg(sid, body()), 403, "not permitted")

        no_consent = self.new_session()
        intake.save_questionnaire(no_consent, questionnaire_body(dict(COMMON_NO_SAFETY), consent_ppg=False))
        self.refused(lambda: intake.upload_ppg(no_consent, body()), 403)

        referral = self.new_session()
        intake.save_referral(referral, intake.ReferralIn(
            profile={"age_months": 300, "sex": "female", "pregnancy_status": "not_pregnant"},
            consent=True, answers={**COMMON_NO_SAFETY, "SAF01": "yes"}))
        self.refused(lambda: intake.upload_ppg(referral, body()), 409, "Safety-referral")
        self.refused(lambda: intake.upload_ppg("demo_00000000", body()), 404)
        self.refused(lambda: intake.upload_ppg("../../etc", body()), 400)

    def test_invalid_recordings_are_rejected_and_nothing_is_saved(self):
        sid = self.cleared_session()
        samples, metrics = recording()
        cases = {
            "wrong header": samples.replace("host_elapsed_s", "elapsed", 1),
            "not numbers": samples.replace("\n0.03,", "\nabc,", 1),
            "out of range": samples.replace(",100000,", ",999999,", 1),
            "too short": recording(seconds=8)[0],
            "time backwards": samples.replace("\n0.07,", "\n0.01,", 1),
            "too few rows": "\r\n".join(samples.splitlines()[:20]) + "\r\n",
            "wrong column count": samples.replace(",120000\r\n", ",120000,1\r\n", 1),
        }
        for label, bad in cases.items():
            with self.subTest(label):
                self.refused(lambda bad=bad: intake.upload_ppg(sid, body(samples=bad)), 422)
        self.refused(lambda: intake.upload_ppg(sid, body(metrics=metrics.replace(",1\r\n", ",7\r\n", 1))), 422)
        self.refused(lambda: intake.upload_ppg(sid, body(metrics="time_ms,hr\r\n1,2\r\n")), 422)
        with self.assertRaises(ValueError):  # size limit enforced by the request model
            body(samples="x" * (intake.MAX_PPG_SAMPLES_CSV + 1))
        with self.assertRaises(ValueError):
            body(upload_id="not-a-uuid")
        self.assertEqual(intake.intake_state(sid)["ppg_recordings"], [])
        self.assertFalse(any((self.sessions / sid / "ppg").glob("*")) if (self.sessions / sid / "ppg").exists() else False)

    def test_metrics_are_optional(self):
        sid = self.cleared_session()
        result = intake.upload_ppg(sid, body(metrics=""))
        self.assertEqual(result["metrics_count"], 0)
        self.assertIsNone(result["median_experimental_hr_bpm"])


class CaptureSwitches(IsolatedDatasets):
    def test_capture_options_report_both_switches(self):
        options = intake.ppg_capture_options()
        self.assertEqual((options["server_serial_enabled"], options["browser_upload_enabled"]), (True, False))
        self.assertEqual((options["min_seconds"], options["max_seconds"], options["baud"]), (5, 60, 115200))

    def test_server_serial_can_be_disabled_with_a_clear_message(self):
        with mock.patch.object(intake, "SERIAL_ENABLED", False):
            state = intake.ppg_job()
            self.assertFalse(state["serial_enabled"])
            self.assertEqual(state["ports"], [])
            with self.assertRaises(HTTPException) as ctx:
                intake.probe_ppg()
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("does not record from a USB sensor", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
