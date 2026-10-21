"""Models for candidate claims, concept mentions, reviews and conflicts."""

from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge_ingestion.models import EvidenceCategory


class ReviewStatus(str, Enum):
    # Extracted by software; nobody has looked at it.
    CANDIDATE = "candidate"
    # Reviewed, but the reviewer could not decide.
    UNCERTAIN = "uncertain"
    # Reviewed; plausible but needs corroborating sources.
    NEEDS_MORE_SOURCES = "needs_more_sources"
    # A named reviewer confirmed the source states this.
    APPROVED = "approved"
    REJECTED = "rejected"
    # Replaced by another candidate (for example a better translation).
    SUPERSEDED = "superseded"


class ReviewerRole(str, Enum):
    PRACTITIONER = "practitioner"
    RESEARCHER = "researcher"


class ConflictKind(str, Enum):
    # One source indicates X for Y while another cautions against it.
    INDICATION_VS_CAUTION = "indication_vs_caution"
    # The same relation is stated in one passage and negated in another.
    POLARITY = "polarity"


class ConflictStatus(str, Enum):
    OPEN = "open"
    # A reviewer has seen the conflict; it is not thereby resolved.
    ACKNOWLEDGED = "acknowledged"


# Candidate predicates with allowed subject and object concept types. They
# describe what a passage states, and are deliberately not the ontology
# predicates in app.ontology.relationships: a text saying "herb X is useful
# in pandu" skips the TherapeuticPrinciple step the ontology requires.
CANDIDATE_PREDICATES = MappingProxyType(
    {
        "HAS_SYMPTOM": (frozenset({"Roga"}), frozenset({"Symptom"})),
        "TRADITIONALLY_INDICATED_FOR": (
            frozenset({"Herb", "Formulation"}),
            frozenset({"Roga", "Symptom"}),
        ),
        "HAS_CAUTION": (
            frozenset({"Herb", "Formulation"}),
            frozenset({"Roga", "Symptom"}),
        ),
        "ASSOCIATED_WITH_DOSHA": (frozenset({"Roga"}), frozenset({"Dosha"})),
        "AFFECTS_DHATU": (frozenset({"Roga"}), frozenset({"Dhatu"})),
        "CONTAINS_INGREDIENT": (
            frozenset({"Formulation"}),
            frozenset({"Herb"}),
        ),
    }
)

# Candidate predicates that correspond directly to an ontology predicate,
# as (ontology predicate, inverted). Others have no direct mapping and need
# a reviewer to model them, e.g. through a TherapeuticPrinciple.
ONTOLOGY_MAPPING = MappingProxyType(
    {
        "HAS_SYMPTOM": ("INDICATES", True),
        "ASSOCIATED_WITH_DOSHA": ("ASSOCIATED_WITH_DOSHA", False),
        "AFFECTS_DHATU": ("AFFECTS_DHATU", False),
        # Ontology v1.1 descriptive predicate (not traversed by reasoning).
        "CONTAINS_INGREDIENT": ("CONTAINS_INGREDIENT", False),
    }
)

# Uncertainty notes attached by the extractor.
NEGATION_CUE = "negation_cue_in_sentence"
DOSAGE_STATEMENT = "dosage_statement_in_sentence"
AMBIGUOUS_TERM = "ambiguous_term"
COMPOUND_MATCH = "matched_inside_compound_word"
SOURCE_QUALITY_FLAGGED = "source_text_quality_flagged"
EVIDENCE_CATEGORY_UNKNOWN = "evidence_category_not_declared"
LIST_CONTEXT = "list_context"
# The sentence lists both concepts but does not relate them (see
# app.knowledge_candidates.structure). Blocks approval and promotion.
STRUCTURE_UNSUPPORTED = "relation_not_supported_by_sentence_structure"

# The sentence ties the statement to a historical period or to specific
# proportions ('during the period of ...', 'two parts of ...', 'equal
# parts'). Not blocking: the statement may be valid, but only with that
# qualifier, which the supporting sentence carries verbatim.
QUALIFIED_STATEMENT = "period_or_proportion_qualifier"

# Uncertainty notes that make a candidate unusable as knowledge. A reviewer
# can reject it or ask for more sources, but cannot approve it.
BLOCKING_UNCERTAINTY = frozenset({STRUCTURE_UNSUPPORTED})


class ConceptRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(min_length=1)
    concept_type: str = Field(min_length=1)
    label: str = Field(min_length=1)


class ConceptMention(BaseModel):
    """A lexicon term found in a chunk's normalized text."""

    model_config = ConfigDict(extra="forbid")

    concept: ConceptRef
    surface: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    ambiguous: bool = False
    compound: bool = False


class ChunkMentions(BaseModel):
    """Concept occurrences in one chunk (a text index, not claims)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    mentions: list[ConceptMention]


class SupportingPassage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    sentence: str = Field(
        min_length=1,
        description="Sentence from the chunk's normalized text.",
    )
    sentence_start: int = Field(ge=0)
    sentence_end: int = Field(ge=0)
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    section_heading: str | None = None
    verse_numbers: list[str] = Field(default_factory=list)
    # Element IDs (e.g. TEI verse references) of the whole chunk the
    # sentence came from; the sentence lies within one of them.
    citation_refs: list[str] = Field(default_factory=list)
    primary_script: str
    declared_source_language: str | None = None
    declared_translation_language: str | None = None
    chunk_quality_flags: list[str] = Field(default_factory=list)


class ReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewer: str = Field(min_length=1)
    reviewer_role: ReviewerRole
    from_status: ReviewStatus
    to_status: ReviewStatus
    note: str | None = None
    additional_source_ids: list[str] = Field(default_factory=list)
    superseded_by: str | None = None
    acknowledged_conflict_ids: list[str] = Field(default_factory=list)


class CandidateClaim(BaseModel):
    """A relation a source passage appears to state, awaiting review.

    extraction_confidence is None: the rule-based extractor has no
    meaningful probability to report, and none is invented.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    subject: ConceptRef
    predicate: str
    object: ConceptRef
    cue: str = Field(description="Cue phrase that triggered extraction.")
    passage: SupportingPassage
    evidence_category: EvidenceCategory | None = None
    extraction_method: str
    extractor_version: str
    lexicon_version: str
    extraction_confidence: float | None = None
    uncertainty: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.CANDIDATE
    review_history: list[ReviewEvent] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)
    stale: bool = Field(
        default=False,
        description=(
            "True when the latest extraction no longer produced this "
            "candidate (its chunk changed or was removed). Kept, not deleted."
        ),
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode="after")
    def _check_predicate(self) -> "CandidateClaim":
        if self.predicate not in CANDIDATE_PREDICATES:
            raise ValueError(f"Unknown candidate predicate {self.predicate!r}.")
        subjects, objects = CANDIDATE_PREDICATES[self.predicate]
        if self.subject.concept_type not in subjects:
            raise ValueError(
                f"{self.predicate} does not allow subject type "
                f"{self.subject.concept_type!r}."
            )
        if self.object.concept_type not in objects:
            raise ValueError(
                f"{self.predicate} does not allow object type "
                f"{self.object.concept_type!r}."
            )
        if self.extraction_confidence is not None and not (
            0.0 <= self.extraction_confidence <= 1.0
        ):
            raise ValueError("extraction_confidence must be within [0, 1].")
        self._check_review_history()
        return self

    def _check_review_history(self) -> None:
        """The status must be exactly what the review history produced.

        Rejects hand-edited records such as an 'approved' status without an
        approval event, events belonging to another candidate, or a broken
        chain of from/to statuses.
        """
        expected = ReviewStatus.CANDIDATE
        for event in self.review_history:
            if event.claim_id != self.claim_id:
                raise ValueError(
                    f"Review event for {event.claim_id} attached to {self.claim_id}."
                )
            if event.from_status != expected:
                raise ValueError(
                    f"Review history of {self.claim_id} is not a continuous "
                    f"chain ({event.from_status.value} after {expected.value})."
                )
            expected = event.to_status
        if self.review_status != expected:
            raise ValueError(
                f"{self.claim_id} has status {self.review_status.value} but its "
                f"review history ends in {expected.value}."
            )

    @property
    def relation_key(self) -> tuple[str, str, str]:
        return (self.subject.concept_id, self.predicate, self.object.concept_id)


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    kind: ConflictKind
    claim_ids: list[str] = Field(min_length=2)
    description: str
    status: ConflictStatus = ConflictStatus.OPEN
    acknowledged_by: list[str] = Field(default_factory=list)
