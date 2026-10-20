"""Source registry, acquisition and ingestion report. No network access."""

import csv
import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

from app.config import IngestionSettings
from app.knowledge_ingestion.cli import main
from app.knowledge_ingestion.registry import (
    REGISTRY_COLUMNS,
    acquire,
    file_checksum,
    load_registry,
    plan_acquisition,
    validate_registry,
)
from app.knowledge_ingestion.report import build_ingestion_report
from app.knowledge_ingestion.service import build_manifest
from ingestion_test_support import SYNTHETIC_TEI_BODY, make_tei


REAL_REGISTRY = Path(__file__).parent / "corpus" / "source_registry.csv"


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, status: int = 200):
        super().__init__(data)
        self.status = status


class FakeOpener:
    """Serves fixed bytes per URL and records the requests it saw."""

    def __init__(self, payloads: dict[str, bytes], fail: set[str] = frozenset()):
        self.payloads = payloads
        self.fail = fail
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        url = request.full_url
        if url in self.fail:
            raise urllib.error.URLError("simulated outage")
        data = self.payloads[url]
        header = request.get_header("Range")
        if header:
            start = int(header.split("=")[1].rstrip("-"))
            return FakeResponse(data[start:], status=206)
        return FakeResponse(data)


def _row(**values) -> dict:
    row = {column: "" for column in REGISTRY_COLUMNS}
    row.update(
        registry_id="T-1", status="candidate", decision="include",
        source_id="test-source", title="Test source", licence="CC BY 4.0",
        licence_evidence="test fixture", evidence_category="traditional_text",
        download_url="https://example.org/test.xml",
        local_relative_path="open/test.xml",
    )
    row.update(values)
    return row


