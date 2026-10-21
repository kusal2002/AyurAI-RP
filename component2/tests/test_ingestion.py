import json

from app.retrieval.ingestion import load_evidence_records, main
from c2_test_support import full_provenance


def write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8"
    )


def test_loads_valid_jsonl_records(tmp_path):
    path = tmp_path / "evidence.jsonl"
    write_jsonl(
        path,
        [full_provenance("EV-1", "text one"), full_provenance("EV-2", "two")],
    )
    records, errors = load_evidence_records(path)

    assert [r.evidence_id for r in records] == ["EV-1", "EV-2"]
    assert errors == []


def test_reports_invalid_and_duplicate_records(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(
            [
                full_provenance("EV-1", "text"),
                full_provenance("EV-1", "duplicate"),
                full_provenance("EV-2", "text", source_url="ftp://bad"),
                {"evidence_id": "EV-3"},
            ]
        ),
        encoding="utf-8",
    )
    records, errors = load_evidence_records(path)

    assert [r.evidence_id for r in records] == ["EV-1"]
    assert [e["evidence_id"] for e in errors] == ["EV-1", "EV-2", "EV-3"]


def test_dry_run_does_not_write(tmp_path, capsys):
    path = tmp_path / "evidence.jsonl"
    write_jsonl(path, [full_provenance("EV-1", "text")])

    assert main([str(path), "--dry-run"]) == 0
    assert "Valid records: 1" in capsys.readouterr().out
