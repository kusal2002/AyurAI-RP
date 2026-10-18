import json
import logging

from app.governance.audit import build_audit_record, emit_audit_record
from app.models.c1_input import Component2ReasoningRequest
from app.models.c2_output import (
    CandidateDisposition,
    Component2Output,
    SufficiencyStatus,
)
from app.models.c3_handoff import build_component3_handoff
from app.reasoning.pipeline import run_component2_reasoning
from c2_test_support import (
    FailingEncoder,
    FakeGraph,
    build_pandu_graph,
    make_retrieval_service,
)


def make_request(symptom_ids=("S-PALLOR",), confidence=0.97):
    return Component2ReasoningRequest(
        request_id="req-test-1",
        risk_tier="high",
        calibrated_confidence=confidence,
        symptom_ids=list(symptom_ids),
    )


def run(graph, request=None, encoder=None, retrieval=True):
    service = (
        make_retrieval_service(graph, encoder=encoder) if retrieval else None
    )
    with graph.patched():
        return run_component2_reasoning(
            request or make_request(), retrieval_service=service
        )


def by_id(output):
    return {c.candidate_id: c for c in output.candidates}


def test_full_pipeline_forwards_sufficient_candidates():
    output = run(build_pandu_graph())

    assert output.abstention.abstain is False
    assert output.sufficiency_status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    assert output.retrieval.mode == "neural_embedding"
    assert output.retrieval.model_id == "test-keyword-encoder"
    assert set(by_id(output)) == {"H-1", "F-1", "D-1", "L-1"}
    for candidate in output.candidates:
        assert candidate.disposition == (
            CandidateDisposition.FORWARD_FOR_SAFETY_ASSESSMENT
        )
        assert candidate.paths[0].claims[-1].retrieval_similarity > 0.3
    assert output.medical_conclusion is None


def test_existing_symptom_to_roga_mapping_is_reported():
    output = run(build_pandu_graph())

    assert output.symptom_mappings[0].found is True
    assert output.symptom_mappings[0].indicates_claim_ids == ["CL-IND"]
    assert [c.concept_id for c in output.interpretation] == ["R-PANDU", "TP-1"]


def test_evidence_ids_trace_back_to_source_records():
    graph = build_pandu_graph()
    output = run(graph)
    herb = by_id(output)["H-1"]

    assert herb.supporting_evidence_ids == ["EV-HERB", "EV-IND", "EV-TP"]
    for evidence_id in herb.supporting_evidence_ids:
        assert evidence_id in graph.evidence
    herb_ref = herb.paths[0].claims[-1].supporting_evidence[0]
    assert herb_ref.citation == graph.evidence["EV-HERB"]["citation"]


def test_conflict_stays_visible_and_candidate_is_withheld():
    graph = build_pandu_graph(herb_contradicts=["EV-HERB-CON"])
    output = run(graph)
    herb = by_id(output)["H-1"]

    assert herb.sufficiency.status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert herb.disposition == CandidateDisposition.WITHHELD_PENDING_REVIEW
    assert herb.contradicting_evidence_ids == ["EV-HERB-CON"]
    assert "supporting_and_contradicting_evidence" in herb.conflict_flags
    assert any(s.kind == "contradicting_evidence" for s in herb.rationale)
    # Forwarded candidates come first regardless of score.
    assert output.candidates[-1].candidate_id == "H-1"


def test_unknown_symptoms_are_out_of_scope_and_abstain():
    output = run(build_pandu_graph(), make_request(["S-UNKNOWN"]))

    assert output.sufficiency_status == SufficiencyStatus.OUT_OF_SCOPE
    assert output.abstention.abstain is True
    assert output.abstention.reasons == [
        "no_supplied_symptom_mapped_to_stored_concept"
    ]
    assert output.candidates == []
    assert output.symptom_mappings[0].found is False


def test_empty_knowledge_graph_returns_no_fabricated_candidates():
    output = run(FakeGraph())

    assert output.candidates == []
    assert output.interpretation == []
    assert output.retrieved_evidence == []
    assert output.abstention.abstain is True


def test_symptom_without_claims_abstains_with_insufficient_evidence():
    graph = FakeGraph()
    graph.add_concept("Symptom", "S-PALLOR", "pallor")
    output = run(graph)

    assert output.sufficiency_status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert output.abstention.reasons == ["no_valid_candidate_path_found"]


def test_insufficient_evidence_example_response():
    graph = build_pandu_graph(herb_supports=())
    for claim in graph.claims.values():
        claim["verification_status"] = "unverified"
    output = run(graph)

    assert output.abstention.abstain is True
    assert output.sufficiency_status in {
        SufficiencyStatus.INSUFFICIENT_EVIDENCE,
        SufficiencyStatus.UNVERIFIED_CLAIMS,
    }
    assert "no_candidate_sufficient_for_review" in output.abstention.reasons
    assert all(
        c.disposition == CandidateDisposition.WITHHELD_PENDING_REVIEW
        for c in output.candidates
    )
    payload = json.loads(output.model_dump_json())
    assert payload["abstention"]["abstain"] is True


