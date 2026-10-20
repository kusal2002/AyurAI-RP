"""Reviewer-modelled claims: ontology claims a person writes from a passage.

Rule-based extraction can only produce relations stated by a cue phrase
next to two lexicon terms. Treatment knowledge is modelled in the ontology
as Roga -> SUGGESTS_PRINCIPLE -> TherapeuticPrinciple -> USES_HERB (and
USES_FORMULATION / RECOMMENDS_DIET / RECOMMENDS_LIFESTYLE). Such claims
need a person to decide what the passage states, so they are authored
here rather than extracted (Stage E design §6, decision D4).

A modelled claim is accepted only when:

- its predicate is a reasoning predicate of ontology v1.0
  (`RELATIONSHIP_RULES`); descriptive predicates are not modelled here;
- the subject and object concept types satisfy that predicate's rule;
- the quoted text occurs exactly once in the cited chunk's normalized
  text, so the evidence sentence is copied from the source, never typed
  in, and its span is exact;
- a named reviewer with a role and a rationale note created it.

The record keeps both the reviewer's paraphrase (`statement`) and the
verbatim quote. Nothing here touches Neo4j: promotion
(`app.db.source_repository.plan_modelled_promotions`) applies the same
source-metadata and provenance checks as for candidates, and writes only
with `--apply`. Withdrawal never deletes a record; it appends an event and
makes the graph claim retractable.

A modelled claim records a reviewer's reading of a traditional source.
It is not a clinical efficacy finding.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.schema import NODE_IDENTIFIERS
from app.knowledge_candidates.models import ConceptRef, ReviewerRole, SupportingPassage
from app.knowledge_ingestion.models import TextChunk
from app.ontology.relationships import RELATIONSHIP_RULES, validate_relationship


MODELLED_ID_PREFIX = "mod-"
CONCEPT_TYPES = frozenset(set(NODE_IDENTIFIERS) - {"Evidence", "Claim"})


class ModelledClaimError(ValueError):
    """The modelled claim is invalid; the message names the problem."""


class ModelledStatus(str, Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class ModelledEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelled_id: str
    action: ModelledStatus
    reviewer: str = Field(min_length=1)
    reviewer_role: ReviewerRole
    note: str = Field(min_length=1)
    at: datetime


class ModelledClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelled_id: str
    subject: ConceptRef
    predicate: str
    object: ConceptRef
    statement: str = Field(min_length=1, max_length=1000, description=(
        "The reviewer's wording of what the passage states."
    ))
    passage: SupportingPassage
    models_candidate_id: str | None = Field(default=None, description=(
        "Candidate this claim models, e.g. a TRADITIONALLY_INDICATED_FOR "
        "candidate that has no direct ontology mapping."
    ))
    status: ModelledStatus
    history: list[ModelledEvent] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self):
        if any(event.modelled_id != self.modelled_id for event in self.history):
            raise ValueError("history contains events for another modelled claim")
        if self.history[0].action != ModelledStatus.ACTIVE:
            raise ValueError("history must start with the creation event")
        if self.history[-1].action != self.status:
            raise ValueError("status does not match the latest history event")
        return self

    @property
    def created(self) -> ModelledEvent:
        return self.history[0]


def _concept(spec: str) -> ConceptRef:
    """Parse 'Type:ID:Label' (label may contain ':')."""
    parts = spec.split(":", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ModelledClaimError(
            f"Concept {spec!r} must be written as Type:ID:Label, "
            "e.g. TherapeuticPrinciple:TP-PANDU-VIRECANA:Purgation in pandu."
        )
    concept_type, concept_id, label = (part.strip() for part in parts)
    if concept_type not in CONCEPT_TYPES:
        raise ModelledClaimError(
            f"Concept type {concept_type!r} is not one of {sorted(CONCEPT_TYPES)}."
        )
    return ConceptRef(concept_id=concept_id, concept_type=concept_type, label=label)


def locate_quote(chunk: TextChunk, quote: str) -> tuple[int, int]:
    """Span of quote in the chunk's normalized text; it must occur once."""
    quote = quote.strip()
    if len(quote) < 10:
        raise ModelledClaimError("The quote must be at least 10 characters.")
    first = chunk.text.find(quote)
    if first < 0:
        raise ModelledClaimError(
            f"The quote does not occur in chunk {chunk.chunk_id}. Copy it from "
            "the chunk's normalized text exactly (including diacritics)."
        )
    if chunk.text.find(quote, first + 1) >= 0:
        raise ModelledClaimError(
            "The quote occurs more than once in the chunk; quote a longer, "
            "unique passage."
        )
    return first, first + len(quote)


