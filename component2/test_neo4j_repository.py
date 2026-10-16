from app.db.neo4j import get_neo4j_driver
from app.db.repository import (
    get_claim,
    get_claims_for_concept,
    get_connected_knowledge,
    get_evidence,
    get_evidence_for_claim,
    get_symptom,
    link_evidence_to_claim,
    save_claim,
    save_evidence,
    save_symptom,
)
from app.models.claim import Claim, VerificationStatus
from app.models.evidence import EvidenceRecord, EvidenceType
from app.models.symptom import SymptomConcept
from app.reasoning.evaluator import evaluate_claim
from app.reasoning.symptom_reasoner import reason_about_symptoms
from app.ontology.claim_service import save_claim_with_evidence


def main():
    driver = get_neo4j_driver()

    concept_id = "TEST-REPO-CONCEPT"
    symptom_id = "TEST-REPO-SYMPTOM"
    claim_id = "TEST-REPO-CLAIM"
    evidence_id = "TEST-REPO-EVIDENCE"
    second_concept_id = "TEST-REPO-CONCEPT-2"
    contradicting_evidence_id = "TEST-REPO-EVIDENCE-2"
    roga_id = "TEST-REPO-ROGA"
    linked_claim_id = "TEST-REPO-LINKED-CLAIM"

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

                # Test symptom save and retrieval using synthetic data.
        symptom = SymptomConcept(
            symptom_id=symptom_id,
            name="Synthetic symptom for repository testing",
            aliases=["Synthetic test alias"],
            description="Temporary integration-test data only.",
        )

        saved_symptom = save_symptom(symptom, driver)
        assert saved_symptom["symptom_id"] == symptom_id
        assert saved_symptom["name"] == symptom.name

        retrieved_symptom = get_symptom(symptom_id, driver)
        assert retrieved_symptom is not None
        assert retrieved_symptom["name"] == symptom.name
        assert retrieved_symptom["aliases"] == symptom.aliases

        print("Symptom save and retrieval: PASS")

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

        contradicting_evidence = EvidenceRecord(
            evidence_id=contradicting_evidence_id,
            title="Synthetic contradictory evidence",
            source_name="Automated test fixture",
            evidence_type=EvidenceType.MODERN_RESEARCH,
            text="Synthetic contradictory content used only for testing.",
            concepts=[concept_id],
        )

        saved_contradicting_evidence = save_evidence(
            contradicting_evidence, driver
        )

        assert (
            saved_contradicting_evidence["evidence_id"]
            == contradicting_evidence_id
        )
        print("Contradictory evidence creation: PASS")

        # Test evidence-linked Symptom -> Roga claim.
        with driver.session() as session:
            session.run(
                """
                MERGE (:Roga {roga_id: $roga_id})
                """,
                roga_id=roga_id,
            ).consume()

        linked_claim = Claim(
            claim_id=linked_claim_id,
            subject_id=symptom_id,
            predicate="INDICATES",
            object_id=roga_id,
            statement="Synthetic symptom-to-Roga claim for integration testing.",
            verification_status=VerificationStatus.UNVERIFIED,
        )

        linked_claim_result = save_claim_with_evidence(
            linked_claim,
            [
                (evidence_id, "SUPPORTS"),
                (contradicting_evidence_id, "CONTRADICTS"),
            ],
            driver,
        )

        assert linked_claim_result["claim"]["claim_id"] == linked_claim_id
        assert (
            linked_claim_result["claim"]["verification_status"]
            == VerificationStatus.UNVERIFIED.value
        )

        linked_evaluation = evaluate_claim(linked_claim_id, driver)
        assert linked_evaluation is not None
        assert linked_evaluation["verification_status"] == "unverified"
        assert linked_evaluation["evidence_summary"] == {
            "supporting_count": 1,
            "contradicting_count": 1,
        }
        assert linked_evaluation["medical_conclusion"] is None

        print("Evidence-linked symptom-to-Roga claim: PASS")

        # Test the end-to-end symptom reasoning flow.
        symptom_reasoning = reason_about_symptoms(
            [symptom_id],
            driver,
        )

        assert symptom_reasoning["summary"] == {
            "requested_symptom_count": 1,
            "unique_symptom_count": 1,
            "found_symptom_count": 1,
            "indicates_claim_count": 1,
        }

        symptom_result = symptom_reasoning["results"][0]

        assert symptom_result["found"] is True
        assert symptom_result["symptom"]["symptom_id"] == symptom_id
        assert len(symptom_result["indicates_claims"]) == 1

        reasoning_claim = symptom_result["indicates_claims"][0]

        assert reasoning_claim["claim_id"] == linked_claim_id
        assert reasoning_claim["roga_id"] == roga_id
        assert reasoning_claim["verification_status"] == "unverified"

        evaluation = reasoning_claim["evaluation"]

        assert evaluation is not None
        assert evaluation["evidence_summary"] == {
            "supporting_count": 1,
            "contradicting_count": 1,
        }
        assert evaluation["medical_conclusion"] is None
        assert symptom_reasoning["medical_conclusion"] is None

        print("End-to-end symptom reasoning flow: PASS")

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

        # Repeating the same link must not create a duplicate.
        link_evidence_to_claim(
            evidence_id,
            claim_id,
            "SUPPORTS",
            driver,
        )

        link_evidence_to_claim(
            contradicting_evidence_id,
            claim_id,
            "CONTRADICTS",
            driver,
        )

        # Repeating the same link must not create a duplicate.
        link_evidence_to_claim(
            contradicting_evidence_id,
            claim_id,
            "CONTRADICTS",
            driver,
        )

        print("Contradictory evidence link: PASS")

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

        assert records["subjects"] == [second_concept_id], (
            f"Expected only {second_concept_id}, got {records['subjects']}"
        )
        assert records["objects"] == [concept_id], (
            f"Expected only {concept_id}, got {records['objects']}"
        )

        print("Claim relationship verification: PASS")

        # Query claims where the concept is the subject.
        subject_claims = get_claims_for_concept(
            second_concept_id,
            driver,
        )

        assert any(
            item["claim"]["claim_id"] == claim_id
            and item["role"] == "subject"
            for item in subject_claims
        ), "The query did not find the claim's subject."

        print("Query claims by subject: PASS")

        # Query claims where the concept is the object.
        object_claims = get_claims_for_concept(
            concept_id,
            driver,
        )

        assert any(
            item["claim"]["claim_id"] == claim_id
            and item["role"] == "object"
            for item in object_claims
        ), "The query did not find the claim's object."

        print("Query claims by object: PASS")

        # A concept without connected claims should return an empty list.
        unconnected_claims = get_claims_for_concept(
            "TEST-UNCONNECTED-CONCEPT",
            driver,
        )

        assert unconnected_claims == [], (
            f"Expected no claims, got {unconnected_claims}"
        )

        print("Query unconnected concept: PASS")


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

        with driver.session() as session:
            contradictory_result = session.run(
                """
                MATCH (e:Evidence {evidence_id: $evidence_id})
                      -[r:CONTRADICTS]->(c:Claim {claim_id: $claim_id})
                RETURN count(r) AS total
                """,
                evidence_id=contradicting_evidence_id,
                claim_id=claim_id,
            ).single()

        assert contradictory_result["total"] == 1
        print("Contradictory evidence verification: PASS")

        # Retrieve connected knowledge for the claim's subject.
        connected_knowledge = get_connected_knowledge(
            second_concept_id,
            driver,
        )

        matching_results = [
            item
            for item in connected_knowledge
            if item["claim"] is not None
            and item["claim"]["claim_id"] == claim_id
        ]

        assert matching_results, (
            "Traversal did not find the connected claim."
        )

        result = matching_results[0]

        assert result["starting_concept"]["symptom_id"] == (
            second_concept_id
        )
        assert result["related_concept"]["symptom_id"] == concept_id

        assert any(
            item["evidence_id"] == evidence_id
            for item in result["supporting_evidence"]
        ), "Traversal did not find supporting evidence."

        assert any(
            item["evidence_id"] == contradicting_evidence_id
            for item in result["contradicting_evidence"]
        ), "Traversal did not find contradicting evidence."

        print("Connected knowledge traversal: PASS")

        # Traversal must also work when the starting concept is the object.
        object_side_knowledge = get_connected_knowledge(
            concept_id,
            driver,
        )

        object_side_results = [
            item
            for item in object_side_knowledge
            if item["claim"] is not None
            and item["claim"]["claim_id"] == claim_id
        ]

        assert object_side_results, (
            "Traversal did not find the claim from its object concept."
        )

        object_side_result = object_side_results[0]

        assert object_side_result["related_concept"]["symptom_id"] == (
            second_concept_id
        ), "Traversal did not return the claim's subject concept."

        print("Object-side knowledge traversal: PASS")

        # An unconnected concept should return no claim results.
        unconnected_knowledge = get_connected_knowledge(
            "TEST-UNCONNECTED-CONCEPT",
            driver,
        )

        assert all(
            item["claim"] is None
            for item in unconnected_knowledge
        ), (
            "Expected no connected claims for the unconnected concept."
        )

        print("Traversal for unconnected concept: PASS")

        # Retrieve a claim with both supporting and contradicting evidence.
        claim_evidence = get_evidence_for_claim(claim_id, driver)

        assert claim_evidence is not None
        assert claim_evidence["claim"]["claim_id"] == claim_id

        evidence_by_id = {
            item["evidence"]["evidence_id"]: item["relationship"]
            for item in claim_evidence["evidence"]
        }

        assert evidence_by_id[evidence_id] == "SUPPORTS"
        assert (
            evidence_by_id[contradicting_evidence_id]
            == "CONTRADICTS"
        )

        print("Retrieve supporting and contradicting evidence: PASS")

        # Evaluate the claim using the real Neo4j repository.
        evaluation = evaluate_claim(claim_id, driver)

        assert evaluation is not None
        assert evaluation["claim"]["claim_id"] == claim_id
        assert evaluation["verification_status"] == "unverified"

        assert len(evaluation["supporting_evidence"]) == 1
        assert len(evaluation["contradicting_evidence"]) == 1

        assert (
            evaluation["supporting_evidence"][0]["evidence_id"]
            == evidence_id
        )
        assert (
            evaluation["contradicting_evidence"][0]["evidence_id"]
            == contradicting_evidence_id
        )

        assert evaluation["evidence_summary"] == {
            "supporting_count": 1,
            "contradicting_count": 1,
        }
        assert evaluation["medical_conclusion"] is None

        print("Real Neo4j claim evaluation: PASS")

        # A nonexistent claim should return None.
        missing_claim_evidence = get_evidence_for_claim(
            "TEST-MISSING-CLAIM",
            driver,
        )

        # A claim with no linked evidence should return an empty list.
        claim_without_evidence = Claim(
            claim_id="TEST-CLAIM-WITHOUT-EVIDENCE",
            subject_id=concept_id,
            predicate="TEST_RELATION",
            object_id=second_concept_id,
            statement="Synthetic claim without evidence.",
            verification_status=VerificationStatus.UNVERIFIED,
        )

        save_claim(claim_without_evidence, driver)

        result_without_evidence = get_evidence_for_claim(
            "TEST-CLAIM-WITHOUT-EVIDENCE",
            driver,
        )

        assert result_without_evidence is not None
        assert result_without_evidence["evidence"] == [], (
            f"Expected an empty evidence list, "
            f"got {result_without_evidence['evidence']}"
        )

        print("Handle claim without evidence: PASS")

        assert missing_claim_evidence is None
        print("Handle missing claim evidence: PASS")


        # Reject evidence links when the evidence record is missing.
        try:
            link_evidence_to_claim(
                "TEST-MISSING-EVIDENCE",
                claim_id,
                "SUPPORTS",
                driver,
            )
        except ValueError:
            print("Reject link to missing evidence: PASS")
        else:
            raise AssertionError(
                "A link to missing evidence was accepted."
            )

        # Reject evidence links when the claim is missing.
        try:
            link_evidence_to_claim(
                evidence_id,
                "TEST-MISSING-CLAIM",
                "SUPPORTS",
                driver,
            )
        except ValueError:
            print("Reject link to missing claim: PASS")
        else:
            raise AssertionError(
                "A link to a missing claim was accepted."
            )

        try:
            link_evidence_to_claim(
                evidence_id,
                claim_id,
                "INVALID_RELATION",
                driver,
            )
        except ValueError:
            print("Reject invalid evidence relationship: PASS")
        else:
            raise AssertionError(
                "Invalid relationship type was accepted."
            )


    finally:
        # Remove only records with this test's dedicated identifiers.
        with driver.session() as session:
            session.run(
                """
                MATCH (n)
                WHERE n.symptom_id = $concept_id
                    OR n.symptom_id = $second_concept_id
                    OR n.symptom_id = $symptom_id
                    OR n.roga_id = $roga_id
                    OR n.claim_id = $linked_claim_id
                    OR n.claim_id = $claim_id
                    OR n.evidence_id = $evidence_id
                    OR n.evidence_id = $contradicting_evidence_id
                    OR n.claim_id = $claim_without_evidence_id
                DETACH DELETE n
                """,
                concept_id=concept_id,
                second_concept_id=second_concept_id,
                symptom_id=symptom_id,
                roga_id=roga_id,
                linked_claim_id=linked_claim_id,
                claim_id=claim_id,
                evidence_id=evidence_id,
                contradicting_evidence_id=contradicting_evidence_id,
                claim_without_evidence_id="TEST-CLAIM-WITHOUT-EVIDENCE",
            ).consume()

        print("Synthetic test cleanup: PASS")


if __name__ == "__main__":
    try:
        main()
    finally:
        from app.db.neo4j import close_neo4j_driver

        close_neo4j_driver()
