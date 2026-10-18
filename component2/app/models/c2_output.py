"""Structured Component 2 output contract.

Four numeric quantities appear in this contract and are NOT
interchangeable:

1. upstream.calibrated_confidence - Component 1 screening confidence,
   passed through as metadata only.
2. retrieval similarity - cosine similarity from the embedding model;
   retrieval relevance only.
3. ranking.score - experimental engineering ranking score from a
   provisional, unvalidated policy.
4. claim stored_confidence - whatever is stored on the Claim node
   (normally null; never generated here).

There is deliberately no overall medical confidence field.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.c1_input import RiskTier


OUTPUT_SCHEMA_VERSION = "c2-output/0.1.0"

SCORE_SEMANTICS = {
    "upstream.calibrated_confidence": (
        "Component 1 screening confidence. Upstream metadata only; not "
        "used as confidence in any Ayurvedic concept or candidate."
    ),
    "retrieval_similarity": (
        "Cosine similarity between embeddings of a query and an evidence "
        "chunk. Retrieval relevance only; not clinical confidence."
    ),
    "ranking.score": (
        "Experimental engineering ranking score from a provisional policy. "
        "Not clinically validated; does not predict safety or efficacy."
    ),
    "stored_confidence": (
        "Confidence stored on the Claim node, if any. Null until an "
        "explicit, evaluated scoring method exists. Never generated here."
    ),
}

DEFAULT_LIMITATIONS = [
    "Research decision-support output only; not a diagnosis or a "
    "prescription.",
    "Graph associations are not causal or efficacy claims.",
    "Candidates are not assessed for patient safety; Component 3 must "
    "perform safety assessment.",
    "Ranking and sufficiency rules are provisional prototypes pending "
    "supervisor and practitioner review.",
    "Results depend entirely on the curated knowledge graph and evidence "
    "corpus currently stored.",
]


class SufficiencyStatus(str, Enum):
    SUFFICIENT_FOR_REVIEW = "sufficient_for_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    UNVERIFIED_CLAIMS = "unverified_claims"
    OUT_OF_SCOPE = "out_of_scope"


class CandidateCategory(str, Enum):
    HERB = "Herb"
    FORMULATION = "Formulation"
    DIET = "Diet"
    LIFESTYLE = "Lifestyle"


class CandidateDisposition(str, Enum):
    FORWARD_FOR_SAFETY_ASSESSMENT = "forward_for_safety_assessment"
    WITHHELD_PENDING_REVIEW = "withheld_pending_review"


class UpstreamScreeningMetadata(BaseModel):
    risk_tier: RiskTier
    calibrated_confidence: float = Field(
        description=SCORE_SEMANTICS["upstream.calibrated_confidence"]
    )


class EvidenceReference(BaseModel):
    evidence_id: str
    relationship: Literal["SUPPORTS", "CONTRADICTS"]
    title: str | None = None
    source_name: str | None = None
    evidence_type: str | None = None
    section: str | None = None
    page: str | None = None
    citation: str | None = None
    source_url: str | None = None
    practitioner_verified: bool = False
    provenance_complete: bool
    missing_provenance: list[str] = Field(default_factory=list)


class ClaimStep(BaseModel):
    claim_id: str
    subject_id: str
    subject_type: str | None
    predicate: str
    object_id: str
    object_type: str | None
    statement: str | None
    verification_status: str
    stored_confidence: float | None = None
    supporting_evidence: list[EvidenceReference] = Field(
        default_factory=list
    )
    contradicting_evidence: list[EvidenceReference] = Field(
        default_factory=list
    )
    evidence_lookup_failed: bool = False
    retrieval_similarity: float | None = Field(
        default=None,
        description=(
            "Best similarity between this claim statement and its own "
            "supporting evidence chunks. "
            + SCORE_SEMANTICS["retrieval_similarity"]
        ),
    )


class CandidatePath(BaseModel):
    concept_ids: list[str]
    claims: list[ClaimStep]


class RankingBreakdown(BaseModel):
    score: float = Field(description=SCORE_SEMANTICS["ranking.score"])
    components: dict[str, float]
    policy_id: str
    label: Literal["experimental_ranking_score_not_clinical_confidence"] = (
        "experimental_ranking_score_not_clinical_confidence"
    )


class SufficiencyAssessment(BaseModel):
    status: SufficiencyStatus
    review_required: bool
    uncertainty_flags: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    policy_id: str


class ExplanationStatement(BaseModel):
    """One deterministic sentence with its provenance."""

    kind: str
    text: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    candidate_id: str
    category: CandidateCategory
    name: str | None
    rank: int
    ranking: RankingBreakdown
    disposition: CandidateDisposition
    paths: list[CandidatePath]
    claim_ids: list[str]
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    verification_statuses: list[str]
    conflict_flags: list[str] = Field(default_factory=list)
    sufficiency: SufficiencyAssessment
    rationale: list[ExplanationStatement] = Field(default_factory=list)


class SymptomMapping(BaseModel):
    symptom_id: str
    found: bool
    name: str | None = None
    indicates_claim_ids: list[str] = Field(default_factory=list)
    message: str | None = None


class InterpretedConcept(BaseModel):
    """A Roga/Dosha/Dhatu/TherapeuticPrinciple reached through claims.

    Reaching a concept is a graph association, not a diagnosis.
    """

    concept_id: str
    concept_type: str
    name: str | None = None
    via_claim_ids: list[str]
    verification_statuses: list[str]
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]


class RejectedPath(BaseModel):
    concept_ids: list[str]
    claim_ids: list[str]
    reason: str


class RetrievedEvidenceItem(BaseModel):
    chunk_id: str
    evidence_id: str
    similarity: float = Field(
        description=SCORE_SEMANTICS["retrieval_similarity"]
    )
    below_threshold: bool
    linked_to_traversed_claim: bool
    title: str | None = None
    source_name: str | None = None
    evidence_type: str | None = None
    section: str | None = None
    page: str | None = None
    citation: str | None = None
    source_url: str | None = None


class RetrievalInfo(BaseModel):
    mode: Literal["neural_embedding", "unavailable", "not_run"]
    model_id: str | None = None
    query_count: int = 0
    top_k: int | None = None
    min_similarity: float | None = None
    indexed_chunks: int = 0
    error: str | None = None


class Abstention(BaseModel):
    abstain: bool
    reasons: list[str] = Field(default_factory=list)
    explanation: str | None = None


class Component2Output(BaseModel):
    schema_version: str = OUTPUT_SCHEMA_VERSION
    request_id: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    upstream: UpstreamScreeningMetadata
    input_symptom_ids: list[str]
    symptom_mappings: list[SymptomMapping]
    interpretation: list[InterpretedConcept]
    candidates: list[Candidate]
    rejected_paths: list[RejectedPath] = Field(default_factory=list)
    retrieval: RetrievalInfo
    retrieved_evidence: list[RetrievedEvidenceItem] = Field(
        default_factory=list
    )
    sufficiency_status: SufficiencyStatus
    uncertainty_flags: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    review_required: bool
    abstention: Abstention
    explanation: list[ExplanationStatement] = Field(default_factory=list)
    traversal_truncated: bool = False
    limitations: list[str] = Field(
        default_factory=lambda: list(DEFAULT_LIMITATIONS)
    )
    score_semantics: dict[str, str] = Field(
        default_factory=lambda: dict(SCORE_SEMANTICS)
    )
    medical_conclusion: None = None
