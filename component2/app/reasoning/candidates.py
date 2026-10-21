"""Extract traceable candidate concepts from evaluated knowledge chains.

Candidates come only from stored ontology claims whose subject and object
types satisfy RELATIONSHIP_RULES. Every candidate keeps every distinct
claim path that reached it, with the supporting and contradicting
evidence that was linked to each claim. Nothing here judges safety or
efficacy.
"""

from typing import Any

from app.models.c2_output import (
    CandidateCategory,
    CandidatePath,
    ClaimStep,
    EvidenceReference,
    InterpretedConcept,
    RejectedPath,
)
from app.ontology.relationships import validate_relationship


CANDIDATE_TYPES = frozenset(category.value for category in CandidateCategory)
INTERPRETATION_TYPES = frozenset(
    {"Roga", "Dosha", "Dhatu", "TherapeuticPrinciple"}
)

# Provenance needed for a reviewer to locate a source: these fields are
# required, plus at least one locator.
REQUIRED_PROVENANCE_FIELDS = ("title", "source_name", "evidence_type")
PROVENANCE_LOCATOR_FIELDS = ("citation", "source_url", "page", "section")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def build_evidence_reference(
    summary: dict[str, Any],
    relationship: str,
) -> EvidenceReference:
    missing = [
        field
        for field in REQUIRED_PROVENANCE_FIELDS
        if not _text(summary.get(field))
    ]
    if not any(_text(summary.get(f)) for f in PROVENANCE_LOCATOR_FIELDS):
        missing.append("citation|source_url|page|section")

    return EvidenceReference(
        evidence_id=str(summary.get("evidence_id")),
        relationship=relationship,
        title=_text(summary.get("title")),
        source_name=_text(summary.get("source_name")),
        evidence_type=_text(summary.get("evidence_type")),
        section=_text(summary.get("section")),
        page=_text(summary.get("page")),
        citation=_text(summary.get("citation")),
        source_url=_text(summary.get("source_url")),
        source_id=_text(summary.get("source_id")),
        source_chunk_id=_text(summary.get("chunk_id")),
        knowledge_status=_text(summary.get("knowledge_status")),
        evidence_role=_text(summary.get("evidence_role")),
        practitioner_verified=bool(summary.get("practitioner_verified")),
        provenance_complete=not missing,
        missing_provenance=missing,
    )


def concept_type(
    concepts: dict[str, dict[str, Any]],
    concept_id: str,
) -> tuple[str | None, str | None]:
    """Return (type, problem) for a concept from get_concepts() output."""
    entry = concepts.get(concept_id)
    if entry is None:
        return None, f"missing_concept:{concept_id}"
    labels = entry.get("labels") or []
    if len(labels) != 1:
        return None, f"ambiguous_concept_type:{concept_id}"
    return labels[0], None


def concept_name(
    concepts: dict[str, dict[str, Any]],
    concept_id: str,
) -> str | None:
    entry = concepts.get(concept_id) or {}
    return _text((entry.get("properties") or {}).get("name"))


def build_claim_step(
    claim: dict[str, Any],
    concepts: dict[str, dict[str, Any]],
) -> ClaimStep:
    evaluation = claim.get("evaluation")
    supporting = []
    contradicting = []
    stored_confidence = None

    if evaluation is not None:
        supporting = [
            build_evidence_reference(item, "SUPPORTS")
            for item in evaluation.get("supporting_evidence", [])
            if item.get("evidence_id")
        ]
        contradicting = [
            build_evidence_reference(item, "CONTRADICTS")
            for item in evaluation.get("contradicting_evidence", [])
            if item.get("evidence_id")
        ]
        stored_confidence = evaluation.get("stored_confidence")

    subject_type, _ = concept_type(concepts, claim["subject_id"])
    object_type, _ = concept_type(concepts, claim["object_id"])

    return ClaimStep(
        claim_id=claim["claim_id"],
        subject_id=claim["subject_id"],
        subject_type=subject_type,
        predicate=claim["predicate"],
        object_id=claim["object_id"],
        object_type=object_type,
        statement=_text(claim.get("statement")),
        verification_status=str(
            claim.get("verification_status") or "unverified"
        ),
        stored_confidence=stored_confidence,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        evidence_lookup_failed=evaluation is None,
        knowledge_status=(
            "provisional" if claim.get("knowledge_status") == "provisional" else "approved"
        ),
        claim_category=_text(claim.get("claim_category")),
        uncertainty_notes=[str(n) for n in claim.get("uncertainty_notes") or []],
        qualifying_evidence=[
            build_evidence_reference(item, "SUPPORTS")
            for item in claim.get("qualifying_evidence") or []
            if item.get("evidence_id")
        ],
    )