def _write_registry(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


# --- the committed registry ------------------------------------------------

def test_committed_registry_is_valid():
    entries = load_registry(REAL_REGISTRY)
    assert validate_registry(entries) == []
    # Every included candidate names a licence and where it was read.
    for entry in entries:
        if entry.decision == "include" and entry.status == "candidate":
            assert entry.licence and entry.licence_evidence, entry.registry_id


def test_committed_registry_never_includes_unverified_rights():
    entries = load_registry(REAL_REGISTRY)
    included = [e for e in entries if e.decision in {"include", "include_reference_only"}]
    assert included
    for entry in included:
        assert "unknown" not in entry.licence.lower(), entry.registry_id
        assert "uploader-asserted" not in entry.licence.lower(), entry.registry_id


# --- validation ------------------------------------------------------------

@pytest.mark.parametrize(
    "override, message",
    [
        ({"decision": "maybe"}, "unknown decision"),
        ({"download_url": "http://example.org/x"}, "https"),
        ({"local_relative_path": "../escape.xml"}, "inside the corpus"),
        ({"local_relative_path": "C:/abs.xml"}, "inside the corpus"),
        ({"licence": ""}, "without a recorded licence"),
        ({"licence": "unknown"}, "without a recorded licence"),
        ({"evidence_category": "clinical_fact"}, "evidence_category"),
        ({"source_id": "bad id!"}, "invalid characters"),
        ({"decision": "exclude", "decision_reason": ""}, "decision_reason"),
    ],
)
def test_validation_rejects_unsafe_rows(tmp_path, override, message):
    path = _write_registry(tmp_path / "r.csv", [_row(**override)])
    problems = validate_registry(load_registry(path))
    assert any(message in problem for problem in problems), problems


def test_validation_rejects_duplicate_ids_and_paths(tmp_path):
    path = _write_registry(tmp_path / "r.csv", [_row(), _row(source_id="other")])
    problems = validate_registry(load_registry(path))
    assert any("duplicate registry_id" in p for p in problems)
    assert any("local_relative_path also used" in p for p in problems)


def test_missing_columns_are_rejected(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("registry_id,title\nX,Y\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_registry(path)


# --- acquisition -----------------------------------------------------------

def test_dry_run_never_touches_network(tmp_path):
    data = b"<TEI/>"
    entries = load_registry(_write_registry(
        tmp_path / "r.csv", [_row(checksum_type="md5", checksum=_md5(data))]))
    opener = FakeOpener({})
    report = acquire(entries, tmp_path / "raw", opener=opener)
    assert opener.requests == []
    assert [item.state for item in report.items] == ["missing"]
    assert not (tmp_path / "raw").exists()


def test_apply_downloads_verifies_and_writes_sidecar(tmp_path):
    data = b"payload bytes"
    entries = load_registry(_write_registry(
        tmp_path / "r.csv",
        [_row(checksum_type="md5", checksum=_md5(data), source_language="sa",
              publication_year="1890", redistribution_permitted="yes")],
    ))
    opener = FakeOpener({"https://example.org/test.xml": data})
    report = acquire(entries, tmp_path / "raw", apply=True, opener=opener, pause_seconds=0)

    target = tmp_path / "raw" / "open" / "test.xml"
    assert report.downloaded == ["T-1"] and report.errors == {}
    assert target.read_bytes() == data
    assert "AyurAI" in opener.requests[0].get_header("User-agent")
    sidecar = json.loads((tmp_path / "raw" / "open" / "test.xml.meta.json").read_text(encoding="utf-8"))
    assert sidecar["source_id"] == "test-source"
    assert sidecar["publication_year"] == 1890
    assert sidecar["evidence_category"] == "traditional_text"
    assert "Licence: CC BY 4.0" in sidecar["usage_notes"]

    # Idempotent: a second run verifies and downloads nothing.
    again = acquire(entries, tmp_path / "raw", apply=True, opener=opener, pause_seconds=0)
    assert again.downloaded == [] and again.items[0].state == "present_verified"
    assert len(opener.requests) == 1


def test_checksum_mismatch_keeps_part_file_and_does_not_install(tmp_path):
    entries = load_registry(_write_registry(
        tmp_path / "r.csv", [_row(checksum_type="md5", checksum="0" * 32)]))
    opener = FakeOpener({"https://example.org/test.xml": b"tampered"})
    report = acquire(entries, tmp_path / "raw", apply=True, opener=opener, pause_seconds=0)
    assert "mismatch" in report.errors["T-1"]
    assert not (tmp_path / "raw" / "open" / "test.xml").exists()
    assert (tmp_path / "raw" / "open" / "test.xml.part").exists()


def test_interrupted_download_resumes_with_range(tmp_path):
    data = b"0123456789abcdef"
    entries = load_registry(_write_registry(
        tmp_path / "r.csv", [_row(checksum_type="md5", checksum=_md5(data))]))
    part = tmp_path / "raw" / "open" / "test.xml.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(data[:6])
    assert plan_acquisition(entries, tmp_path / "raw")[0].state == "partial"

    opener = FakeOpener({"https://example.org/test.xml": data})
    report = acquire(entries, tmp_path / "raw", apply=True, opener=opener, pause_seconds=0)
    assert report.errors == {}
    assert opener.requests[0].get_header("Range") == "bytes=6-"
    assert (tmp_path / "raw" / "open" / "test.xml").read_bytes() == data


def test_existing_different_file_is_a_conflict_not_overwritten(tmp_path):
    entries = load_registry(_write_registry(
        tmp_path / "r.csv", [_row(checksum_type="md5", checksum=_md5(b"expected"))]))
    target = tmp_path / "raw" / "open" / "test.xml"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"curated local copy")
    opener = FakeOpener({"https://example.org/test.xml": b"expected"})
    report = acquire(entries, tmp_path / "raw", apply=True, opener=opener, pause_seconds=0)
    assert report.items[0].state == "conflict"
    assert opener.requests == []
    assert target.read_bytes() == b"curated local copy"


def test_existing_sidecar_is_never_replaced(tmp_path):
    data = b"x"
    entries = load_registry(_write_registry(
        tmp_path / "r.csv", [_row(checksum_type="md5", checksum=_md5(data))]))
    sidecar = tmp_path / "raw" / "open" / "test.xml.meta.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text('{"title": "curated"}', encoding="utf-8")
    acquire(entries, tmp_path / "raw", apply=True,
            opener=FakeOpener({"https://example.org/test.xml": data}), pause_seconds=0)
    assert sidecar.read_text(encoding="utf-8") == '{"title": "curated"}'


def test_network_failure_is_reported_and_resumable(tmp_path):
    entries = load_registry(_write_registry(tmp_path / "r.csv", [_row()]))
    opener = FakeOpener({}, fail={"https://example.org/test.xml"})
    report = acquire(entries, tmp_path / "raw", apply=True, opener=opener, pause_seconds=0)
    assert "download failed" in report.errors["T-1"]


def test_unchecksummed_download_reports_sha256_for_recording(tmp_path):
    data = b"no checksum known"
    entries = load_registry(_write_registry(tmp_path / "r.csv", [_row()]))
    report = acquire(entries, tmp_path / "raw", apply=True,
                     opener=FakeOpener({"https://example.org/test.xml": data}), pause_seconds=0)
    assert report.recorded_checksums["T-1"] == hashlib.sha256(data).hexdigest()
    assert report.items[0].state == "present_unverified"


def test_git_blob_checksum_matches_git(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"hello\n")
    # `git hash-object` of "hello\n"
    assert file_checksum(path, "git-blob-sha1") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_excluded_and_deferred_rows_are_never_planned(tmp_path):
    rows = [
        _row(registry_id="A", decision="exclude", decision_reason="r", local_relative_path="a"),
        _row(registry_id="B", decision="defer", decision_reason="r", local_relative_path="b"),
        _row(registry_id="C", decision="quarantine_recommended", decision_reason="r", local_relative_path="c"),
    ]
    entries = load_registry(_write_registry(tmp_path / "r.csv", rows))
    assert plan_acquisition(entries, tmp_path) == []


def test_cli_acquire_refuses_invalid_registry(tmp_path, capsys):
    path = _write_registry(tmp_path / "r.csv", [_row(download_url="http://insecure")])
    assert main(["acquire", str(path), "--raw", str(tmp_path / "raw"), "--apply"]) == 1
    assert "nothing acquired" in capsys.readouterr().out


# --- ingestion report --------------------------------------------------------

def test_ingestion_report_counts_without_text(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_tei(raw / "a.xml", SYNTHETIC_TEI_BODY)
    (raw / "b.xml").write_text("<catalog/>", encoding="utf-8")
    (raw / "dup.xml").write_bytes((raw / "a.xml").read_bytes())
    out = tmp_path / "extracted"
    manifest = build_manifest(raw, extract_dir=out)
    (out / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    assert main(["chunk", str(out)]) == 0

    report = build_ingestion_report(out / "manifest.json", extracted_dir=out,
                                    settings=IngestionSettings())
    totals = report["totals"]
    assert totals["sources"] == 3
    assert totals["rejected"] == 1
    assert totals["duplicate_files_beyond_first"] == 1
    # Identical files share a content-derived source_id, so one output.
    assert report["chunks"]["sources_validated"] == 1
    assert totals["validation_problem_sources"] == 0
    assert report["rejected_sources"][0]["status"] == "unsupported_format"
    assert "pāṇḍu" not in json.dumps(report, ensure_ascii=False)


def test_manifest_update_processes_only_selected_paths(tmp_path):
    raw = tmp_path / "raw"
    (raw / "old").mkdir(parents=True)
    (raw / "new").mkdir()
    (raw / "old" / "a.txt").write_text("Old source.", encoding="utf-8")
    out = tmp_path / "extracted"
    manifest_path = out / "manifest.json"
    assert main(["manifest", str(raw), "--out", str(manifest_path), "--extract-dir", str(out)]) == 0
    before = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_record = before["sources"][0]

    make_tei(raw / "new" / "b.xml", SYNTHETIC_TEI_BODY)
    (raw / "old" / "a.txt").write_text("Changed but not selected.", encoding="utf-8")
    assert main(["manifest-update", str(manifest_path), "--root", str(raw),
                 "--path-prefix", "new/", "--extract-dir", str(out)]) == 0

    after = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_path = {r["relative_path"]: r for r in after["sources"]}
    assert set(by_path) == {"old/a.txt", "new/b.xml"}
    # The unselected record is kept exactly as stored (not re-hashed).
    assert by_path["old/a.txt"] == old_record
    assert by_path["new/b.xml"]["extractor"] == "tei_xml"
    assert list(out.glob("manifest.before-update-*.json"))