def test_model_unavailable_degrades_without_fake_retrieval():
    output = run(build_pandu_graph(), encoder=FailingEncoder())

    assert output.retrieval.mode == "unavailable"
    assert output.retrieval.error
    assert output.retrieved_evidence == []
    assert "semantic_retrieval_unavailable" in output.uncertainty_flags
    assert all(
        c.paths[0].claims[-1].retrieval_similarity is None
        for c in output.candidates
    )
    assert output.abstention.abstain is True


def test_screening_confidence_is_not_used_for_candidates():
    high = run(build_pandu_graph(), make_request(confidence=0.99))
    low = run(build_pandu_graph(), make_request(confidence=0.01))

    assert [
        (c.candidate_id, c.ranking.score) for c in high.candidates
    ] == [(c.candidate_id, c.ranking.score) for c in low.candidates]
    assert high.upstream.calibrated_confidence == 0.99


def test_output_serializes_and_has_no_overall_medical_confidence():
    output = run(build_pandu_graph())
    payload = json.loads(output.model_dump_json())

    assert Component2Output.model_validate(payload).request_id == "req-test-1"
    assert payload["medical_conclusion"] is None
    assert not any("confidence" == key for key in payload)
    assert "overall_confidence" not in payload
    assert set(payload["score_semantics"]) == {
        "upstream.calibrated_confidence",
        "retrieval_similarity",
        "ranking.score",
        "stored_confidence",
    }


def test_explanations_are_traceable_to_claims_and_evidence():
    output = run(build_pandu_graph())

    for candidate in output.candidates:
        path_statements = [
            s for s in candidate.rationale if s.kind == "candidate_path"
        ]
        assert path_statements
        for statement in path_statements:
            assert statement.claim_ids
            assert set(statement.claim_ids) <= set(candidate.claim_ids)
            assert set(statement.evidence_ids) <= set(
                candidate.supporting_evidence_ids
                + candidate.contradicting_evidence_ids
            )


def test_component3_handoff_contains_required_fields():
    graph = build_pandu_graph(herb_contradicts=["EV-HERB-CON"])
    handoff = build_component3_handoff(run(graph))
    payload = json.loads(handoff.model_dump_json())

    assert payload["safety_assessment_performed_by_component2"] is False
    herb = next(c for c in payload["candidates"] if c["candidate_id"] == "H-1")
    for field in (
        "category",
        "display_name",
        "claim_path",
        "claim_ids",
        "evidence_ids",
        "supporting_evidence",
        "contradicting_evidence",
        "verification_statuses",
        "rationale",
        "sufficiency_status",
        "uncertainty_flags",
        "review_required",
        "disposition",
    ):
        assert field in herb
    assert [e["evidence_id"] for e in herb["contradicting_evidence"]] == [
        "EV-HERB-CON"
    ]
    assert herb["supporting_evidence"][0]["citation"]


def test_audit_record_contains_ids_but_no_sensitive_input(caplog):
    output = run(build_pandu_graph())
    record = build_audit_record(output)

    assert record.request_id == "req-test-1"
    assert "CL-HERB" in record.claim_ids_traversed
    assert "EV-HERB" in record.evidence_ids_referenced
    assert set(record.candidate_ids_forwarded) == {"H-1", "F-1", "D-1", "L-1"}
    assert record.retrieval_mode == "neural_embedding"
    assert record.input_symptom_count == 1

    with caplog.at_level(logging.INFO, logger="ayurai.c2.audit"):
        emit_audit_record(record)
    logged = caplog.text
    assert "S-PALLOR" not in logged
    assert "0.97" not in logged
    assert '"high"' not in logged
    assert "req-test-1" in logged


def test_rejected_invalid_paths_are_reported():
    graph = build_pandu_graph()
    graph.add_concept("Herb", "H-BAD", "synthetic bad herb")
    graph.add_claim(
        "CL-BAD", "S-PALLOR", "USES_HERB", "H-BAD", supports=["EV-HERB"]
    )
    output = run(graph)

    assert "H-BAD" not in by_id(output)
    assert output.rejected_paths[0].claim_ids == ["CL-BAD"]
    assert "ontology_invalid_paths_rejected" in output.uncertainty_flags


def test_pipeline_without_retrieval_service_reports_not_run():
    output = run(build_pandu_graph(), retrieval=False)

    assert output.retrieval.mode == "not_run"
    assert output.abstention.abstain is True
