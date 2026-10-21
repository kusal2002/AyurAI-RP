"""Stage E: promote approved candidate claims into the knowledge graph.

Design: docs/stage_e_neo4j_design.md (approved decisions D1-D6).

* Only trusted candidates are promoted: approved, current, with the
  approval backed by a review event that is also present in the
  append-only review log. Every other candidate is reported with a reason.
* Book text is not uploaded: Source and SourceChunk nodes carry
  provenance only, and the evidence node holds just the approved
  supporting sentence (D1). No vectors are written (D2). Candidates and
  the review log stay local (D3).
* Descriptive claims (ontology v1.1, e.g. CONTAINS_INGREDIENT) get their
  supporting sentence as :DescriptiveEvidence, not :Evidence. The API
  evidence index loads :Evidence only, so descriptive claims cannot reach
  retrieval, ranking or reasoning output.
* Each promoted claim is written in ONE write transaction using MERGE on
  stable IDs, so re-running is idempotent and a failure leaves nothing
  half-written. A source_id already stored with different file content
  aborts the transaction. Labels and ID properties come from fixed
  allow-lists, never from data.
* Nodes created here carry promotion_batch_id and created_at, set on
  create only.
* Withdrawn approvals are retracted without deleting anything: the claim
  is relabelled :RetractedClaim, and evidence that no longer supports any
  active claim is relabelled :RetractedEvidence. Re-approval restores them.

plan_promotions() and plan_retractions() need no database. promote() and
retract() write only when called with apply=True.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from neo4j import Driver
from neo4j.exceptions import (
    AuthError,
    Neo4jError,
    ServiceUnavailable,
    SessionExpired,
)

from app.db.neo4j import get_neo4j_driver
from app.db.schema import NODE_IDENTIFIERS
from app.knowledge_candidates.models import (
    BLOCKING_UNCERTAINTY,
    ONTOLOGY_MAPPING,
    QUALIFIED_STATEMENT,
    CandidateClaim,
    Conflict,
    ReviewEvent,
    ReviewerRole,
    ReviewStatus,
)
from app.knowledge_candidates.review import (
    approval_event,
    to_ontology_claim,
    trusted_candidates,
)
from app.knowledge_ingestion.models import EvidenceCategory, SourceRecord, TextChunk
from app.models.evidence import EvidenceRecord, EvidenceType
from app.ontology.evidence_validation import validate_evidence_provenance
from app.ontology.relationships import DESCRIPTIVE_RELATIONSHIP_RULES


# D6: declared source category -> existing EvidenceType. OTHER has no
# honest mapping and blocks promotion.
EVIDENCE_TYPE_BY_CATEGORY = {
    EvidenceCategory.TRADITIONAL_TEXT: EvidenceType.CLASSICAL,
    EvidenceCategory.MODERN_CLINICAL_RESEARCH: EvidenceType.MODERN_RESEARCH,
    EvidenceCategory.SYSTEMATIC_REVIEW: EvidenceType.MODERN_RESEARCH,
    EvidenceCategory.PRACTITIONER_INTERPRETATION: EvidenceType.PRACTITIONER,
}

# :Evidence is read by the API evidence index (list_evidence); descriptive
# support must never carry that label.
EVIDENCE_LABEL = "Evidence"
DESCRIPTIVE_EVIDENCE_LABEL = "DescriptiveEvidence"
_EVIDENCE_LABELS = (EVIDENCE_LABEL, DESCRIPTIVE_EVIDENCE_LABEL)

_SOURCE_PROPERTIES = (
    "title", "author", "editor", "edition", "publication_year", "publisher",
    "source_language", "script", "translation_language", "translator",
    "usage_notes",
)
_CHUNK_PROPERTIES = (
    "source_id", "chunk_index", "page_start", "page_end", "line_start",
    "line_end", "section_heading", "verse_numbers", "citation_refs",
    "printed_pages", "primary_script",
    "scripts", "content_sha256", "chunker_version", "normalization_version",
    "quality_flags",
)


class PromotionError(RuntimeError):
    """The graph write failed; the message never contains credentials."""


@dataclass
class ConceptNode:
    label: str
    id_property: str
    concept_id: str
    name: str


@dataclass
class PromotionPlan:
    candidate_id: str
    claim_id: str
    triple: tuple[str, str, str]
    descriptive: bool
    evidence_label: str
    source_id: str
    source_content_sha256: str
    source_properties: dict[str, Any]
    chunk_id: str
    chunk_properties: dict[str, Any]
    concepts: list[ConceptNode]
    evidence_properties: dict[str, Any]
    sentence_span: tuple[int, int]
    claim_properties: dict[str, Any]


@dataclass
class PromotionReport:
    plans: list[PromotionPlan] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    applied: bool = False
    batch_id: str | None = None
    counters: dict[str, int] = field(default_factory=dict)


@dataclass
class RetractionPlan:
    candidate_id: str
    claim_id: str
    reason: str
    retracted_by: str


@dataclass
class RetractionReport:
    plans: list[RetractionPlan] = field(default_factory=list)
    applied: bool = False
    batch_id: str | None = None
    retracted_claims: list[str] = field(default_factory=list)
    not_in_graph: list[str] = field(default_factory=list)
    evidence_retracted: int = 0


def make_evidence_id(chunk_id: str, start: int, end: int, descriptive: bool = False) -> str:
    payload = json.dumps([chunk_id, start, end], separators=(",", ":"))
    prefix = "DEV-" if descriptive else "EV-"
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _pages(chunk: TextChunk) -> str | None:
    if chunk.page_start is None:
        if chunk.printed_pages:
            # Printed folios of the source edition (TEI <pb n>), not
            # physical pages of the file.
            return "printed p. " + ", ".join(chunk.printed_pages)
        return None
    if chunk.page_start == chunk.page_end:
        return str(chunk.page_start)
    return f"{chunk.page_start}-{chunk.page_end}"


def _citation(chunk: TextChunk) -> str | None:
    """Encoded verse references when present, otherwise danda numbers.

    Both cover the whole chunk; the quoted sentence lies inside it.
    """
    if chunk.citation_refs:
        refs = chunk.citation_refs
        span = refs[0] if len(refs) == 1 else f"{refs[0]} to {refs[-1]}"
        return f"chunk covers {span}"
    if chunk.verse_numbers:
        return "verse " + ", ".join(chunk.verse_numbers)
    return None


def _concept(ref) -> ConceptNode:
    if ref.concept_type not in NODE_IDENTIFIERS or ref.concept_type in {
        "Evidence", "Claim",
    }:
        raise ValueError(f"Concept type {ref.concept_type!r} is not allowed.")
    return ConceptNode(
        label=ref.concept_type,
        id_property=NODE_IDENTIFIERS[ref.concept_type],
        concept_id=ref.concept_id,
        name=ref.label,
    )


def _event_key(event: ReviewEvent) -> tuple:
    return (
        event.claim_id, event.at, event.reviewer, event.reviewer_role,
        event.from_status, event.to_status,
    )


def plan_promotions(
    candidates: Iterable[CandidateClaim],
    conflicts: dict[str, Conflict],
    sources: dict[str, SourceRecord],
    chunks: dict[str, TextChunk],
    review_log: Iterable[ReviewEvent] | None = None,
    conflicting_source_ids: Iterable[str] = (),
) -> PromotionReport:
    """Decide what would be written. Never touches the database.

    review_log: events from review_log.jsonl. When given, an approval must
    appear there exactly as recorded on the candidate.
    conflicting_source_ids: source IDs the manifest reports as reused for
    different file content; their candidates are not promoted.
    """
    report = PromotionReport()
    candidates = list(candidates)
    trusted = {c.claim_id for c in trusted_candidates(candidates)}
    logged = (
        {_event_key(event) for event in review_log}
        if review_log is not None else None
    )
    conflicting = set(conflicting_source_ids)

    for candidate in sorted(candidates, key=lambda c: c.claim_id):
        reason = _skip_reason(
            candidate, trusted, sources, chunks, logged, conflicting
        )
        if reason:
            report.skipped.append((candidate.claim_id, reason))
            continue

        claim = to_ontology_claim(candidate, conflicts)
        if claim is None:
            report.skipped.append(
                (candidate.claim_id,
                 f"{candidate.predicate} has no direct ontology mapping")
            )
            continue

        descriptive = claim.predicate in DESCRIPTIVE_RELATIONSHIP_RULES
        source = sources[candidate.passage.source_id]
        chunk = chunks[candidate.passage.chunk_id]
        metadata = source.metadata
        approval = approval_event(candidate)
        passage = candidate.passage
        evidence = EvidenceRecord(
            evidence_id=make_evidence_id(
                chunk.chunk_id, passage.sentence_start, passage.sentence_end,
                descriptive,
            ),
            title=metadata.title,
            source_name=(
                f"{metadata.title} ({metadata.edition})"
                if metadata.edition else metadata.title
            ),
            evidence_type=EVIDENCE_TYPE_BY_CATEGORY[metadata.evidence_category],
            section=chunk.section_heading or None,
            page=_pages(chunk),
            text=passage.sentence,
            concepts=[claim.subject_id, claim.object_id],
            citation=_citation(chunk),
            practitioner_verified=approval.reviewer_role.value == "practitioner",
        )
        try:
            validate_evidence_provenance(evidence)
        except ValueError as exc:
            report.skipped.append((candidate.claim_id, f"evidence invalid: {exc}"))
            continue

        report.plans.append(
            PromotionPlan(
                candidate_id=candidate.claim_id,
                claim_id=claim.claim_id,
                triple=(claim.subject_id, claim.predicate, claim.object_id),
                descriptive=descriptive,
                evidence_label=(
                    DESCRIPTIVE_EVIDENCE_LABEL if descriptive else EVIDENCE_LABEL
                ),
                source_id=source.source_id,
                source_content_sha256=source.content_sha256,
                source_properties=_drop_none({
                    **{k: getattr(metadata, k) for k in _SOURCE_PROPERTIES},
                    "evidence_category": metadata.evidence_category.value,
                    "content_sha256": source.content_sha256,
                    "source_format": source.source_format.value,
                    "file_name": source.file_name,
                    "extraction_status": source.extraction_status.value,
                    "extractor": source.extractor,
                    "extractor_version": source.extractor_version,
                }),
                chunk_id=chunk.chunk_id,
                chunk_properties=_drop_none(
                    {k: getattr(chunk, k) for k in _CHUNK_PROPERTIES}
                ),
                concepts=[
                    _concept(candidate.subject),
                    _concept(candidate.object),
                ],
                evidence_properties={
                    **_drop_none(evidence.model_dump(mode="json")),
                    "chunk_id": chunk.chunk_id,
                    "source_id": source.source_id,
                    "candidate_id": candidate.claim_id,
                },
                sentence_span=(passage.sentence_start, passage.sentence_end),
                # created_at is set once, on create, by the write query.
                claim_properties={
                    **_drop_none(claim.model_dump(mode="json", exclude={"created_at"})),
                    "descriptive": descriptive,
                    # True when the supporting sentence limits the claim to a
                    # historical period or to stated proportions; read the
                    # evidence text before using the claim.
                    "qualified_statement": QUALIFIED_STATEMENT in candidate.uncertainty,
                    "candidate_id": candidate.claim_id,
                    "approved_by": approval.reviewer,
                    "approved_role": approval.reviewer_role.value,
                    "approved_at": approval.at.isoformat(),
                    "extraction_method": candidate.extraction_method,
                    "extractor_version": candidate.extractor_version,
                    "lexicon_version": candidate.lexicon_version,
                },
            )
        )
    return report


def _source_properties(source: SourceRecord) -> dict[str, Any]:
    metadata = source.metadata
    return _drop_none({
        **{k: getattr(metadata, k) for k in _SOURCE_PROPERTIES},
        "evidence_category": metadata.evidence_category.value,
        "content_sha256": source.content_sha256,
        "source_format": source.source_format.value,
        "file_name": source.file_name,
        "extraction_status": source.extraction_status.value,
        "extractor": source.extractor,
        "extractor_version": source.extractor_version,
    })


def _source_problem(source: SourceRecord | None, chunk: TextChunk | None,
                    source_id: str, conflicting: set[str]) -> str | None:
    if source_id in conflicting:
        return "source_id is reused for different file content (see manifest)"
    if source is None:
        return "source record not found"
    metadata = source.metadata
    if not metadata.title or not metadata.title.strip():
        return "source metadata has no title (add a .meta.json sidecar)"
    if metadata.evidence_category is None:
        return "source evidence_category not declared"
    if metadata.evidence_category not in EVIDENCE_TYPE_BY_CATEGORY:
        return f"evidence_category {metadata.evidence_category.value!r} has no evidence type mapping"
    if chunk is None:
        return "supporting chunk not found (re-chunk and re-extract)"
    if chunk.source_id != source.source_id:
        return "supporting chunk belongs to another source"
    return None


def plan_modelled_promotions(
    modelled: Iterable["ModelledClaim"],
    sources: dict[str, SourceRecord],
    chunks: dict[str, TextChunk],
    modelled_log: Iterable["ModelledEvent"] | None = None,
    conflicting_source_ids: Iterable[str] = (),
) -> PromotionReport:
    """Plan reviewer-modelled claims (app.knowledge_candidates.modelled).

    Same guarantees as candidate promotion: curated source metadata, a
    current chunk whose text still contains the quoted span exactly, the
    creation event present in the append-only log, and one write
    transaction per claim. Never touches the database.
    """
    from app.knowledge_candidates.modelled import ModelledStatus

    report = PromotionReport()
    logged = (
        {(e.modelled_id, e.action, e.reviewer, e.at) for e in modelled_log}
        if modelled_log is not None else None
    )
    conflicting = set(conflicting_source_ids)
    for claim in sorted(modelled, key=lambda c: c.modelled_id):
        created = claim.created
        passage = claim.passage
        source = sources.get(passage.source_id)
        chunk = chunks.get(passage.chunk_id)
        reason = None
        if claim.status != ModelledStatus.ACTIVE:
            reason = f"modelled claim is {claim.status.value}"
        elif logged is not None and (
            created.modelled_id, created.action, created.reviewer, created.at
        ) not in logged:
            reason = "creation event not found in modelled_log.jsonl"
        else:
            reason = _source_problem(source, chunk, passage.source_id, conflicting)
        if reason is None and chunk.text[passage.sentence_start:passage.sentence_end] != passage.sentence:
            reason = "quoted passage no longer matches the chunk text (stale)"
        if reason:
            report.skipped.append((claim.modelled_id, reason))
            continue

        metadata = source.metadata
        practitioner = created.reviewer_role == ReviewerRole.PRACTITIONER
        evidence = EvidenceRecord(
            evidence_id=make_evidence_id(chunk.chunk_id, passage.sentence_start, passage.sentence_end),
            title=metadata.title,
            source_name=(f"{metadata.title} ({metadata.edition})" if metadata.edition else metadata.title),
            evidence_type=EVIDENCE_TYPE_BY_CATEGORY[metadata.evidence_category],
            section=chunk.section_heading or None,
            page=_pages(chunk),
            text=passage.sentence,
            concepts=[claim.subject.concept_id, claim.object.concept_id],
            citation=_citation(chunk),
            practitioner_verified=practitioner,
        )
        try:
            validate_evidence_provenance(evidence)
        except ValueError as exc:
            report.skipped.append((claim.modelled_id, f"evidence invalid: {exc}"))
            continue
        claim_id = f"CL-{claim.modelled_id}"
        report.plans.append(PromotionPlan(
            candidate_id=claim.modelled_id,
            claim_id=claim_id,
            triple=(claim.subject.concept_id, claim.predicate, claim.object.concept_id),
            descriptive=False,
            evidence_label=EVIDENCE_LABEL,
            source_id=source.source_id,
            source_content_sha256=source.content_sha256,
            source_properties=_source_properties(source),
            chunk_id=chunk.chunk_id,
            chunk_properties=_drop_none({k: getattr(chunk, k) for k in _CHUNK_PROPERTIES}),
            concepts=[_concept(claim.subject), _concept(claim.object)],
            evidence_properties={
                **_drop_none(evidence.model_dump(mode="json")),
                "chunk_id": chunk.chunk_id,
                "source_id": source.source_id,
                "candidate_id": claim.modelled_id,
            },
            sentence_span=(passage.sentence_start, passage.sentence_end),
            claim_properties={
                "claim_id": claim_id,
                "subject_id": claim.subject.concept_id,
                "predicate": claim.predicate,
                "object_id": claim.object.concept_id,
                "statement": claim.statement,
                "verification_status": (
                    "practitioner_verified" if practitioner else "literature_supported"
                ),
                "descriptive": False,
                "qualified_statement": False,
                "candidate_id": claim.modelled_id,
                "modelled": True,
                "models_candidate_id": claim.models_candidate_id,
                "approved_by": created.reviewer,
                "approved_role": created.reviewer_role.value,
                "approved_at": created.at.isoformat(),
                "modelling_note": created.note[:1000],
                "extraction_method": "reviewer_modelled",
                "extractor_version": None,
                "lexicon_version": "reviewer-modelled",
            },
        ))
        report.plans[-1].claim_properties = _drop_none(report.plans[-1].claim_properties)
    return report


def plan_modelled_retractions(modelled: Iterable["ModelledClaim"]) -> RetractionReport:
    """Withdrawn modelled claims whose graph claim must stop being used."""
    from app.knowledge_candidates.modelled import ModelledStatus

    report = RetractionReport()
    for claim in sorted(modelled, key=lambda c: c.modelled_id):
        if claim.status != ModelledStatus.WITHDRAWN:
            continue
        last = claim.history[-1]
        report.plans.append(RetractionPlan(
            candidate_id=claim.modelled_id,
            claim_id=f"CL-{claim.modelled_id}",
            reason=f"modelled claim withdrawn: {last.note}"[:500],
            retracted_by=last.reviewer,
        ))
    return report


def _skip_reason(
    candidate: CandidateClaim,
    trusted: set[str],
    sources: dict[str, SourceRecord],
    chunks: dict[str, TextChunk],
    logged: set[tuple] | None,
    conflicting: set[str],
) -> str | None:
    if candidate.claim_id not in trusted:
        if candidate.review_status != ReviewStatus.APPROVED:
            return f"not approved ({candidate.review_status.value})"
        if candidate.stale:
            return "stale"
        if BLOCKING_UNCERTAINTY & set(candidate.uncertainty):
            return "relation not supported by the sentence structure"
        return "approved status has no matching approval event"
    if logged is not None and _event_key(approval_event(candidate)) not in logged:
        return "approval event not found in review_log.jsonl"
    if candidate.passage.source_id in conflicting:
        return "source_id is reused for different file content (see manifest)"
    source = sources.get(candidate.passage.source_id)
    if source is None:
        return "source record not found"
    metadata = source.metadata
    if not metadata.title or not metadata.title.strip():
        return "source metadata has no title (add a .meta.json sidecar)"
    if metadata.evidence_category is None:
        return "source evidence_category not declared"
    if metadata.evidence_category not in EVIDENCE_TYPE_BY_CATEGORY:
        return f"evidence_category {metadata.evidence_category.value!r} has no evidence type mapping"
    chunk = chunks.get(candidate.passage.chunk_id)
    if chunk is None:
        return "supporting chunk not found (re-chunk and re-extract)"
    if chunk.source_id != source.source_id:
        return "supporting chunk belongs to another source"
    return None


# --- promotion writes --------------------------------------------------------

# Returns no row when the source_id already exists with different content,
# which aborts the transaction.
_MERGE_SOURCE = """
MERGE (s:Source {source_id: $source_id})
ON CREATE SET s.promotion_batch_id = $batch_id, s.created_at = $now,
              s.content_sha256 = $content_sha256
