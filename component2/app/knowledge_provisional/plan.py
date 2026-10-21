"""Validate provisional claim drafts against the extracted sources and plan writes.

Input: a draft dataset (e.g. knowledge/provisional/pandu_traditional_v1.json)
written with AI assistance from source passages. Every claim and reference
statement must quote its source exactly: the quote is located in the
extracted passages of the named source (whitespace-normalized NFC text),
optionally checked against an encoded verse ID, and then tied to the
earliest source chunk that contains it. A quote that cannot be found, or
that is ambiguous, is rejected, never "repaired".

Nothing here touches Neo4j. The plan states exactly what would be written.

Isolation from the approved pathway (docs/knowledge_graph_schema.md §10):

- claims become `:ProvisionalClaim` (never `:Claim`), evidence becomes
  `:ProvisionalEvidence` (never `:Evidence`);
- links use `PROVISIONAL_SUBJECT_OF`, `PROVISIONAL_OBJECT_OF`,
  `PROVISIONALLY_SUPPORTS` and `PROVISIONALLY_QUALIFIES`, which no
  approved query traverses;
- every claim has `verification_status = "unverified"` and
  `knowledge_status = "provisional"`; the planner refuses any other status.
"""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.schema import NODE_IDENTIFIERS
from app.db.source_repository import (
    EVIDENCE_TYPE_BY_CATEGORY,
    _CHUNK_PROPERTIES,
    _drop_none,
    _source_properties,
)
from app.knowledge_ingestion.models import ExtractedPassage, SourceRecord, TextChunk
from app.knowledge_ingestion.service import chunks_path, load_chunks, load_extraction_output
from app.models.evidence import EvidenceRecord
from app.ontology.evidence_validation import validate_evidence_provenance
from app.ontology.relationships import (
    DESCRIPTIVE_RELATIONSHIP_RULES,
    validate_relationship,
)

PLANNER_VERSION = "1"
ALLOWED_EXTRACTION_METHODS = {"ai_assisted_draft"}
EVIDENCE_ROLES = {"claim_support", "translation_support", "modern_reference"}
CONCEPT_TYPES = set(NODE_IDENTIFIERS) - {"Evidence", "Claim"}
MIN_QUOTE_CHARS = 12


