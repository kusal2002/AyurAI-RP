import hashlib
import json

import pytest

from app.knowledge_ingestion.cli import main
from app.knowledge_ingestion.manifest import (
    SourceMetadataError,
    derive_source_id,
    load_source_metadata,
    read_manifest,
    sha256_file,
    write_manifest,
)
from app.knowledge_ingestion.models import ExtractionStatus, SourceMetadata
from app.knowledge_ingestion.service import (
    build_manifest,
    process_source,
    scan_hashes,
    write_extraction,
)
from ingestion_test_support import DEVANAGARI, SINHALA, make_pdf


def write_sidecar(path, **metadata):
    sidecar = path.with_name(path.name + ".meta.json")
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False), "utf-8")
    return sidecar


def test_sha256_is_stable_and_streamed(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"x" * 3000)

    assert sha256_file(path, chunk_size=7) == hashlib.sha256(
        b"x" * 3000
    ).hexdigest()
    assert sha256_file(path) == sha256_file(path)


def test_derived_source_id_tracks_content_not_filename(tmp_path):
    first = tmp_path / "book.txt"
    first.write_text("edition one", encoding="utf-8")
    original = process_source(first).record

    copy = tmp_path / "renamed.txt"
    copy.write_text("edition one", encoding="utf-8")
    assert process_source(copy).record.source_id == original.source_id

    first.write_text("edition two, corrected", encoding="utf-8")
    changed = process_source(first).record
    assert changed.source_id != original.source_id
    assert changed.source_id_origin == "content_hash"
    assert changed.source_id == derive_source_id(changed.content_sha256)


def test_sidecar_metadata_sets_source_id_and_keeps_unknowns_null(tmp_path):
    path = tmp_path / "charaka.txt"
    path.write_text(DEVANAGARI, encoding="utf-8")
    write_sidecar(
        path,
        source_id="charaka-samhita-ed1",
        title="Synthetic Samhita",
        source_language="sa",
        script="Deva",
    )

    record = process_source(path).record

    assert record.source_id == "charaka-samhita-ed1"
    assert record.source_id_origin == "metadata"
    assert record.metadata.title == "Synthetic Samhita"
    assert record.metadata.author is None
    assert record.metadata.publication_year is None
    assert record.errors == []


def test_invalid_sidecar_is_reported_and_not_trusted(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("text", encoding="utf-8")
    write_sidecar(path, source_id="bad id with spaces", invented_field=1)

    record = process_source(path).record

    assert record.source_id_origin == "content_hash"
    assert "is invalid" in record.errors[0]
    assert "source_id" in record.errors[0]


def test_metadata_file_rejects_unknown_fields(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"titel": "typo"}), encoding="utf-8")

    with pytest.raises(SourceMetadataError):
        load_source_metadata(path)


def test_process_source_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        process_source(tmp_path / "absent.txt")


