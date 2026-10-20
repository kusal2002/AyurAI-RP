"""File-based storage for candidates, mentions, conflicts and reviews.

Layout of a candidate directory (git-ignored, under corpus/extracted/):

    candidates.jsonl       current state of every candidate (one per line)
    conflicts.json         detected conflicts with acknowledgement state
    review_log.jsonl       append-only log of every review decision
    mentions/<source>.jsonl  concept mentions per chunk

Re-running extraction keeps review state and history: a candidate produced
again keeps its status; one no longer produced for a processed source is
marked stale, never deleted.

run_extraction() reports these counters:

    new                     produced for the first time
    kept_with_review_state  produced again; review state kept
    refreshed_analysis      produced again with a changed ANALYSIS_FIELDS value
    revived                 was stale, produced again, now not stale
    newly_stale             was not stale, not produced again, now stale
    still_stale             was already stale and is still not produced

Candidates of sources not processed in a run are left exactly as stored and
are not counted.
"""

import json
import os
from pathlib import Path
from typing import Callable, Iterable

from app.knowledge_candidates.conflicts import attach_conflicts, detect_conflicts
from app.knowledge_candidates.extractor import CandidateExtractor
from app.knowledge_candidates.models import (
    CandidateClaim,
    ChunkMentions,
    Conflict,
    ReviewEvent,
)
from app.knowledge_ingestion.models import EvidenceCategory, TextChunk


# Every CandidateClaim field belongs to exactly one group. A re-extraction
# replaces the analysis fields with the fresh extraction and keeps the
# review/lifecycle fields; the identity field is what matches the two.
IDENTITY_FIELDS = frozenset({"claim_id"})
ANALYSIS_FIELDS = frozenset({
    "subject", "predicate", "object", "cue", "passage", "evidence_category",
    "extraction_method", "extractor_version", "lexicon_version",
    "extraction_confidence", "uncertainty",
})
# conflict_ids is recomputed after every merge; stale is set by the merge.
REVIEW_LIFECYCLE_FIELDS = frozenset({
    "review_status", "review_history", "conflict_ids", "stale", "extracted_at",
})


def _analysis(candidate: CandidateClaim) -> dict:
    return candidate.model_dump(mode="json", include=set(ANALYSIS_FIELDS))


def _write_atomic(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line + "\n")
    os.replace(temporary, path)


class CandidateStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @property
    def candidates_path(self) -> Path:
        return self.root / "candidates.jsonl"

    @property
    def conflicts_path(self) -> Path:
        return self.root / "conflicts.json"

    @property
    def review_log_path(self) -> Path:
        return self.root / "review_log.jsonl"

    def load_candidates(self) -> dict[str, CandidateClaim]:
        if not self.candidates_path.is_file():
            return {}
        with self.candidates_path.open(encoding="utf-8") as handle:
            items = [
                CandidateClaim.model_validate_json(line)
                for line in handle if line.strip()
            ]
        return {item.claim_id: item for item in items}

    def load_conflicts(self) -> dict[str, Conflict]:
        if not self.conflicts_path.is_file():
            return {}
        data = json.loads(self.conflicts_path.read_text(encoding="utf-8"))
        return {
            item["conflict_id"]: Conflict.model_validate(item) for item in data
        }

    def save(
        self,
        candidates: dict[str, CandidateClaim],
        conflicts: dict[str, Conflict],
    ) -> None:
        ordered = sorted(
            candidates.values(),
            key=lambda c: (c.passage.source_id, c.passage.chunk_id, c.claim_id),
        )
        _write_atomic(
            self.candidates_path, (c.model_dump_json() for c in ordered)
        )
        _write_atomic(
            self.conflicts_path,
            [json.dumps(
                [c.model_dump(mode="json") for c in sorted(
                    conflicts.values(), key=lambda c: c.conflict_id)],
                ensure_ascii=False, indent=2,
            )],
        )

    def load_review_log(self) -> list[ReviewEvent]:
        if not self.review_log_path.is_file():
            return []
        with self.review_log_path.open(encoding="utf-8") as handle:
            return [
                ReviewEvent.model_validate_json(line)
                for line in handle if line.strip()
            ]

    def append_review(self, event: ReviewEvent) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.review_log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(event.model_dump_json() + "\n")

    def write_mentions(self, source_id: str, mentions: list[ChunkMentions]) -> None:
        _write_atomic(
            self.root / "mentions" / f"{source_id}.jsonl",
            (m.model_dump_json() for m in mentions if m.mentions),
        )


def run_extraction(
    sources: Iterable[tuple[str, EvidenceCategory | None, Iterable[TextChunk]]],
    extractor: CandidateExtractor,
    store: CandidateStore,
    progress: Callable[[str, int], None] | None = None,
) -> dict:
    """Extract candidates for the given sources and merge them into store.

    sources yields (source_id, declared evidence category, chunks).
    """
    existing = store.load_candidates()
    previous_conflicts = store.load_conflicts()
    produced: dict[str, CandidateClaim] = {}
    processed_sources: set[str] = set()
    mention_count = 0

    for source_id, category, chunks in sources:
        processed_sources.add(source_id)
        source_mentions: list[ChunkMentions] = []
        found = 0
        for chunk in chunks:
            chunk_mentions, candidates = extractor.extract(chunk, category)
            source_mentions.append(chunk_mentions)
            mention_count += len(chunk_mentions.mentions)
            for candidate in candidates:
                produced.setdefault(candidate.claim_id, candidate)
                found += 1
        store.write_mentions(source_id, source_mentions)
        if progress:
            progress(source_id, found)

    merged: dict[str, CandidateClaim] = {}
    new = kept = refreshed = revived = newly_stale = still_stale = 0
    for claim_id, candidate in existing.items():
        if claim_id in produced:
            # Same candidate identity: take the fresh extraction analysis
            # (ANALYSIS_FIELDS) but keep the review decision, its history and
            # the first extraction time.
            fresh = produced[claim_id]
            if _analysis(fresh) != _analysis(candidate):
                refreshed += 1
            if candidate.stale:
                revived += 1
            merged[claim_id] = fresh.model_copy(
                update={
                    "review_status": candidate.review_status,
                    "review_history": candidate.review_history,
                    "extracted_at": candidate.extracted_at,
                    "stale": False,
                }
            )
            kept += 1
        elif candidate.passage.source_id in processed_sources:
            if candidate.stale:
                still_stale += 1
            else:
                newly_stale += 1
            merged[claim_id] = candidate.model_copy(update={"stale": True})
        else:
            merged[claim_id] = candidate
    for claim_id, candidate in produced.items():
        if claim_id not in merged:
            merged[claim_id] = candidate
            new += 1

    conflicts = attach_conflicts(
        merged, detect_conflicts(merged.values()), previous_conflicts
    )
    store.save(merged, conflicts)
    return {
        "sources": len(processed_sources),
        "mentions": mention_count,
        "candidates_total": len(merged),
        "new": new,
        "kept_with_review_state": kept,
        "refreshed_analysis": refreshed,
        "revived": revived,
        "newly_stale": newly_stale,
        "still_stale": still_stale,
        "conflicts": len(conflicts),
    }
