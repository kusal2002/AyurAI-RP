from typing import Any

from app.db.repository import get_evidence_for_claim


def evaluate_claim(
    claim_id: str,
    driver: Any = None,
) -> dict[str, Any] | None:
    """
    Evaluate the evidence associated with a knowledge graph claim.

    This function summarizes the stored evidence and verification status.
    It does not determine medical truth or generate a new confidence score.
    """
    if not claim_id or not claim_id.strip():
        raise ValueError("claim_id must not be empty.")

    result = get_evidence_for_claim(claim_id, driver)

    if result is None:
        return None

    claim = result["claim"]
    evidence_records = result["evidence"]

    supporting_evidence = []
    contradicting_evidence = []

    for item in evidence_records:
        evidence = item["evidence"]
        relationship = item["relationship"]

        evidence_summary = {
            "evidence_id": evidence.get("evidence_id"),
            "title": evidence.get("title"),
            "source_name": evidence.get("source_name"),
            "evidence_type": evidence.get("evidence_type"),
            "section": evidence.get("section"),
            "page": evidence.get("page"),
            "citation": evidence.get("citation"),
            "source_url": evidence.get("source_url"),
            "practitioner_verified": evidence.get(
                "practitioner_verified", False
            ),
        }

        if relationship == "SUPPORTS":
            supporting_evidence.append(evidence_summary)
        elif relationship == "CONTRADICTS":
            contradicting_evidence.append(evidence_summary)
        else:
            raise ValueError(
                f"Unsupported evidence relationship: {relationship}"
            )

    verification_status = claim.get(
        "verification_status", "unverified"
    )

    reasoning_notes = []

    if supporting_evidence:
        reasoning_notes.append(
            "Supporting evidence is linked to this claim."
        )
    else:
        reasoning_notes.append(
            "No supporting evidence is linked to this claim."
        )

    if contradicting_evidence:
        reasoning_notes.append(
            "Contradicting evidence is linked to this claim."
        )
    else:
        reasoning_notes.append(
            "No contradicting evidence is linked to this claim."
        )

    if supporting_evidence and contradicting_evidence:
        reasoning_notes.append(
            "Conflicting evidence is present. The claim requires "
            "further review; do not resolve the conflict automatically."
        )

    if verification_status == "disputed":
        reasoning_notes.append(
            "The claim is marked as disputed and requires careful review."
        )
    elif verification_status == "unverified":
        reasoning_notes.append(
            "The claim is unverified; do not treat it as established."
        )
    elif verification_status == "literature_supported":
        reasoning_notes.append(
            "The claim is marked as literature-supported in the repository."
        )
    elif verification_status == "practitioner_verified":
        reasoning_notes.append(
            "The claim is marked as practitioner-verified in the repository."
        )

    return {
        "claim": claim,
        "verification_status": verification_status,
        "stored_confidence": claim.get("confidence"),
        "supporting_evidence": supporting_evidence,
        "contradicting_evidence": contradicting_evidence,
        "evidence_summary": {
            "supporting_count": len(supporting_evidence),
            "contradicting_count": len(contradicting_evidence),
        },
        "reasoning_notes": reasoning_notes,
        "medical_conclusion": None,
    }