def _validate_step(
    claim: dict[str, Any],
    concepts: dict[str, dict[str, Any]],
) -> str | None:
    subject_type, problem = concept_type(concepts, claim["subject_id"])
    if problem:
        return problem
    object_type, problem = concept_type(concepts, claim["object_id"])
    if problem:
        return problem
    try:
        validate_relationship(
            claim["predicate"], subject_type, object_type
        )
    except ValueError:
        return (
            f"ontology_violation:{claim['claim_id']}:"
            f"{subject_type}-{claim['predicate']}->{object_type}"
        )
    return None


def extract_candidate_paths(
    chain_results: list[dict[str, Any]],
    concepts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Collect candidate paths, interpretation concepts and rejected paths.

    chain_results are outputs of trace_knowledge_chains(). A chain is
    scanned claim by claim; the first claim that violates the ontology (or
    references a missing/ambiguous concept) ends that chain and is
    reported as a rejected path. Valid prefixes ending at a Herb,
    Formulation, Diet or Lifestyle concept become candidate paths.
    """
    candidate_paths: dict[str, list[CandidatePath]] = {}
    seen_paths: dict[str, set[tuple[str, ...]]] = {}
    interpretation: dict[str, dict[str, Any]] = {}
    rejected: dict[tuple[str, ...], RejectedPath] = {}
    step_cache: dict[str, ClaimStep] = {}

    for result in chain_results:
        for chain in result.get("chains", []):
            concept_ids = chain["concept_ids"]
            claims = chain["claims"]
            steps: list[ClaimStep] = []

            for index, claim in enumerate(claims):
                problem = _validate_step(claim, concepts)
                if problem:
                    claim_ids = tuple(c["claim_id"] for c in claims[:index + 1])
                    rejected.setdefault(
                        claim_ids,
                        RejectedPath(
                            concept_ids=concept_ids[:index + 2],
                            claim_ids=list(claim_ids),
                            reason=problem,
                        ),
                    )
                    break

                step = step_cache.get(claim["claim_id"])
                if step is None:
                    step = build_claim_step(claim, concepts)
                    step_cache[claim["claim_id"]] = step
                steps.append(step)

                object_id = claim["object_id"]
                object_type = step.object_type

                if object_type in INTERPRETATION_TYPES:
                    entry = interpretation.setdefault(
                        object_id,
                        {"type": object_type, "steps": {}},
                    )
                    entry["steps"][step.claim_id] = step

                if object_type in CANDIDATE_TYPES:
                    key = tuple(s.claim_id for s in steps)
                    if key in seen_paths.setdefault(object_id, set()):
                        continue
                    seen_paths[object_id].add(key)
                    candidate_paths.setdefault(object_id, []).append(
                        CandidatePath(
                            concept_ids=concept_ids[:index + 2],
                            claims=list(steps),
                        )
                    )

    interpreted = [
        InterpretedConcept(
            concept_id=concept_id,
            concept_type=entry["type"],
            name=concept_name(concepts, concept_id),
            via_claim_ids=sorted(entry["steps"]),
            verification_statuses=sorted(
                {s.verification_status for s in entry["steps"].values()}
            ),
            supporting_evidence_ids=sorted(
                {
                    e.evidence_id
                    for s in entry["steps"].values()
                    for e in s.supporting_evidence
                }
            ),
            contradicting_evidence_ids=sorted(
                {
                    e.evidence_id
                    for s in entry["steps"].values()
                    for e in s.contradicting_evidence
                }
            ),
        )
        for concept_id, entry in sorted(interpretation.items())
    ]

    return {
        "candidate_paths": candidate_paths,
        "interpretation": interpreted,
        "rejected_paths": list(rejected.values()),
        "claim_steps": step_cache,
    }
