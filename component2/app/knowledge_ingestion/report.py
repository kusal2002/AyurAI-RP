"""Ingestion report: counts of what was processed, skipped and validated.

Reads local files only (manifest, chunk files, candidate store) and
returns counts and identifiers, never passage text, so the report can be
shared or attached to research notes.
"""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.config import IngestionSettings
from app.knowledge_ingestion.chunking import validate_chunks
from app.knowledge_ingestion.manifest import read_manifest
from app.knowledge_ingestion.models import ExtractionStatus
from app.knowledge_ingestion.service import (
    chunks_path,
    iter_extraction_summaries,
    load_chunks,
    load_extraction_output,
)


_PROCESSED = {ExtractionStatus.EXTRACTED, ExtractionStatus.PARTIAL_EXTRACTION}
_REJECTED = {
    ExtractionStatus.FAILED,
    ExtractionStatus.UNSUPPORTED_FORMAT,
    ExtractionStatus.EMPTY_OR_UNREADABLE,
}


def _collection(relative_path: str) -> str:
    return relative_path.split("/", 1)[0] if "/" in relative_path else "(root)"


def build_ingestion_report(
    manifest_path: str | Path,
    *,
    extracted_dir: str | Path | None = None,
    candidates_dir: str | Path | None = None,
    settings: IngestionSettings | None = None,
) -> dict:
    settings = settings or IngestionSettings()
    manifest = read_manifest(manifest_path)
    sources = manifest.sources

    statuses = Counter(record.extraction_status.value for record in sources)
    duplicate_extra = sum(
        len(group.relative_paths) - 1 for group in manifest.duplicate_groups
    )
    by_collection: dict[str, Counter] = {}
    for record in sources:
        by_collection.setdefault(
            _collection(record.relative_path), Counter()
        )[record.extraction_status.value] += 1

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_generated_at": manifest.generated_at.isoformat(),
        "totals": {
            "sources": len(sources),
            "processed": sum(
                1 for r in sources if r.extraction_status in _PROCESSED
            ),
            "needs_ocr_or_review": statuses.get(
                ExtractionStatus.NEEDS_OCR_OR_REVIEW.value, 0
            ),
            "rejected": sum(
                1 for r in sources if r.extraction_status in _REJECTED
            ),
            "skipped_files": len(manifest.skipped_files),
            "duplicate_groups": len(manifest.duplicate_groups),
            "duplicate_files_beyond_first": duplicate_extra,
            "source_id_conflicts": len(manifest.source_id_conflicts),
            "with_curated_title": sum(1 for r in sources if r.metadata.title),
            "with_evidence_category": sum(
                1 for r in sources if r.metadata.evidence_category
            ),
            "with_licence_notes": sum(
                1 for r in sources if r.metadata.usage_notes
            ),
            "validation_problem_sources": 0,
        },
        "by_status": dict(sorted(statuses.items())),
        "by_collection": {
            name: dict(sorted(counts.items()))
            for name, counts in sorted(by_collection.items())
        },
        "rejected_sources": [
            {
                "source_id": r.source_id,
                "relative_path": r.relative_path,
                "status": r.extraction_status.value,
                "errors": r.errors[:3],
            }
            for r in sources
            if r.extraction_status in _REJECTED
        ],
    }

    if extracted_dir is not None:
        chunked = validated = 0
        problems: list[dict] = []
        missing: list[str] = []
        for summary in iter_extraction_summaries(extracted_dir):
            record, passages = load_extraction_output(summary)
            path = chunks_path(summary.parent, record.source_id)
            if not path.is_file():
                if passages:
                    missing.append(record.source_id)
                continue
            chunked += 1
            found = validate_chunks(load_chunks(path), passages, settings)
            if found:
                problems.append(
                    {"source_id": record.source_id, "problems": len(found),
                     "first": found[:3]}
                )
            else:
                validated += 1
        report["chunks"] = {
            "sources_chunked": chunked,
            "sources_validated": validated,
            "sources_without_chunks": len(missing),
            "sources_with_problems": problems,
        }
        report["totals"]["validation_problem_sources"] = len(problems)

    if candidates_dir is not None:
        from app.knowledge_candidates.store import CandidateStore

        candidates = list(CandidateStore(candidates_dir).load_candidates().values())
        report["candidates"] = {
            "total": len(candidates),
            "by_review_status": dict(sorted(Counter(
                c.review_status.value for c in candidates
            ).items())),
            "stale": sum(1 for c in candidates if c.stale),
            "by_predicate": dict(sorted(Counter(
                c.predicate for c in candidates
            ).items())),
        }
    return report