def make_modelled_id(subject: str, predicate: str, obj: str, chunk_id: str,
                     span: tuple[int, int]) -> str:
    payload = json.dumps([subject, predicate, obj, chunk_id, list(span)],
                         separators=(",", ":"))
    return MODELLED_ID_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def model_claim(
    chunk: TextChunk,
    *,
    subject: str,
    predicate: str,
    object: str,
    quote: str,
    statement: str,
    reviewer: str,
    reviewer_role: ReviewerRole,
    note: str,
    models_candidate_id: str | None = None,
    now: datetime | None = None,
) -> ModelledClaim:
    """Validate and build a new modelled claim (not stored yet)."""
    if not reviewer.strip():
        raise ModelledClaimError("A named reviewer is required.")
    if not note or not note.strip():
        raise ModelledClaimError(
            "A note explaining how the passage supports this claim is required."
        )
    if not statement.strip():
        raise ModelledClaimError("A statement is required.")
    if predicate not in RELATIONSHIP_RULES:
        raise ModelledClaimError(
            f"Predicate {predicate!r} is not a reasoning predicate; allowed: "
            + ", ".join(sorted(RELATIONSHIP_RULES))
        )
    subject_ref, object_ref = _concept(subject), _concept(object)
    if subject_ref.concept_id == object_ref.concept_id:
        raise ModelledClaimError("Subject and object must differ.")
    try:
        validate_relationship(predicate, subject_ref.concept_type, object_ref.concept_type)
    except ValueError as exc:
        raise ModelledClaimError(str(exc)) from None

    start, end = locate_quote(chunk, quote)
    passage = SupportingPassage(
        chunk_id=chunk.chunk_id,
        source_id=chunk.source_id,
        sentence=chunk.text[start:end],
        sentence_start=start,
        sentence_end=end,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        section_heading=chunk.section_heading,
        verse_numbers=chunk.verse_numbers,
        citation_refs=chunk.citation_refs,
        primary_script=chunk.primary_script,
        declared_source_language=chunk.declared_source_language,
        declared_translation_language=chunk.declared_translation_language,
        chunk_quality_flags=chunk.quality_flags,
    )
    modelled_id = make_modelled_id(
        subject_ref.concept_id, predicate, object_ref.concept_id,
        chunk.chunk_id, (start, end),
    )
    event = ModelledEvent(
        modelled_id=modelled_id, action=ModelledStatus.ACTIVE,
        reviewer=reviewer.strip(), reviewer_role=reviewer_role,
        note=note.strip(), at=now or datetime.now(timezone.utc),
    )
    return ModelledClaim(
        modelled_id=modelled_id, subject=subject_ref, predicate=predicate,
        object=object_ref, statement=statement.strip(), passage=passage,
        models_candidate_id=models_candidate_id, status=ModelledStatus.ACTIVE,
        history=[event],
    )


def withdraw(claim: ModelledClaim, reviewer: str, reviewer_role: ReviewerRole,
             note: str, now: datetime | None = None) -> tuple[ModelledClaim, ModelledEvent]:
    if claim.status == ModelledStatus.WITHDRAWN:
        raise ModelledClaimError(f"{claim.modelled_id} is already withdrawn.")
    if not reviewer.strip() or not note.strip():
        raise ModelledClaimError("Withdrawal needs a named reviewer and a note.")
    event = ModelledEvent(
        modelled_id=claim.modelled_id, action=ModelledStatus.WITHDRAWN,
        reviewer=reviewer.strip(), reviewer_role=reviewer_role,
        note=note.strip(), at=now or datetime.now(timezone.utc),
    )
    updated = claim.model_copy(update={
        "status": ModelledStatus.WITHDRAWN, "history": [*claim.history, event],
    })
    return ModelledClaim.model_validate(updated.model_dump()), event


class ModelledStore:
    """modelled_claims.jsonl (current state) + modelled_log.jsonl (append-only)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @property
    def claims_path(self) -> Path:
        return self.root / "modelled_claims.jsonl"

    @property
    def log_path(self) -> Path:
        return self.root / "modelled_log.jsonl"

    def load(self) -> dict[str, ModelledClaim]:
        if not self.claims_path.is_file():
            return {}
        claims = {}
        with self.claims_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    claim = ModelledClaim.model_validate_json(line)
                    claims[claim.modelled_id] = claim
        return claims

    def load_log(self) -> list[ModelledEvent]:
        if not self.log_path.is_file():
            return []
        with self.log_path.open(encoding="utf-8") as handle:
            return [ModelledEvent.model_validate_json(l) for l in handle if l.strip()]

    def _append(self, event: ModelledEvent) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(event.model_dump_json() + "\n")

    def _save(self, claims: dict[str, ModelledClaim]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.claims_path.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for claim in sorted(claims.values(), key=lambda c: c.modelled_id):
                handle.write(claim.model_dump_json() + "\n")
        os.replace(temporary, self.claims_path)

    def add(self, claim: ModelledClaim) -> None:
        claims = self.load()
        if claim.modelled_id in claims:
            raise ModelledClaimError(
                f"{claim.modelled_id} already exists for this subject, predicate, "
                "object and passage."
            )
        self._append(claim.created)
        claims[claim.modelled_id] = claim
        self._save(claims)

    def withdraw(self, modelled_id: str, reviewer: str, role: ReviewerRole,
                 note: str) -> ModelledClaim:
        claims = self.load()
        if modelled_id not in claims:
            raise ModelledClaimError(f"Unknown modelled claim {modelled_id}.")
        updated, event = withdraw(claims[modelled_id], reviewer, role, note)
        self._append(event)
        claims[modelled_id] = updated
        self._save(claims)
        return updated