WITH s
WHERE s.content_sha256 = $content_sha256
SET s += $properties
RETURN s.source_id AS source_id
"""
_MERGE_CHUNK = """
MATCH (s:Source {source_id: $source_id})
MERGE (c:SourceChunk {chunk_id: $chunk_id})
ON CREATE SET c.promotion_batch_id = $batch_id, c.created_at = $now
SET c += $properties
MERGE (c)-[:PART_OF]->(s)
"""
_MERGE_CONCEPT = """
MERGE (n:{label} {{{id_property}: $concept_id}})
ON CREATE SET n.name = $name,
              n.created_by = 'candidate_promotion',
              n.lexicon_version = $lexicon_version,
              n.promotion_batch_id = $batch_id,
              n.created_at = $now
"""
# A previously retracted node with the same ID is restored, not duplicated.
_MERGE_EVIDENCE = """
OPTIONAL MATCH (old:RetractedEvidence {{evidence_id: $evidence_id}})
FOREACH (x IN CASE WHEN old IS NULL THEN [] ELSE [old] END |
    REMOVE x:RetractedEvidence SET x:{label})
WITH 1 AS ignored
MATCH (c:SourceChunk {{chunk_id: $chunk_id}})
MERGE (e:{label} {{evidence_id: $evidence_id}})
ON CREATE SET e.promotion_batch_id = $batch_id, e.created_at = $now
SET e += $properties
MERGE (e)-[r:FROM_CHUNK]->(c)
SET r.sentence_start = $sentence_start, r.sentence_end = $sentence_end
"""
_MERGE_CLAIM = """
OPTIONAL MATCH (old:RetractedClaim {{claim_id: $claim_id}})
FOREACH (x IN CASE WHEN old IS NULL THEN [] ELSE [old] END |
    REMOVE x:RetractedClaim SET x:Claim)
