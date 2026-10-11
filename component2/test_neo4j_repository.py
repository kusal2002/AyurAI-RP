from app.db.neo4j import get_neo4j_driver
from app.db.repository import (
    get_claim,
    get_evidence,
    link_evidence_to_claim,
    save_claim,
    save_evidence,
)
from app.models.claim import Claim, VerificationStatus
from app.models.evidence import EvidenceRecord, EvidenceType


def main():
    driver = get_neo4j_driver()

    concept_id = "TEST-REPO-CONCEPT"
    claim_id = "TEST-REPO-CLAIM"
    evidence_id = "TEST-REPO-EVIDENCE"
    second_concept_id = "TEST-REPO-CONCEPT-2"

    try:
        # Create a temporary synthetic concept for this test.
        with driver.session() as session:
            session.run(
                """
                MERGE (:Symptom {symptom_id: $concept_id})
                """,
                concept_id=concept_id,
            ).consume()

            session.run(
                """
                MERGE (:Symptom {symptom_id: $concept_id})
                """,
                concept_id=second_concept_id,
            ).consume()

        evidence = EvidenceRecord(
            evidence_id=evidence_id,
            title="Synthetic repository test evidence",
            source_name="Automated test fixture",
            evidence_type=EvidenceType.MODERN_RESEARCH,
            text="Synthetic content used only to test storage.",
            concepts=[concept_id],
        )

        saved_evidence = save_evidence(evidence, driver)
        assert saved_evidence["evidence_id"] == evidence_id
        assert get_evidence(evidence_id, driver) is not None
        print("Evidence save and retrieval: PASS")

        claim = Claim(
            claim_id=claim_id,
            subject_id=concept_id,
            predicate="TEST_RELATION",
            object_id=concept_id,
            statement="Synthetic claim used only for testing.",
            verification_status=VerificationStatus.UNVERIFIED,
        )

        saved_claim = save_claim(claim, driver)
        assert saved_claim["claim_id"] == claim_id
        assert get_claim(claim_id, driver) is not None
        print("Claim save and retrieval: PASS")

        link_evidence_to_claim(
            evidence_id,
            claim_id,
            "SUPPORTS",
            driver,
        )

        updated_claim = claim.model_copy(
    update={
        "subject_id": second_concept_id,
        "statement": "Updated synthetic claim used only for testing.",
    }
)

        save_claim(updated_claim, driver)

        with driver.session() as session:
            records = session.run(
                """
                MATCH (c:Claim {claim_id: $claim_id})
                OPTIONAL MATCH (s)-[:SUBJECT_OF]->(c)
                OPTIONAL MATCH (c)-[:OBJECT_OF]->(o)
                RETURN collect(DISTINCT s.symptom_id) AS subjects,
                    collect(DISTINCT o.symptom_id) AS objects
                """,
                claim_id=claim_id,
            ).single(strict=True)

        print("DEBUG subjects:", records["subjects"])
        print("DEBUG objects:", records["objects"])

        assert records["subjects"] == [second_concept_id], (
            f"Expected only {second_concept_id}, got {records['subjects']}"
        )
        assert records["objects"] == [concept_id], (
            f"Expected only {concept_id}, got {records['objects']}"
        )

        print("Claim relationship verification: PASS")


        invalid_claim = Claim(
            claim_id="TEST-INVALID-CLAIM",
            subject_id="TEST-MISSING-CONCEPT",
            predicate="TEST_RELATION",
            object_id=concept_id,
            statement="This claim must not be saved.",
            verification_status=VerificationStatus.UNVERIFIED,
        )

        try:
            save_claim(invalid_claim, driver)
        except ValueError:
            print("Reject claim with missing concept: PASS")
        else:
            raise AssertionError(
                "Invalid claim was accepted; expected ValueError."
            )

        assert get_claim("TEST-INVALID-CLAIM", driver) is None

        with driver.session() as session:
            result = session.run(
                """
                MATCH (e:Evidence {evidence_id: $evidence_id})
                      -[r:SUPPORTS]->(c:Claim {claim_id: $claim_id})
                RETURN count(r) AS total
                """,
                evidence_id=evidence_id,
                claim_id=claim_id,
            ).single()

        assert result["total"] == 1
        print("Evidence-to-claim relationship: PASS")

    finally:
        # Remove only records with this test's dedicated identifiers.
        with driver.session() as session:
            session.run(
                """
                MATCH (n)
                WHERE n.symptom_id = $concept_id
                    OR n.symptom_id = $second_concept_id
                    OR n.claim_id = $claim_id
                    OR n.evidence_id = $evidence_id
                DETACH DELETE n
                """,
                concept_id=concept_id,
                second_concept_id=second_concept_id,
                claim_id=claim_id,
                evidence_id=evidence_id,
            ).consume()

        print("Synthetic test cleanup: PASS")


if __name__ == "__main__":
    try:
        main()
    finally:
        from app.db.neo4j import close_neo4j_driver

        close_neo4j_driver()
