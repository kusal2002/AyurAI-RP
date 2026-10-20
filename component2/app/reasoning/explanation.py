"""Deterministic, evidence-grounded explanation statements.

Every statement about an Ayurvedic relationship is built only from stored
claim statements and evidence metadata, and carries the claim IDs and
evidence IDs it is derived from. No text, citation or source is generated
from model memory.
"""

from app.models.c2_output import (
    Candidate,
    CandidateDisposition,
    ExplanationStatement,
    InterpretedConcept,
    SymptomMapping,
)


def _label(concept_id: str, name: str | None) -> str:
    return f"{name} ({concept_id})" if name else concept_id


def explain_symptom_mappings(
    mappings: list[SymptomMapping],
) -> list[ExplanationStatement]:
    statements = []
    for mapping in mappings:
        if not mapping.found:
            text = (
                f"Supplied symptom ID {mapping.symptom_id} was not found "
                "as a stored Symptom concept and was not used."
            )
        elif not mapping.indicates_claim_ids:
            text = (
                f"Symptom {_label(mapping.symptom_id, mapping.name)} was "
                "found but has no stored INDICATES claims."
            )
        else:
            text = (
                f"Symptom {_label(mapping.symptom_id, mapping.name)} was "
                f"mapped through {len(mapping.indicates_claim_ids)} stored "
                "INDICATES claim(s)."
            )
        statements.append(
            ExplanationStatement(
                kind="symptom_mapping",
                text=text,
                claim_ids=list(mapping.indicates_claim_ids),
            )
        )
    return statements


def explain_interpretation(
    concepts: list[InterpretedConcept],
) -> list[ExplanationStatement]:
    return [
        ExplanationStatement(
            kind="interpretation",
            text=(
                f"{concept.concept_type} {_label(concept.concept_id, concept.name)} "
                f"is reached through stored claim(s) with verification "
                f"status {', '.join(concept.verification_statuses)}; "
                f"{len(concept.supporting_evidence_ids)} supporting and "
                f"{len(concept.contradicting_evidence_ids)} contradicting "
                "evidence record(s). This is a knowledge-graph association, "
                "not a diagnosis."
            ),
            claim_ids=list(concept.via_claim_ids),
            evidence_ids=sorted(
                set(concept.supporting_evidence_ids)
                | set(concept.contradicting_evidence_ids)
            ),
        )
        for concept in concepts
    ]


def explain_candidate(candidate: Candidate) -> list[ExplanationStatement]:
    statements = []
    label = _label(candidate.candidate_id, candidate.name)

    for path in candidate.paths:
        claim_ids = [claim.claim_id for claim in path.claims]
        evidence_ids = sorted(
            {
                ref.evidence_id
                for claim in path.claims
                for ref in claim.supporting_evidence
                + claim.contradicting_evidence
            }
        )
        quoted = " -> ".join(
            f"[{claim.claim_id}: {claim.predicate}, "
            f"{claim.verification_status}"
            + (f', "{claim.statement}"' if claim.statement else "")
            + "]"
            for claim in path.claims
        )
        statements.append(
            ExplanationStatement(
                kind="candidate_path",
                text=(
                    f"{candidate.category.value} candidate {label} appears "
                    f"because of the stored claim path "
                    f"{' -> '.join(path.concept_ids)}: {quoted}."
                ),
                claim_ids=claim_ids,
                evidence_ids=evidence_ids,
            )
        )

    for claim in {
        claim.claim_id: claim
        for path in candidate.paths
        for claim in path.claims
    }.values():
        if claim.supporting_evidence:
            statements.append(
                ExplanationStatement(
                    kind="supporting_evidence",
                    text=(
                        f"Claim {claim.claim_id} is supported by: "
                        + "; ".join(
                            f"{ref.evidence_id} ({ref.title or 'untitled'}"
                            f", {ref.source_name or 'unknown source'}"
                            + (f", {ref.citation}" if ref.citation else "")
                            + ")"
                            for ref in claim.supporting_evidence
                        )
                        + "."
                    ),
                    claim_ids=[claim.claim_id],
                    evidence_ids=[
                        ref.evidence_id for ref in claim.supporting_evidence
                    ],
                )
            )
        if claim.contradicting_evidence:
            statements.append(
                ExplanationStatement(
                    kind="contradicting_evidence",
                    text=(
                        f"Claim {claim.claim_id} is contradicted by: "
                        + "; ".join(
                            f"{ref.evidence_id} ({ref.title or 'untitled'})"
                            for ref in claim.contradicting_evidence
                        )
                        + ". The conflict is preserved, not resolved."
                    ),
                    claim_ids=[claim.claim_id],
                    evidence_ids=[
                        ref.evidence_id
                        for ref in claim.contradicting_evidence
                    ],
                )
            )

    sufficiency = candidate.sufficiency
    if sufficiency.evidence_gaps:
        statements.append(
            ExplanationStatement(
                kind="evidence_gaps",
                text=(
                    "Evidence gaps: "
                    + ", ".join(sufficiency.evidence_gaps)
                    + "."
                ),
                claim_ids=list(candidate.claim_ids),
            )
        )

    if candidate.disposition == CandidateDisposition.WITHHELD_PENDING_REVIEW:
        decision = (
            f"Withheld pending review: sufficiency status is "
            f"{sufficiency.status.value}."
        )
    else:
        decision = (
            "Forwarded for Component 3 safety assessment and practitioner "
            "review; this is not a statement that the candidate is safe "
            "or effective."
        )
    statements.append(
        ExplanationStatement(
            kind="candidate_decision",
            text=decision,
            claim_ids=list(candidate.claim_ids),
            evidence_ids=sorted(
                set(candidate.supporting_evidence_ids)
                | set(candidate.contradicting_evidence_ids)
            ),
        )
    )
    return statements


def explain_abstention(reasons: list[str]) -> ExplanationStatement:
    return ExplanationStatement(
        kind="abstention",
        text=(
            "Component 2 abstains from forwarding any candidate: "
            + ", ".join(reasons)
            + ". Practitioner review of the evidence base is required."
        ),
    )


def explain_caution(reasons: list[str], escalation: list[str]) -> ExplanationStatement:
    """Caution statement: why the decision is not a plain recommendation."""
    text = (
        "Decision: caution. Candidates are presented for practitioner review "
        "with caution because of: " + ", ".join(reasons) + "."
    )
    if escalation:
        text += " " + " ".join(escalation)
    return ExplanationStatement(kind="caution", text=text)
