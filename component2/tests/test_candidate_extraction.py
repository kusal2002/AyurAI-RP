import pytest

from app.reasoning.candidates import extract_candidate_paths
from app.reasoning.knowledge_chain import trace_knowledge_chains
from c2_test_support import build_pandu_graph


def extract(graph, start="S-PALLOR"):
    with graph.patched():
        result = trace_knowledge_chains(start)
        concept_ids = {
            cid for chain in result["chains"] for cid in chain["concept_ids"]
        }
        concepts = graph.get_concepts(concept_ids)
    return extract_candidate_paths([result], concepts)


def test_extracts_each_candidate_category():
    extracted = extract(build_pandu_graph())
    paths = extracted["candidate_paths"]

    assert set(paths) == {"H-1", "F-1", "D-1", "L-1"}
    assert {
        cid: paths[cid][0].claims[-1].object_type for cid in paths
    } == {
        "H-1": "Herb",
        "F-1": "Formulation",
        "D-1": "Diet",
        "L-1": "Lifestyle",
    }


def test_preserves_path_direction_claims_and_statuses():
    extracted = extract(build_pandu_graph())
    path = extracted["candidate_paths"]["H-1"][0]

    assert path.concept_ids == ["S-PALLOR", "R-PANDU", "TP-1", "H-1"]
    assert [c.claim_id for c in path.claims] == ["CL-IND", "CL-TP", "CL-HERB"]
    assert [(c.subject_id, c.object_id) for c in path.claims] == [
        ("S-PALLOR", "R-PANDU"),
        ("R-PANDU", "TP-1"),
        ("TP-1", "H-1"),
    ]
    assert path.claims[0].statement == "pallor indicates pandu"
    assert all(
        c.verification_status == "literature_supported" for c in path.claims
    )


def test_interpretation_contains_roga_and_principle_not_candidates():
    extracted = extract(build_pandu_graph())
    concepts = {c.concept_id: c for c in extracted["interpretation"]}

    assert set(concepts) == {"R-PANDU", "TP-1"}
    assert concepts["R-PANDU"].concept_type == "Roga"
    assert concepts["R-PANDU"].via_claim_ids == ["CL-IND"]
    assert concepts["R-PANDU"].supporting_evidence_ids == ["EV-IND"]


def test_retains_supporting_and_contradicting_evidence():
    graph = build_pandu_graph(herb_contradicts=["EV-HERB-CON"])
    herb_claim = extract(graph)["candidate_paths"]["H-1"][0].claims[-1]

    assert [e.evidence_id for e in herb_claim.supporting_evidence] == [
        "EV-HERB"
    ]
    assert [e.evidence_id for e in herb_claim.contradicting_evidence] == [
        "EV-HERB-CON"
    ]


def test_missing_evidence_has_no_fabricated_provenance():
    graph = build_pandu_graph(herb_supports=())
    herb_claim = extract(graph)["candidate_paths"]["H-1"][0].claims[-1]

    assert herb_claim.supporting_evidence == []
    assert herb_claim.contradicting_evidence == []


def test_unverified_and_disputed_statuses_are_not_promoted():
    for status in ("unverified", "disputed"):
        graph = build_pandu_graph(herb_status=status)
        herb_claim = extract(graph)["candidate_paths"]["H-1"][0].claims[-1]
        assert herb_claim.verification_status == status


def test_rejects_ontology_invalid_paths_from_direct_inserts():
    graph = build_pandu_graph()
    # Directly inserted data: a Herb used directly by a Roga is not allowed.
    graph.add_concept("Herb", "H-BAD", "synthetic bad herb")
    graph.add_claim(
        "CL-BAD", "R-PANDU", "USES_HERB", "H-BAD", supports=["EV-HERB"]
    )
    extracted = extract(graph)

    assert "H-BAD" not in extracted["candidate_paths"]
    rejected = extracted["rejected_paths"]
    assert len(rejected) == 1
    assert rejected[0].claim_ids == ["CL-IND", "CL-BAD"]
    assert rejected[0].reason.startswith("ontology_violation:CL-BAD")


def test_rejects_path_with_missing_concept_metadata():
    graph = build_pandu_graph()
    del graph.concepts["TP-1"]
    extracted = extract(graph)

    assert extracted["candidate_paths"] == {}
    assert any(
        r.reason == "missing_concept:TP-1" for r in extracted["rejected_paths"]
    )


def test_rejects_ambiguous_concept_type():
    graph = build_pandu_graph()
    graph.add_concept(
        "Herb", "H-1", "synthetic herb", extra_labels=("Formulation",)
    )
    extracted = extract(graph)

    assert "H-1" not in extracted["candidate_paths"]
    assert any(
        r.reason == "ambiguous_concept_type:H-1"
        for r in extracted["rejected_paths"]
    )


def test_missing_name_is_kept_as_none():
    graph = build_pandu_graph()
    graph.add_concept("Herb", "H-1")  # no name stored
    extracted = extract(graph)

    assert "H-1" in extracted["candidate_paths"]


def test_candidate_reached_by_multiple_paths_is_deduplicated():
    graph = build_pandu_graph()
    graph.add_concept("Dosha", "DO-1", "synthetic dosha")
    graph.add_evidence("EV-DO", "Synthetic dosha text.")
    graph.add_claim(
        "CL-DO", "R-PANDU", "ASSOCIATED_WITH_DOSHA", "DO-1",
        supports=["EV-DO"],
    )
    graph.add_claim(
        "CL-DO-TP", "DO-1", "SUGGESTS_PRINCIPLE", "TP-1",
        supports=["EV-DO"],
    )
    paths = extract(graph)["candidate_paths"]

    herb_paths = paths["H-1"]
    assert len(herb_paths) == 2
    assert {tuple(c.claim_id for c in p.claims) for p in herb_paths} == {
        ("CL-IND", "CL-TP", "CL-HERB"),
        ("CL-IND", "CL-DO", "CL-DO-TP", "CL-HERB"),
    }


@pytest.mark.parametrize("field", ["title", "citation"])
def test_flags_incomplete_provenance(field):
    graph = build_pandu_graph()
    graph.evidence["EV-HERB"][field] = None
    if field == "citation":
        for locator in ("page", "section", "source_url"):
            graph.evidence["EV-HERB"][locator] = None
    herb_claim = extract(graph)["candidate_paths"]["H-1"][0].claims[-1]
    reference = herb_claim.supporting_evidence[0]

    assert reference.provenance_complete is False
    assert reference.missing_provenance