def make_corpus(root):
    (root / "nested").mkdir(parents=True)
    (root / "a.txt").write_text(SINHALA, encoding="utf-8")
    (root / "nested" / "a-copy.txt").write_text(SINHALA, encoding="utf-8")
    (root / "b.md").write_text(f"# Title\n\n{DEVANAGARI}", encoding="utf-8")
    make_pdf(root / "scan.pdf", [None], image_pages={1})
    (root / "old.doc").write_bytes(b"legacy")
    (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
    write_sidecar(root / "b.md", source_id="b-source")


def test_build_manifest_reports_status_duplicates_and_skips(tmp_path):
    root = tmp_path / "raw"
    make_corpus(root)

    manifest = build_manifest(root)

    by_path = {r.relative_path: r for r in manifest.sources}
    assert sorted(by_path) == [
        "a.txt", "b.md", "nested/a-copy.txt", "old.doc", "scan.pdf",
    ]
    assert by_path["a.txt"].extraction_status == ExtractionStatus.EXTRACTED
    assert by_path["b.md"].source_id == "b-source"
    assert (
        by_path["scan.pdf"].extraction_status
        == ExtractionStatus.NEEDS_OCR_OR_REVIEW
    )
    assert by_path["scan.pdf"].pages_needing_ocr == [1]
    assert (
        by_path["old.doc"].extraction_status
        == ExtractionStatus.UNSUPPORTED_FORMAT
    )
    assert len(manifest.duplicate_groups) == 1
    assert manifest.duplicate_groups[0].relative_paths == [
        "a.txt", "nested/a-copy.txt",
    ]
    assert manifest.source_id_conflicts == []


def test_reused_source_id_with_different_content_is_a_conflict(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    for name, text in (("one.txt", "first"), ("two.txt", "second")):
        path = root / name
        path.write_text(text, encoding="utf-8")
        write_sidecar(path, source_id="same-id")

    manifest = build_manifest(root)

    assert len(manifest.source_id_conflicts) == 1
    conflict = manifest.source_id_conflicts[0]
    assert conflict.source_id == "same-id"
    assert conflict.relative_paths == ["one.txt", "two.txt"]


def test_manifest_round_trip(tmp_path):
    root = tmp_path / "raw"
    make_corpus(root)
    manifest = build_manifest(root)

    path = write_manifest(manifest, tmp_path / "out" / "manifest.json")

    assert read_manifest(path) == manifest


def test_write_extraction_is_idempotent_and_keeps_unicode(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text(f"{SINHALA}\n\n{DEVANAGARI}", encoding="utf-8")
    out = tmp_path / "extracted"

    summary, passages = write_extraction(process_source(path), out)
    first = passages.read_text(encoding="utf-8")
    write_extraction(process_source(path), out)

    assert passages.read_text(encoding="utf-8") == first
    lines = [json.loads(line) for line in first.splitlines()]
    assert [line["text"] for line in lines] == [SINHALA, DEVANAGARI]
    assert SINHALA in first  # stored as UTF-8, not \\u escapes
    assert {line["source_id"] for line in lines} == {
        process_source(path).record.source_id
    }
    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    assert "passages" not in summary_data
    assert summary_data["source"]["passage_count"] == 2
    assert sorted(p.name for p in out.iterdir()) == sorted(
        [summary.name, passages.name]
    )


def test_scan_hashes_finds_duplicates_without_extraction(tmp_path):
    root = tmp_path / "raw"
    make_corpus(root)

    by_hash, skipped = scan_hashes(root)

    groups = [paths for paths in by_hash.values() if len(paths) > 1]
    assert groups == [["a.txt", "nested/a-copy.txt"]]
    assert skipped == []


# --- CLI ---------------------------------------------------------------------

def test_cli_inspect_prints_metadata_but_no_text(tmp_path, capsys):
    path = tmp_path / "book.txt"
    path.write_text("confidential passage wording", encoding="utf-8")

    assert main(["inspect", str(path)]) == 0
    output = capsys.readouterr().out
    assert "status:      extracted" in output
    assert "confidential passage wording" not in output

    assert main(["inspect", str(path), "--json"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["source"]["passage_count"] == 1
    assert "confidential passage wording" not in output


def test_cli_extract_writes_outputs(tmp_path, capsys):
    path = tmp_path / "book.md"
    path.write_text("# H\n\nBody", encoding="utf-8")
    out = tmp_path / "extracted"

    assert main(["extract", str(path), "--out", str(out)]) == 0
    assert len(list(out.glob("*.passages.jsonl"))) == 1


def test_cli_extract_writes_nothing_for_scanned_pdf(tmp_path, capsys):
    path = make_pdf(tmp_path / "scan.pdf", [None], image_pages={1})
    out = tmp_path / "extracted"

    assert main(["extract", str(path), "--out", str(out)]) == 1
    assert "needs OCR:   pages 1" in capsys.readouterr().out
    assert not out.exists()


def test_cli_manifest_status_and_duplicates(tmp_path, capsys):
    root = tmp_path / "raw"
    make_corpus(root)
    manifest_path = tmp_path / "extracted" / "manifest.json"

    assert main([
        "manifest", str(root), "--out", str(manifest_path),
        "--extract-dir", str(tmp_path / "extracted"),
    ]) == 0
    assert manifest_path.is_file()
    assert (tmp_path / "extracted" / "b-source.passages.jsonl").is_file()
    capsys.readouterr()

    # Not every source is fully extracted, so status signals it.
    assert main(["status", str(manifest_path)]) == 1
    output = capsys.readouterr().out
    assert "needs_ocr_or_review" in output
    assert "DUPLICATE content: a.txt, nested/a-copy.txt" in output

    assert main(["duplicates", str(root)]) == 1
    assert "Duplicate groups: 1" in capsys.readouterr().out
    assert main(["duplicates", str(manifest_path)]) == 1


def test_cli_reports_missing_inputs(tmp_path, capsys):
    assert main(["inspect", str(tmp_path / "absent.pdf")]) == 2
    assert main(["status", str(tmp_path / "absent.json")]) == 2

    bogus = tmp_path / "bogus.json"
    bogus.write_text('{"sources": "not a list"}', encoding="utf-8")
    assert main(["status", str(bogus)]) == 2
    assert "ERROR" in capsys.readouterr().out


# --- corpus-relative paths for direct extraction ----------------------------

import os  # noqa: E402

from app.knowledge_ingestion.service import (  # noqa: E402
    SourceOutsideRootError,
    corpus_relative_path,
)


def make_book(root):
    book = root / "ayurveda_books" / "Ashtank_Hirdaya.txt"
    book.parent.mkdir(parents=True)
    book.write_text("Synthetic test text about pandu.", encoding="utf-8")
    return book


def summary_relative_path(out):
    (summary,) = out.glob("*.extraction.json")
    return json.loads(summary.read_text(encoding="utf-8"))["source"]["relative_path"]


def test_cli_extract_with_root_records_corpus_relative_path(tmp_path, capsys):
    root = tmp_path / "raw"
    book = make_book(root)
    out = tmp_path / "extracted"

    assert main(["extract", str(book), "--out", str(out), "--root", str(root)]) == 0
    assert summary_relative_path(out) == "ayurveda_books/Ashtank_Hirdaya.txt"


def test_cli_extract_without_root_keeps_file_name(tmp_path, capsys):
    book = make_book(tmp_path / "raw")
    out = tmp_path / "extracted"

    assert main(["extract", str(book), "--out", str(out)]) == 0
    assert summary_relative_path(out) == "Ashtank_Hirdaya.txt"


def test_relative_path_uses_forward_slashes_for_native_and_messy_paths(tmp_path):
    root = tmp_path / "raw"
    book = make_book(root)
    native = os.sep.join([str(root), "ayurveda_books", "Ashtank_Hirdaya.txt"])
    messy = str(root / "ayurveda_books" / ".." / "ayurveda_books" / "Ashtank_Hirdaya.txt")

    for candidate in (book, native, messy, str(book).replace("/", os.sep)):
        assert corpus_relative_path(candidate, root) == "ayurveda_books/Ashtank_Hirdaya.txt"
    assert corpus_relative_path(book, str(root) + os.sep) == "ayurveda_books/Ashtank_Hirdaya.txt"


def test_source_outside_root_is_rejected(tmp_path, capsys):
    root = tmp_path / "raw"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "book.txt"
    outside.parent.mkdir()
    outside.write_text("Synthetic text.", encoding="utf-8")
    out = tmp_path / "extracted"

    with pytest.raises(SourceOutsideRootError, match="not inside the corpus root"):
        corpus_relative_path(outside, root)
    assert main(["extract", str(outside), "--out", str(out), "--root", str(root)]) == 2
    assert "not inside the corpus root" in capsys.readouterr().out
    assert not out.exists()  # nothing written, no fallback to the file name


def test_root_must_be_an_existing_directory(tmp_path):
    book = make_book(tmp_path / "raw")
    with pytest.raises(NotADirectoryError):
        corpus_relative_path(book, tmp_path / "missing")


def test_explicit_relative_path_and_manifest_paths_are_unchanged(tmp_path):
    root = tmp_path / "raw"
    book = make_book(root)

    assert process_source(book, "custom/given.txt").record.relative_path == "custom/given.txt"
    assert process_source(book).record.relative_path == "Ashtank_Hirdaya.txt"

    manifest = build_manifest(root)
    (record,) = manifest.sources
    assert record.relative_path == "ayurveda_books/Ashtank_Hirdaya.txt"
    assert corpus_relative_path(book, root) == record.relative_path