def norm(text: str) -> str:
    """NFC with whitespace runs collapsed: the matching form for quotes."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def _hash(*parts: Any) -> str:
    payload = json.dumps(list(parts), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def provisional_claim_id(subject: str, predicate: str, obj: str) -> str:
    return "PCL-" + _hash(subject, predicate, obj)


def provisional_evidence_id(source_id: str, passage_index: int, start: int, end: int) -> str:
    return "PEV-" + _hash(source_id, passage_index, start, end)


@dataclass
class SourceBundle:
    record: SourceRecord
    passages: list[ExtractedPassage]
    norm_passages: list[str]
    chunks: list[TextChunk]
    norm_chunks: list[str]


@dataclass
class PlannedEvidence:
    evidence_id: str
    role: str
    source_id: str
    chunk_id: str
    passage_index: int
    span: tuple[int, int]
    properties: dict[str, Any]


@dataclass
class PlannedClaim:
    claim_id: str
    key: str
    triple: tuple[str, str, str]
    descriptive: bool
    properties: dict[str, Any]
    evidence_ids: list[str]
    qualifier_ids: list[str]


@dataclass
class ProvisionalPlan:
    dataset_id: str
    dataset_version: str
    planner_version: str = PLANNER_VERSION
    planned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    concepts: dict[str, dict[str, Any]] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: dict[str, PlannedEvidence] = field(default_factory=dict)
    claims: dict[str, PlannedClaim] = field(default_factory=dict)
    rejected: list[dict[str, str]] = field(default_factory=list)
    duplicates: list[dict[str, str]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        claims = list(self.claims.values())
        ev = list(self.evidence.values())
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "planner_version": self.planner_version,
            "claims": len(claims),
            "claims_by_category": dict(Counter(c.properties["claim_category"] for c in claims)),
            "claims_by_predicate": dict(Counter(c.triple[1] for c in claims)),
            "descriptive_claims": sum(c.descriptive for c in claims),
            "claims_with_qualification": sum(bool(c.qualifier_ids) for c in claims),
            "claims_with_independent_sources": dict(Counter(
                len({self.evidence[e].source_id for e in c.evidence_ids if self.evidence[e].role == "claim_support"})
                for c in claims
            )),
            "evidence": len(ev),
            "evidence_by_role": dict(Counter(e.role for e in ev)),
            "evidence_by_source": dict(Counter(e.source_id for e in ev)),
            "evidence_by_script": dict(Counter(e.properties.get("primary_script") for e in ev)),
            "evidence_by_type": dict(Counter(e.properties["evidence_type"] for e in ev)),
            "concepts": len(self.concepts),
            "concepts_by_type": dict(Counter(c["label"] for c in self.concepts.values())),
            "sources": len(self.sources),
            "source_chunks": len(self.chunks),
            "rejected": len(self.rejected),
            "duplicates": len(self.duplicates),
            "relationships": {
                "PROVISIONAL_SUBJECT_OF": len(claims),
                "PROVISIONAL_OBJECT_OF": len(claims),
                "PROVISIONALLY_SUPPORTS": sum(len(c.evidence_ids) for c in claims),
                "PROVISIONALLY_QUALIFIES": sum(len(c.qualifier_ids) for c in claims),
                "FROM_CHUNK": len(ev),
                "PART_OF": len(self.chunks),
            },
        }


class _Sources:
    def __init__(self, extracted_dir: Path):
        self.extracted_dir = Path(extracted_dir)
        self._cache: dict[str, SourceBundle | None] = {}

    def get(self, source_id: str) -> SourceBundle | None:
        if source_id in self._cache:
            return self._cache[source_id]
        summary = self.extracted_dir / f"{source_id}.extraction.json"
        bundle = None
        if summary.is_file():
            record, passages = load_extraction_output(summary)
            chunk_file = chunks_path(self.extracted_dir, source_id)
            chunks = load_chunks(chunk_file) if chunk_file.is_file() else []
            bundle = SourceBundle(
                record, passages, [norm(p.text) for p in passages],
                chunks, [norm(c.text) for c in chunks],
            )
        self._cache[source_id] = bundle
        return bundle


def _source_problem(record: SourceRecord) -> str | None:
    metadata = record.metadata
    if not metadata.title:
        return "source has no curated title (.meta.json sidecar)"
    if metadata.evidence_category is None:
        return "source evidence_category not declared"
    if metadata.evidence_category not in EVIDENCE_TYPE_BY_CATEGORY:
        return f"evidence_category {metadata.evidence_category.value!r} has no evidence type"
    if not metadata.usage_notes:
        return "source has no licence/usage notes"
    return None


def _locate(bundle: SourceBundle, quote: str, element_id: str | None):
    """Return (passage_index, start, end, chunk) or raise ValueError."""
    q = norm(quote)
    if len(q) < MIN_QUOTE_CHARS:
        raise ValueError(f"quote shorter than {MIN_QUOTE_CHARS} characters")
    matches = []
    for passage, text in zip(bundle.passages, bundle.norm_passages):
        if element_id and passage.location.element_id != element_id:
            continue
        start = text.find(q)
        if start < 0:
            continue
        if text.find(q, start + 1) >= 0:
            raise ValueError("quote occurs more than once in one passage")
        matches.append((passage.passage_index, start, start + len(q)))
    if not matches:
        where = f" in passage {element_id}" if element_id else ""
        raise ValueError(f"quote not found{where}")
    if len(matches) > 1:
        raise ValueError(f"quote is ambiguous ({len(matches)} passages); quote more text or give element_id")
    passage_index, start, end = matches[0]
    for chunk, text in zip(bundle.chunks, bundle.norm_chunks):
        if q in text and any(s.passage_index == passage_index for s in chunk.passage_spans):
            return passage_index, start, end, chunk
    raise ValueError("no chunk contains the quote (re-chunk the source)")


def _evidence_properties(bundle: SourceBundle, chunk: TextChunk, passage_index: int,
                         quote: str, role: str, item: dict, dataset: dict) -> dict[str, Any]:
    record = bundle.record
    metadata = record.metadata
    passage = next(p for p in bundle.passages if p.passage_index == passage_index)
    location = passage.location
    citation = location.element_id or (
        f"lines {location.line_start}-{location.line_end}" if location.line_start else None
    )
    evidence = EvidenceRecord(
        evidence_id="PEV-check",
        title=metadata.title,
        source_name=f"{metadata.title} ({metadata.edition})" if metadata.edition else metadata.title,
        evidence_type=EVIDENCE_TYPE_BY_CATEGORY[metadata.evidence_category],
        section=location.section_heading or chunk.section_heading or None,
        page=location.printed_page,
        text=norm(quote),
        citation=citation,
    )
    validate_evidence_provenance(evidence)
    props = _drop_none(evidence.model_dump(mode="json"))
    props.pop("evidence_id", None)
    props.pop("concepts", None)
    props.update(_drop_none({
        "evidence_role": role,
        "knowledge_status": "provisional",
        "review_status": dataset["review_status"],
        "extraction_method": dataset["extraction_method"],
        "dataset_id": dataset["dataset_id"],
        "dataset_version": dataset["dataset_version"],
        "source_id": record.source_id,
        "chunk_id": chunk.chunk_id,
        "passage_index": passage_index,
        "element_id": location.element_id,
        "line_start": location.line_start,
        "line_end": location.line_end,
        "primary_script": chunk.primary_script,
        "source_language": metadata.source_language,
        "translation_language": metadata.translation_language,
        "evidence_category": metadata.evidence_category.value,
        "licence_note": metadata.usage_notes,
        "category": item.get("category"),
        "topics": item.get("topics") or None,
        "uncertainty_notes": item.get("uncertainty") or None,
    }))
    return props


def plan_dataset(dataset_path: str | Path, extracted_dir: str | Path) -> ProvisionalPlan:
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    if dataset.get("extraction_method") not in ALLOWED_EXTRACTION_METHODS:
        raise ValueError("dataset extraction_method must be one of " + ", ".join(sorted(ALLOWED_EXTRACTION_METHODS)))
    plan = ProvisionalPlan(dataset["dataset_id"], str(dataset["dataset_version"]),
                           gaps=list(dataset.get("known_gaps", [])))
    sources = _Sources(Path(extracted_dir))

    for concept in dataset["concepts"]:
        if concept["type"] not in CONCEPT_TYPES:
            plan.rejected.append({"item": concept["id"], "reason": f"unknown concept type {concept['type']}"})
            continue
        if concept["id"] in plan.concepts:
            plan.duplicates.append({"item": concept["id"], "reason": "duplicate concept id"})
            continue
        plan.concepts[concept["id"]] = {
            "label": concept["type"],
            "id_property": NODE_IDENTIFIERS[concept["type"]],
            "properties": _drop_none({
                "name": concept["name"],
                "aliases": concept.get("aliases") or [],
                "botanical_name_as_stated": concept.get("botanical_name_as_stated"),
                "botanical_name_source": concept.get("botanical_name_source"),
                "botanical_name_verified": False if concept.get("botanical_name_as_stated") else None,
            }),
        }

    def add_evidence(item: dict, role: str, owner: str) -> str | None:
        bundle = sources.get(item["source_id"])
        if bundle is None:
            plan.rejected.append({"item": owner, "reason": f"source {item['source_id']} not extracted"})
            return None
        problem = _source_problem(bundle.record)
        if problem:
            plan.rejected.append({"item": owner, "reason": f"{item['source_id']}: {problem}"})
            return None
        try:
            passage_index, start, end, chunk = _locate(bundle, item["quote"], item.get("element_id"))
            props = _evidence_properties(bundle, chunk, passage_index, item["quote"], role, item, dataset)
        except ValueError as exc:
            plan.rejected.append({"item": owner, "reason": f"{item['source_id']} {item.get('element_id') or ''}: {exc}".strip()})
            return None
        evidence_id = provisional_evidence_id(item["source_id"], passage_index, start, end)
        existing = plan.evidence.get(evidence_id)
        if existing is not None and existing.role != role:
            plan.rejected.append({"item": owner, "reason": f"{item['source_id']}: same passage span already used as {existing.role}"})
            return None
        if evidence_id not in plan.evidence:
            plan.evidence[evidence_id] = PlannedEvidence(
                evidence_id, role, item["source_id"], chunk.chunk_id, passage_index, (start, end), props,
            )
        plan.sources.setdefault(item["source_id"], {
            "content_sha256": bundle.record.content_sha256,
            "properties": _source_properties(bundle.record),
        })
        plan.chunks.setdefault(chunk.chunk_id, {
            "source_id": item["source_id"],
            "properties": _drop_none({k: getattr(chunk, k) for k in _CHUNK_PROPERTIES}),
        })
        return evidence_id

    reference_ids: dict[str, str] = {}
    for item in dataset.get("reference_evidence", []):
        evidence_id = add_evidence(item, "modern_reference", item["key"])
        if evidence_id:
            reference_ids[item["key"]] = evidence_id

    seen_keys: set[str] = set()
    for item in dataset["claims"]:
        key = item["key"]
        if key in seen_keys:
            plan.duplicates.append({"item": key, "reason": "duplicate claim key"})
            continue
        seen_keys.add(key)
        subject, predicate, obj = item["subject"], item["predicate"], item["object"]
        missing = [c for c in (subject, obj) if c not in plan.concepts]
        if missing:
            plan.rejected.append({"item": key, "reason": f"undeclared concept(s): {', '.join(missing)}"})
            continue
        try:
            validate_relationship(predicate, plan.concepts[subject]["label"],
                                  plan.concepts[obj]["label"], allow_descriptive=True)
        except ValueError as exc:
            plan.rejected.append({"item": key, "reason": f"ontology: {exc}"})
            continue
        claim_id = provisional_claim_id(subject, predicate, obj)
        if claim_id in plan.claims:
            plan.duplicates.append({"item": key, "reason": f"same triple as {plan.claims[claim_id].key}"})
            continue
        evidence_ids = []
        for ev in item["evidence"]:
            role = "translation_support" if ev.get("role") == "translation" else "claim_support"
            evidence_id = add_evidence(ev, role, key)
            if evidence_id and evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
        if not any(plan.evidence[e].role == "claim_support" for e in evidence_ids):
            plan.rejected.append({"item": key, "reason": "no located primary-source quote; claim not planned"})
            continue
        qualifiers = []
        for ref_key in item.get("qualified_by_reference", []):
            if ref_key in reference_ids:
                qualifiers.append(reference_ids[ref_key])
            else:
                plan.rejected.append({"item": key, "reason": f"qualifying reference {ref_key} not planned"})
        descriptive = predicate in DESCRIPTIVE_RELATIONSHIP_RULES
        plan.claims[claim_id] = PlannedClaim(
            claim_id, key, (subject, predicate, obj), descriptive,
            _drop_none({
                "claim_id": claim_id,
                "claim_key": key,
                "subject_id": subject,
                "predicate": predicate,
                "object_id": obj,
                "statement": item["statement"],
                "claim_category": item["category"],
                # Never anything else on this pathway (see module docstring).
                "verification_status": "unverified",
                "knowledge_status": "provisional",
                "review_status": dataset["review_status"],
                "extraction_method": dataset["extraction_method"],
                "dataset_id": dataset["dataset_id"],
                "dataset_version": str(dataset["dataset_version"]),
                "drafted_on": dataset.get("drafted_on"),
                "planner_version": PLANNER_VERSION,
                "descriptive": descriptive,
                "uncertainty_notes": item.get("uncertainty") or None,
            }),
            evidence_ids, qualifiers,
        )
    return plan


def plan_to_dict(plan: ProvisionalPlan) -> dict[str, Any]:
    return {
        "summary": plan.summary(),
        "rejected": plan.rejected,
        "duplicates": plan.duplicates,
        "known_gaps": plan.gaps,
        "claims": [
            {"claim_id": c.claim_id, "key": c.key, "triple": list(c.triple),
             "category": c.properties["claim_category"],
             "evidence": [{"evidence_id": e, "role": plan.evidence[e].role,
                           "source_id": plan.evidence[e].source_id,
                           "citation": plan.evidence[e].properties.get("citation"),
                           "quote": plan.evidence[e].properties["text"]} for e in c.evidence_ids],
             "qualified_by": c.qualifier_ids}
            for c in plan.claims.values()
        ],
        "reference_evidence": [
            {"evidence_id": e.evidence_id, "source_id": e.source_id, "category": e.properties.get("category"),
             "quote": e.properties["text"]}
            for e in plan.evidence.values() if e.role == "modern_reference"
        ],
    }
