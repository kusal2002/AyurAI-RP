"""Ingestion interface for approved evidence sources.

Input is a JSON array or JSON Lines file of EvidenceRecord objects that a
researcher has curated from approved classical or contemporary sources.
Each record is validated with the existing provenance rules before it is
saved. This module does not scrape, download or generate any literature.

Usage:
    python -m app.retrieval.ingestion corpus/processed/evidence.jsonl --dry-run
    python -m app.retrieval.ingestion corpus/processed/evidence.jsonl
"""

import argparse
import json
from pathlib import Path
from typing import Any

from neo4j import Driver
from pydantic import ValidationError

from app.db.repository import save_evidence
from app.models.evidence import EvidenceRecord
from app.ontology.evidence_validation import validate_evidence_provenance


def _read_raw_records(path: Path) -> list[Any]:
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in content.splitlines()
            if line.strip()
        ]
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("Evidence file must contain a JSON array.")
    return data


def load_evidence_records(
    path: str | Path,
) -> tuple[list[EvidenceRecord], list[dict[str, Any]]]:
    """Parse and validate evidence records from a curated file.

    Returns (valid_records, errors). Duplicate evidence IDs are reported
    as errors instead of being merged silently.
    """
    path = Path(path)
    records: list[EvidenceRecord] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()

    for position, raw in enumerate(_read_raw_records(path)):
        try:
            record = EvidenceRecord.model_validate(raw)
            validate_evidence_provenance(record)
        except (ValidationError, ValueError) as exc:
            errors.append(
                {
                    "position": position,
                    "evidence_id": (
                        raw.get("evidence_id")
                        if isinstance(raw, dict)
                        else None
                    ),
                    "error": str(exc).splitlines()[0],
                }
            )
            continue

        if record.evidence_id in seen:
            errors.append(
                {
                    "position": position,
                    "evidence_id": record.evidence_id,
                    "error": "Duplicate evidence_id in input file.",
                }
            )
            continue

        seen.add(record.evidence_id)
        records.append(record)

    return records, errors


def ingest_evidence_records(
    records: list[EvidenceRecord],
    driver: Driver | None = None,
) -> list[str]:
    """Save validated evidence records. Returns the saved evidence IDs.

    After ingestion, call EvidenceRetrievalService.refresh() (or the
    /api/v1/c2/evidence-index/refresh endpoint) to re-index.
    """
    saved = []
    for record in records:
        save_evidence(record, driver)
        saved.append(record.evidence_id)
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the file without writing to Neo4j.",
    )
    args = parser.parse_args(argv)

    records, errors = load_evidence_records(args.path)

    for error in errors:
        print(f"INVALID record {error['position']} "
              f"({error['evidence_id']}): {error['error']}")

    print(f"Valid records: {len(records)}; invalid records: {len(errors)}")

    if args.dry_run or errors:
        if errors:
            print("Nothing saved: fix invalid records first.")
        return 1 if errors else 0

    from app.db.neo4j import close_neo4j_driver

    try:
        saved = ingest_evidence_records(records)
    finally:
        close_neo4j_driver()

    print(f"Saved {len(saved)} evidence records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
