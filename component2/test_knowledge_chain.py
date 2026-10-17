from unittest.mock import patch

import pytest

from app.reasoning.knowledge_chain import trace_knowledge_chains


def make_claim(
    claim_id,
    subject_id,
    predicate,
    object_id,
    verification_status="unverified",
):
    return {
        "claim_id": claim_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "statement": f"Synthetic claim {claim_id}",
        "verification_status": verification_status,
    }


def make_record(claim):
    return {
        "claim": claim,
        "related_concept": {"concept_id": claim["object_id"]},
        "supporting_evidence": [],
        "contradicting_evidence": [],
    }


def make_evaluation(
    claim,
    supporting_count=0,
    contradicting_count=0,
):
    return {
        "claim": claim,
        "verification_status": claim["verification_status"],
        "stored_confidence": None,
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "evidence_summary": {
            "supporting_count": supporting_count,
            "contradicting_count": contradicting_count,
        },
        "reasoning_notes": [],
        "medical_conclusion": None,
    }


def test_traces_a_linear_knowledge_chain():
    claim_ab = make_claim("C-AB", "A", "INDICATES", "B")
    claim_bc = make_claim(
        "C-BC",
        "B",
        "ASSOCIATED_WITH_DOSHA",
        "C",
    )

    graph = {
        "A": [make_record(claim_ab)],
        "B": [make_record(claim_bc)],
        "C": [],
    }

    def connected(concept_id, driver=None):
        return graph.get(concept_id, [])

    def evaluate(claim_id, driver=None):
        claims = {"C-AB": claim_ab, "C-BC": claim_bc}
        return make_evaluation(claims[claim_id])

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            side_effect=connected,
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
            side_effect=evaluate,
        ),
    ):
        result = trace_knowledge_chains("A")

    assert result["start_concept_id"] == "A"
    assert len(result["chains"]) == 1

    chain = result["chains"][0]
    assert chain["concept_ids"] == ["A", "B", "C"]
    assert [item["claim_id"] for item in chain["claims"]] == [
        "C-AB",
        "C-BC",
    ]
    assert chain["termination_reason"] == "no_outgoing_claims"
    assert result["summary"]["unique_claim_count"] == 2
    assert result["medical_conclusion"] is None


def test_traces_multiple_branches():
    claim_ab = make_claim("C-AB", "A", "INDICATES", "B")
    claim_ac = make_claim("C-AC", "A", "INDICATES", "C")

    graph = {
        "A": [make_record(claim_ab), make_record(claim_ac)],
        "B": [],
        "C": [],
    }

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            side_effect=lambda concept_id, driver=None: graph.get(
                concept_id, []
            ),
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
            side_effect=lambda claim_id, driver=None: make_evaluation(
                {"C-AB": claim_ab, "C-AC": claim_ac}[claim_id]
            ),
        ),
    ):
        result = trace_knowledge_chains("A")

    assert len(result["chains"]) == 2
    assert {
        tuple(chain["concept_ids"])
        for chain in result["chains"]
    } == {
        ("A", "B"),
        ("A", "C"),
    }
    assert result["summary"]["unique_claim_count"] == 2


def test_prevents_cycles():
    claim_ab = make_claim("C-AB", "A", "INDICATES", "B")
    claim_ba = make_claim("C-BA", "B", "INDICATES", "A")

    graph = {
        "A": [make_record(claim_ab)],
        "B": [make_record(claim_ba)],
    }

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            side_effect=lambda concept_id, driver=None: graph.get(
                concept_id, []
            ),
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
            return_value=make_evaluation(claim_ab),
        ),
    ):
        result = trace_knowledge_chains("A")

    assert len(result["chains"]) == 1
    assert result["chains"][0]["concept_ids"] == ["A", "B"]
    assert result["chains"][0]["termination_reason"] == "cycle_prevented"


def test_respects_max_depth():
    claim_ab = make_claim("C-AB", "A", "INDICATES", "B")
    claim_bc = make_claim(
        "C-BC",
        "B",
        "ASSOCIATED_WITH_DOSHA",
        "C",
    )

    graph = {
        "A": [make_record(claim_ab)],
        "B": [make_record(claim_bc)],
        "C": [],
    }

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            side_effect=lambda concept_id, driver=None: graph.get(
                concept_id, []
            ),
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
            side_effect=lambda claim_id, driver=None: make_evaluation(
                {"C-AB": claim_ab, "C-BC": claim_bc}[claim_id]
            ),
        ),
    ):
        result = trace_knowledge_chains("A", max_depth=1)

    assert len(result["chains"]) == 1
    assert result["chains"][0]["concept_ids"] == ["A", "B"]
    assert result["chains"][0]["termination_reason"] == "max_depth"


def test_preserves_conflicting_evidence_summary():
    claim_ab = make_claim("C-AB", "A", "INDICATES", "B")

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            side_effect=lambda concept_id, driver=None: (
                [make_record(claim_ab)] if concept_id == "A" else []
            ),
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
            return_value=make_evaluation(
                claim_ab,
                supporting_count=1,
                contradicting_count=1,
            ),
        ),
    ):
        result = trace_knowledge_chains("A")

    assert result["summary"]["chains_with_conflicting_evidence"] == 1
    assert result["chains"][0]["claims"][0]["evaluation"][
        "evidence_summary"
    ] == {
        "supporting_count": 1,
        "contradicting_count": 1,
    }


def test_ignores_unsupported_predicates():
    invalid_claim = make_claim(
        "C-INVALID",
        "A",
        "UNKNOWN_RELATION",
        "B",
    )

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            return_value=[make_record(invalid_claim)],
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
        ) as evaluate_mock,
    ):
        result = trace_knowledge_chains("A")

    assert result["chains"] == []
    assert result["summary"]["unique_claim_count"] == 0
    evaluate_mock.assert_not_called()


def test_respects_max_chains_and_reports_truncation():
    claim_ab = make_claim("C-AB", "A", "INDICATES", "B")
    claim_ac = make_claim("C-AC", "A", "INDICATES", "C")

    graph = {
        "A": [make_record(claim_ab), make_record(claim_ac)],
        "B": [],
        "C": [],
    }

    with (
        patch(
            "app.reasoning.knowledge_chain.get_connected_knowledge",
            side_effect=lambda concept_id, driver=None: graph.get(
                concept_id, []
            ),
        ),
        patch(
            "app.reasoning.knowledge_chain.evaluate_claim",
            side_effect=lambda claim_id, driver=None: make_evaluation(
                {"C-AB": claim_ab, "C-AC": claim_ac}[claim_id]
            ),
        ),
    ):
        result = trace_knowledge_chains("A", max_chains=1)

    assert len(result["chains"]) == 1
    assert result["truncated"] is True


@pytest.mark.parametrize(
    "start_concept_id",
    ["", "   ", None, 123],
)
def test_rejects_invalid_start_concept(start_concept_id):
    with pytest.raises(ValueError, match="start_concept_id"):
        trace_knowledge_chains(start_concept_id)


@pytest.mark.parametrize(
    "max_depth",
    [0, -1, 9, True],
)
def test_rejects_invalid_max_depth(max_depth):
    with pytest.raises(ValueError, match="max_depth"):
        trace_knowledge_chains("A", max_depth=max_depth)


@pytest.mark.parametrize(
    "max_chains",
    [0, -1, True],
)
def test_rejects_invalid_max_chains(max_chains):
    with pytest.raises(ValueError, match="max_chains"):
        trace_knowledge_chains("A", max_chains=max_chains)