WITH 1 AS ignored
MATCH (subject:{subject_label} {{{subject_id_property}: $subject_id}})
MATCH (object:{object_label} {{{object_id_property}: $object_id}})
MATCH (e:{evidence_label} {{evidence_id: $evidence_id}})
MERGE (claim:Claim {{claim_id: $claim_id}})
ON CREATE SET claim.promotion_batch_id = $batch_id, claim.created_at = $now
SET claim += $properties
MERGE (subject)-[:SUBJECT_OF]->(claim)
MERGE (claim)-[:OBJECT_OF]->(object)
MERGE (e)-[:SUPPORTS]->(claim)
RETURN claim.claim_id AS claim_id
"""

_COUNTER_FIELDS = (
    "nodes_created", "relationships_created", "properties_set",
    "labels_added", "labels_removed", "nodes_deleted", "relationships_deleted",
)


def _runner(tx, counters: dict[str, int]):
    def run(query: str, **params) -> list:
        result = tx.run(query, **params)
        records = list(result)
        summary = result.consume()
        for name in _COUNTER_FIELDS:
            counters[name] += getattr(summary.counters, name, 0)
        return records
    return run


def write_plan(tx, plan: PromotionPlan, batch_id: str, now: str) -> dict[str, int]:
    """Run every statement for one plan inside the given transaction."""
    if plan.evidence_label not in _EVIDENCE_LABELS:
        raise PromotionError(f"Unexpected evidence label {plan.evidence_label!r}.")
    counters = dict.fromkeys(_COUNTER_FIELDS, 0)
    run = _runner(tx, counters)

    common = {"batch_id": batch_id, "now": now}
    if not run(_MERGE_SOURCE, source_id=plan.source_id,
               content_sha256=plan.source_content_sha256,
               properties=plan.source_properties, **common):
        # Raising inside the transaction function rolls everything back.
        raise PromotionError(
            f"Source {plan.source_id} already exists in the graph with "
            "different file content; nothing was written for this claim."
        )
    run(_MERGE_CHUNK, source_id=plan.source_id, chunk_id=plan.chunk_id,
        properties=plan.chunk_properties, **common)
    by_id = {}
    for concept in plan.concepts:
        by_id[concept.concept_id] = concept
        run(
            _MERGE_CONCEPT.format(label=concept.label, id_property=concept.id_property),
            concept_id=concept.concept_id, name=concept.name,
            lexicon_version=plan.claim_properties["lexicon_version"], **common,
        )
    run(_MERGE_EVIDENCE.format(label=plan.evidence_label),
        chunk_id=plan.chunk_id,
        evidence_id=plan.evidence_properties["evidence_id"],
        properties=plan.evidence_properties,
        sentence_start=plan.sentence_span[0], sentence_end=plan.sentence_span[1],
        **common)
    subject_id, _, object_id = plan.triple
    subject, obj = by_id[subject_id], by_id[object_id]
    records = run(
        _MERGE_CLAIM.format(
            subject_label=subject.label, subject_id_property=subject.id_property,
            object_label=obj.label, object_id_property=obj.id_property,
            evidence_label=plan.evidence_label,
        ),
        subject_id=subject_id, object_id=object_id,
        evidence_id=plan.evidence_properties["evidence_id"],
        claim_id=plan.claim_id, properties=plan.claim_properties, **common,
    )
    if len(records) != 1:
        raise PromotionError(
            f"Claim {plan.claim_id} could not be linked to its concepts."
        )
    return counters


def _batch_id(prefix: str, batch_id: str | None) -> str:
    return batch_id or (
        f"{prefix}-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )


def _execute(db: Driver, work, items, *args) -> list:
    """Run work once per item, each in its own write transaction."""
    results = []
    try:
        with db.session() as session:
            for item in items:
                results.append(session.execute_write(work, item, *args))
    except (ServiceUnavailable, SessionExpired, AuthError) as exc:
        raise PromotionError(
            f"Neo4j is unavailable ({type(exc).__name__}); nothing further "
            "was written."
        ) from None
    except Neo4jError as exc:
        raise PromotionError(
            f"Neo4j rejected a transaction ({type(exc).__name__}); that "
            "transaction was rolled back and nothing further was written."
        ) from None
    return results


def promote(
    report: PromotionReport,
    driver: Driver | None = None,
    apply: bool = False,
    batch_id: str | None = None,
) -> PromotionReport:
    """Write the planned promotions when apply=True; otherwise do nothing.

    Each plan is one write transaction. Raises PromotionError if the
    database is unavailable or a transaction fails; plans committed before
    the failure stay committed (each is complete on its own).
    """
    report.batch_id = _batch_id("promo", batch_id)
    if not apply or not report.plans:
        return report

    db = driver if driver is not None else get_neo4j_driver()
    now = datetime.now(timezone.utc).isoformat()
    totals = dict.fromkeys(_COUNTER_FIELDS, 0)
    for counters in _execute(db, write_plan, report.plans, report.batch_id, now):
        for name, value in counters.items():
            totals[name] += value
    report.applied = True
    report.counters = totals
    return report


# --- retraction --------------------------------------------------------------

def plan_retractions(candidates: Iterable[CandidateClaim]) -> RetractionReport:
    """Find candidates that were approved once but are no longer trusted.

    Their graph claims (if they were promoted) should stop being used:
    the approval was withdrawn, the candidate was superseded, or its
    supporting passage changed (stale). Never touches the database.
    """
    report = RetractionReport()
    candidates = list(candidates)
    trusted = {c.claim_id for c in trusted_candidates(candidates)}
    for candidate in sorted(candidates, key=lambda c: c.claim_id):
        if candidate.claim_id in trusted:
            continue
        if candidate.predicate not in ONTOLOGY_MAPPING:
            continue  # never promotable, so never in the graph
        ever_approved = any(
            event.to_status == ReviewStatus.APPROVED
            for event in candidate.review_history
        )
        if not ever_approved:
            continue
        last = candidate.review_history[-1]
        if candidate.review_status != ReviewStatus.APPROVED:
            reason = f"approval withdrawn ({candidate.review_status.value})"
            if last.note:
                reason += f": {last.note}"
            by = last.reviewer
        elif candidate.stale:
            reason = "supporting passage changed (stale)"
            by = "system:stale"
        elif BLOCKING_UNCERTAINTY & set(candidate.uncertainty):
            reason = "re-extraction found the sentence does not state the relation"
            by = "system:structure_check"
        else:
            reason = "approval is not backed by a valid review event"
            by = "system:review_check"
        report.plans.append(
            RetractionPlan(
                candidate_id=candidate.claim_id,
                claim_id=f"CL-{candidate.claim_id}",
                reason=reason[:500],
                retracted_by=by,
            )
        )
    return report


_RETRACT_CLAIM = """
MATCH (claim:Claim {claim_id: $claim_id})
REMOVE claim:Claim
SET claim:RetractedClaim,
    claim.retracted_at = $now,
    claim.retraction_reason = $reason,
    claim.retracted_by = $retracted_by,
    claim.retraction_batch_id = $batch_id
