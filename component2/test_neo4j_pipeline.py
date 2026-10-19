"""Live Neo4j integration checks for the Component 2 pipeline.

Run with:  python test_neo4j_pipeline.py

Uses only synthetic concepts, claims and evidence whose identifiers start
with TEST-C2PIPE-. All of them are removed in the finally block and the
removal is verified. The synthetic data proves software integration only;
it says nothing about real Ayurvedic knowledge.
"""

from app.db.neo4j import get_neo4j_driver
from app.db.repository import (
    get_claim,
    get_concepts,
    list_evidence,
    save_claim,
    save_evidence,
    save_symptom,
)
from app.feedback.service import (
    DuplicateFeedbackError,
    get_feedback,
    save_feedback,
)
from app.governance.audit import build_audit_record
from app.models.c1_input import Component2ReasoningRequest
from app.models.claim import Claim, VerificationStatus
from app.models.evidence import EvidenceRecord, EvidenceType
from app.models.feedback import PractitionerFeedback
from app.models.symptom import SymptomConcept
from app.ontology.claim_service import save_claim_with_evidence
from app.reasoning.pipeline import run_component2_reasoning
from app.retrieval.service import EvidenceRetrievalService


PREFIX = "TEST-C2PIPE-"
SYMPTOM = PREFIX + "SYMPTOM"
ROGA = PREFIX + "ROGA"
PRINCIPLE = PREFIX + "PRINCIPLE"
HERB = PREFIX + "HERB"
FORMULATION = PREFIX + "FORMULATION"
DIET = PREFIX + "DIET"
BAD_HERB = PREFIX + "BAD-HERB"
FEEDBACK_ID = PREFIX + "FEEDBACK"

CONCEPTS = [
    ("Roga", "roga_id", ROGA, "synthetic test roga"),
    ("TherapeuticPrinciple", "principle_id", PRINCIPLE,
     "synthetic test principle"),
    ("Herb", "herb_id", HERB, "synthetic test herb"),
    ("Formulation", "formulation_id", FORMULATION,
     "synthetic test formulation"),
    ("Diet", "diet_id", DIET, "synthetic test diet"),
    ("Herb", "herb_id", BAD_HERB, "synthetic invalid-path herb"),
]


def evidence(suffix, text, evidence_type=EvidenceType.CLASSICAL):
    return EvidenceRecord(
        evidence_id=PREFIX + suffix,
        title=f"Synthetic integration source {suffix}",
        source_name="Automated integration-test fixture",
        evidence_type=evidence_type,
        section="Synthetic section",
        page="1",
        text=text,
        citation=f"Synthetic fixture citation {suffix}",
    )


def claim(suffix, subject, predicate, obj, statement, status):
    return Claim(
        claim_id=PREFIX + suffix,
        subject_id=subject,
        predicate=predicate,
        object_id=obj,
        statement=statement,
        verification_status=status,
    )


def check(label, condition):
    if not condition:
        raise AssertionError(f"{label}: FAIL")
    print(f"{label}: PASS")


def cleanup(driver):
    with driver.session() as session:
        session.run(
            """
            MATCH (n)
            WHERE any(key IN keys(n)
                      WHERE key ENDS WITH '_id'
                        AND n[key] IS :: STRING
                        AND n[key] STARTS WITH $prefix)
            DETACH DELETE n
            """,
            prefix=PREFIX,
        ).consume()
        remaining = session.run(
            """
            MATCH (n)
            WHERE any(key IN keys(n)
                      WHERE key ENDS WITH '_id'
                        AND n[key] IS :: STRING
                        AND n[key] STARTS WITH $prefix)
            RETURN count(n) AS total
            """,
            prefix=PREFIX,
        ).single()["total"]
    return remaining