RETURN claim.claim_id AS claim_id
"""
# Evidence is retracted only when it supports no remaining active claim.
_RETRACT_EVIDENCE = """
MATCH (e)-[:SUPPORTS]->(:RetractedClaim {claim_id: $claim_id})
WHERE (e:Evidence OR e:DescriptiveEvidence)
  AND NOT EXISTS { MATCH (e)-[:SUPPORTS]->(:Claim) }
REMOVE e:Evidence, e:DescriptiveEvidence
SET e:RetractedEvidence,
    e.retracted_at = $now,
    e.retraction_batch_id = $batch_id
RETURN count(e) AS evidence_retracted
"""


def write_retraction(tx, plan: RetractionPlan, batch_id: str, now: str) -> dict:
    found = list(tx.run(
        _RETRACT_CLAIM, claim_id=plan.claim_id, reason=plan.reason,
        retracted_by=plan.retracted_by, batch_id=batch_id, now=now,
    ))
    if not found:
        return {"claim_id": plan.claim_id, "found": False, "evidence": 0}
    records = list(tx.run(
        _RETRACT_EVIDENCE, claim_id=plan.claim_id, batch_id=batch_id, now=now,
    ))
    evidence = records[0]["evidence_retracted"] if records else 0
    return {"claim_id": plan.claim_id, "found": True, "evidence": evidence}


def retract(
    report: RetractionReport,
    driver: Driver | None = None,
    apply: bool = False,
    batch_id: str | None = None,
) -> RetractionReport:
    """Relabel withdrawn claims when apply=True; otherwise do nothing.

    Nothing is deleted. Each claim is one write transaction.
    """
    report.batch_id = _batch_id("retract", batch_id)
    if not apply or not report.plans:
        return report

    db = driver if driver is not None else get_neo4j_driver()
    now = datetime.now(timezone.utc).isoformat()
    for outcome in _execute(db, write_retraction, report.plans, report.batch_id, now):
        if outcome["found"]:
            report.retracted_claims.append(outcome["claim_id"])
            report.evidence_retracted += outcome["evidence"]
        else:
            report.not_in_graph.append(outcome["claim_id"])
    report.applied = True
    return report