def main():
    driver = get_neo4j_driver()
    S = VerificationStatus.LITERATURE_SUPPORTED

    try:
        cleanup(driver)

        save_symptom(
            SymptomConcept(symptom_id=SYMPTOM, name="synthetic test symptom"),
            driver,
        )
        with driver.session() as session:
            for label, key, concept_id, name in CONCEPTS:
                session.run(
                    f"MERGE (n:{label} {{{key}: $id}}) SET n.name = $name",
                    id=concept_id,
                    name=name,
                ).consume()

        for record in [
            evidence("EV-IND", "Synthetic fixture: the synthetic test "
                     "symptom indicates the synthetic test roga."),
            evidence("EV-TP", "Synthetic fixture: the synthetic test roga "
                     "suggests the synthetic test principle."),
            evidence("EV-HERB", "Synthetic fixture: the synthetic test "
                     "principle uses the synthetic test herb."),
            evidence("EV-FORM", "Synthetic fixture: the synthetic test "
                     "principle uses the synthetic test formulation."),
            evidence("EV-FORM-CON", "Synthetic fixture: the synthetic test "
                     "principle does not use the synthetic test formulation.",
                     EvidenceType.MODERN_RESEARCH),
        ]:
            save_evidence(record, driver)

        save_claim_with_evidence(
            claim("CL-IND", SYMPTOM, "INDICATES", ROGA,
                  "The synthetic test symptom indicates the synthetic "
                  "test roga.", S),
            [(PREFIX + "EV-IND", "SUPPORTS")], driver,
        )
        save_claim_with_evidence(
            claim("CL-TP", ROGA, "SUGGESTS_PRINCIPLE", PRINCIPLE,
                  "The synthetic test roga suggests the synthetic test "
                  "principle.", S),
            [(PREFIX + "EV-TP", "SUPPORTS")], driver,
        )
        save_claim_with_evidence(
            claim("CL-HERB", PRINCIPLE, "USES_HERB", HERB,
                  "The synthetic test principle uses the synthetic test "
                  "herb.", S),
            [(PREFIX + "EV-HERB", "SUPPORTS")], driver,
        )
        save_claim_with_evidence(
            claim("CL-FORM", PRINCIPLE, "USES_FORMULATION", FORMULATION,
                  "The synthetic test principle uses the synthetic test "
                  "formulation.", S),
            [(PREFIX + "EV-FORM", "SUPPORTS"),
             (PREFIX + "EV-FORM-CON", "CONTRADICTS")], driver,
        )
        save_claim_with_evidence(
            claim("CL-DIET", PRINCIPLE, "RECOMMENDS_DIET", DIET,
                  "The synthetic test principle recommends the synthetic "
                  "test diet.", VerificationStatus.UNVERIFIED),
            [], driver,
        )
        # Simulate a directly inserted claim that bypasses ontology checks.
        save_claim(
            claim("CL-BAD", ROGA, "USES_HERB", BAD_HERB,
                  "Directly inserted invalid synthetic claim.", S),
            driver,
        )
        print("Synthetic pipeline graph creation: PASS")

        concepts = get_concepts([SYMPTOM, HERB, PREFIX + "MISSING"], driver)
        check(
            "Batch concept lookup",
            concepts[SYMPTOM]["labels"] == ["Symptom"]
            and concepts[HERB]["properties"]["name"] == "synthetic test herb"
            and PREFIX + "MISSING" not in concepts,
        )

        stored_ids = {e["evidence_id"] for e in list_evidence(driver)}
        check("Evidence listing", PREFIX + "EV-HERB" in stored_ids)

        service = EvidenceRetrievalService(
            evidence_loader=lambda d: [
                e for e in list_evidence(d)
                if e["evidence_id"].startswith(PREFIX)
            ]
        )
        model_ready = service.ensure_ready(driver)
        print(
            f"Embedding model {service.model_id}: "
            + ("LOADED" if model_ready else f"UNAVAILABLE ({service.last_error})")
        )

        request = Component2ReasoningRequest(
            request_id="test-c2pipe-request",
            risk_tier="moderate",
            calibrated_confidence=0.9,
            symptom_ids=[SYMPTOM, f" {SYMPTOM} ", PREFIX + "UNKNOWN"],
        )
        output = run_component2_reasoning(
            request, driver=driver, retrieval_service=service
        )
        candidates = {c.candidate_id: c for c in output.candidates}

        check(
            "Pipeline symptom mapping",
            [m.found for m in output.symptom_mappings] == [True, False],
        )
        check(
            "Pipeline interpretation (Roga, principle)",
            {c.concept_id for c in output.interpretation} == {ROGA, PRINCIPLE},
        )
        check(
            "Pipeline candidate extraction",
            set(candidates) == {HERB, FORMULATION, DIET},
        )
        check(
            "Ontology-invalid direct insert rejected",
            BAD_HERB not in candidates
            and any(PREFIX + "CL-BAD" in r.claim_ids
                    for r in output.rejected_paths),
        )
        herb = candidates[HERB]
        check(
            "Herb evidence trace to stored records",
            herb.supporting_evidence_ids == sorted(
                [PREFIX + "EV-HERB", PREFIX + "EV-IND", PREFIX + "EV-TP"]
            ),
        )
        check(
            "Formulation conflict preserved and withheld",
            candidates[FORMULATION].sufficiency.status.value
            == "conflicting_evidence"
            and candidates[FORMULATION].contradicting_evidence_ids
            == [PREFIX + "EV-FORM-CON"]
            and candidates[FORMULATION].disposition.value
            == "withheld_pending_review",
        )
        check(
            "Diet without evidence is insufficient",
            candidates[DIET].sufficiency.status.value
            == "insufficient_evidence",
        )

        if model_ready:
            similarities = [c.retrieval_similarity for c in herb.paths[0].claims]
            print(f"  herb path claim-evidence similarities: {similarities}")
            check(
                "Real embedding retrieval used",
                output.retrieval.mode == "neural_embedding"
                and all(s is not None for s in similarities),
            )
            check(
                "Herb forwarded for safety assessment",
                herb.disposition.value == "forward_for_safety_assessment"
                and output.abstention.abstain is False,
            )
            check(
                "Open retrieval returns traceable evidence",
                all(item.evidence_id.startswith(PREFIX)
                    for item in output.retrieved_evidence)
                and len(output.retrieved_evidence) > 0,
            )
        else:
            check(
                "Model unavailable reported, no fallback",
                output.retrieval.mode == "unavailable"
                and output.abstention.abstain is True,
            )
            print("Real embedding retrieval checks: SKIPPED (model unavailable)")

        unknown_output = run_component2_reasoning(
            Component2ReasoningRequest(
                risk_tier="low",
                calibrated_confidence=0.2,
                symptom_ids=[PREFIX + "UNKNOWN"],
            ),
            driver=driver,
            retrieval_service=service,
        )
        check(
            "Unknown symptom abstains as out of scope",
            unknown_output.abstention.abstain
            and unknown_output.sufficiency_status.value == "out_of_scope",
        )

        audit = build_audit_record(output).model_dump_json()
        check(
            "Audit record has IDs but no symptom IDs or screening data",
            PREFIX + "CL-HERB" in audit
            and SYMPTOM not in audit
            and "0.9" not in audit,
        )

        feedback = PractitionerFeedback(
            feedback_id=FEEDBACK_ID,
            request_id="test-c2pipe-request",
            claim_ids=[PREFIX + "CL-FORM", PREFIX + "CL-MISSING"],
            candidate_ids=[FORMULATION],
            evidence_ids=[PREFIX + "EV-FORM-CON"],
            review_outcome="needs_more_evidence",
            issue_category="contradicting_evidence",
            rationale="Synthetic integration-test feedback.",
            refinement_terms=["synthetic test formulation"],
            reviewer_role="researcher",
            reviewer_ref="test-reviewer",
        )
        stored = save_feedback(feedback, driver)
        check(
            "Feedback stored and linked to existing claims only",
            stored["linked_claim_ids"] == [PREFIX + "CL-FORM"]
            and stored["unknown_claim_ids"] == [PREFIX + "CL-MISSING"],
        )
        check(
            "Feedback retrievable",
            get_feedback(FEEDBACK_ID, driver)["reviewed_claim_ids"]
            == [PREFIX + "CL-FORM"],
        )
        check(
            "Feedback did not modify the reviewed claim",
            get_claim(PREFIX + "CL-FORM", driver)["verification_status"]
            == "literature_supported",
        )
        try:
            save_feedback(feedback, driver)
        except DuplicateFeedbackError:
            print("Duplicate feedback rejected (append-only): PASS")
        else:
            raise AssertionError("Duplicate feedback was accepted.")

    finally:
        remaining = cleanup(driver)
        if remaining:
            raise AssertionError(
                f"Synthetic cleanup left {remaining} nodes."
            )
        print("Synthetic pipeline cleanup verified: PASS")


if __name__ == "__main__":
    try:
        main()
    finally:
        from app.db.neo4j import close_neo4j_driver

        close_neo4j_driver()
