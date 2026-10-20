"""Reference-derived C1 samples (NHANES reader) and the C1 scenario paths."""

import json
import struct
from pathlib import Path

import pytest

from app.integration.c1_reference_samples import (
    TIER_BY_SEVERITY,
    _ibm_to_float,
    build_payload,
    read_xpt,
    who_2024_severity,
)

SAMPLES = Path(__file__).parent / "samples"


def _ibm(value: float | None) -> bytes:
    """Encode a float as an IBM 8-byte float (test helper)."""
    if value is None:
        return b"." + b"\x00" * 7
    if value == 0:
        return b"\x00" * 8
    sign = 0x80 if value < 0 else 0
    value = abs(value)
    exponent = 0
    while value >= 1:
        value /= 16
        exponent += 1
    while value < 1 / 16:
        value *= 16
        exponent -= 1
    mantissa = int(round(value * (1 << 56)))
    return bytes([sign | (exponent + 64)]) + mantissa.to_bytes(7, "big")


def _write_xpt(path: Path, names: list[str], rows: list[list[float | None]]) -> None:
    def record(text: str) -> bytes:
        return text.encode("ascii").ljust(80, b" ")

    out = b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!000000000000000000000000000000  "
    out += record("SAS     SAS     SASLIB  9.4") + record("")
    out += record("HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!000000000000000001600000000140")
    out += record("HEADER RECORD*******DSCRPTR HEADER RECORD!!!!!!!000000000000000000000000000000")
    out += record("SAS     TEST") + record("")
    out += record("HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!000000" + f"{len(names):04d}" + "00000000000000000000")
    namestrs = b""
    for index, name in enumerate(names):
        rec = struct.pack(">hhhh", 1, 0, 8, index + 1) + name.encode().ljust(8)
        rec = rec.ljust(84, b"\x00") + struct.pack(">i", index * 8)
        namestrs += rec.ljust(140, b"\x00")
    namestrs += b" " * ((-len(namestrs)) % 80)
    out += namestrs
    out += record("HEADER RECORD*******OBS     HEADER RECORD!!!!!!!000000000000000000000000000000")
    data = b"".join(_ibm(v) for row in rows for v in row)
    out += data + b" " * ((-len(data)) % 80)
    path.write_bytes(out)


def test_ibm_float_round_trip_and_missing():
    for value in (13.7, 0.5, 109264.0, 2.0, 1.0):
        assert _ibm_to_float(_ibm(value)) == pytest.approx(value)
    assert _ibm_to_float(b"." + b"\x00" * 7) is None
    assert _ibm_to_float(b"\x00" * 8) == 0.0


def test_read_xpt_rows_and_column_filter(tmp_path):
    path = tmp_path / "t.xpt"
    _write_xpt(path, ["SEQN", "LBXHGB"], [[1.0, 13.7], [2.0, None], [3.0, 9.4]])
    rows = read_xpt(path)
    assert rows == [{"SEQN": 1.0, "LBXHGB": pytest.approx(13.7)},
                    {"SEQN": 2.0, "LBXHGB": None},
                    {"SEQN": 3.0, "LBXHGB": pytest.approx(9.4)}]
    assert read_xpt(path, {"SEQN"}) == [{"SEQN": 1.0}, {"SEQN": 2.0}, {"SEQN": 3.0}]


def test_read_xpt_rejects_other_files(tmp_path):
    path = tmp_path / "x.xpt"
    path.write_bytes(b"not sas")
    with pytest.raises(ValueError):
        read_xpt(path)


@pytest.mark.parametrize("hb, sex, severity", [
    (12.0, "female", "none"), (11.9, "female", "mild"), (11.0, "female", "mild"),
    (10.9, "female", "moderate"), (7.9, "female", "severe"),
    (13.0, "male", "none"), (12.9, "male", "mild"), (11.0, "male", "mild"), (10.9, "male", "moderate"),
])
def test_who_2024_table_3_boundaries(hb, sex, severity):
    assert who_2024_severity(hb, sex) == severity


def test_payload_never_invents_answers_or_confidence():
    payload = build_payload(111, "female", 47, 10.2, dpq040=None, cdq010=1.0)
    assert payload.screening_result.risk_level == TIER_BY_SEVERITY["moderate"] == "high"
    assert payload.screening_result.screening_confidence is None
    assert payload.screening_result.status == "reference_derived_not_model_output"
    assert [s.model_dump() for s in payload.symptoms] == [{"name": "breathlessness", "present": True}]
    assert "questionnaire:fatigue" in payload.missing_data
    refused = build_payload(112, "male", 50, 14.0, dpq040=7.0, cdq010=2.0)
    assert {s.name: s.present for s in refused.symptoms} == {"breathlessness": False}


# --- C1 scenarios over the in-memory test graph ------------------------------

@pytest.fixture(scope="module")
def graph_client():
    """The real API with graph reads served by the synthetic test graph."""
    from fastapi.testclient import TestClient

    import app.api.c2 as c2_api
    import app.integration.c1_to_c2 as c1_to_c2
    import app.reasoning.evaluator as evaluator
    import app.reasoning.knowledge_chain as knowledge_chain
    import app.reasoning.pipeline as pipeline
    import app.reasoning.symptom_reasoner as symptom_reasoner
    from app.config import RetrievalSettings
    from app.main import app
    from app.retrieval.service import EvidenceRetrievalService, get_retrieval_service
    from c2_test_support import KeywordEncoder
    from memory_graph_test_support import load_synthetic_graph

    graph = load_synthetic_graph()
    patches = pytest.MonkeyPatch()
    patches.setattr(symptom_reasoner, "get_symptom", graph.get_symptom)
    patches.setattr(symptom_reasoner, "get_claims_for_concept", graph.get_claims_for_concept)
    patches.setattr(knowledge_chain, "get_connected_knowledge", graph.get_connected_knowledge)
    patches.setattr(evaluator, "get_evidence_for_claim", graph.get_evidence_for_claim)
    patches.setattr(pipeline, "get_concepts", graph.get_concepts)
    patches.setattr(c1_to_c2, "resolve_symptom_reference", graph.resolve_symptom_reference)
    service = EvidenceRetrievalService(
        settings=RetrievalSettings(embedding_model="test-keyword-encoder", min_similarity=0.0),
        encoder=KeywordEncoder(), evidence_loader=lambda driver: graph.list_evidence(),
    )
    app.dependency_overrides[c2_api.get_driver] = lambda: None
    app.dependency_overrides[get_retrieval_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()
    patches.undo()


def _scenarios():
    return {s["scenario_id"]: s["payload"]
            for s in json.loads((SAMPLES / "c1_screening_scenarios.json").read_text(encoding="utf-8"))["scenarios"]}


@pytest.mark.parametrize("scenario, status, reason", [
    ("syn-01-high-classic", "completed", None),
    ("syn-03-low-no-symptoms", "insufficient_input", "no_present_symptoms_resolved"),
    ("syn-06-unsupported-tier", "blocked", "unsupported_upstream_risk_tier"),
    ("syn-08-ambiguous-symptom", "insufficient_input", "no_present_symptoms_resolved"),
])
def test_scenarios_take_the_expected_path(graph_client, scenario, status, reason):
    body = graph_client.post("/api/v1/c1/reasoning", json=_scenarios()[scenario]).json()
    assert body["status"] == status
    assert body["mapping"]["reason"] == reason


def test_classic_scenario_exercises_every_candidate_status(graph_client):
    body = graph_client.post("/api/v1/c1/reasoning", json=_scenarios()["syn-01-high-classic"]).json()
    statuses = {c["candidate_id"]: c["sufficiency"]["status"] for c in body["reasoning"]["candidates"]}
    assert statuses["H-SANDBOX-2"] == "conflicting_evidence"
    assert statuses["H-SANDBOX-3"] == "unverified_claims"
    assert statuses["F-SANDBOX-1"] == "insufficient_evidence"
    resolved = {r["input_name"]: r["symptom_id"] for r in body["mapping"]["resolved_symptoms"]}
    assert resolved["shortness of breath"] == "S-BREATHLESSNESS"


def test_unknown_and_ambiguous_symptoms_are_reported_not_guessed(graph_client):
    unknown = graph_client.post("/api/v1/c1/reasoning", json=_scenarios()["syn-04-unknown-symptom"]).json()
    assert {u["input_name"]: u["status"] for u in unknown["mapping"]["unresolved_symptoms"]} == {"hair loss": "not_found"}
    ambiguous = graph_client.post("/api/v1/c1/reasoning", json=_scenarios()["syn-08-ambiguous-symptom"]).json()
    [entry] = ambiguous["mapping"]["unresolved_symptoms"]
    assert entry["status"] == "ambiguous" and set(entry["candidate_ids"]) == {"S-FATIGUE", "S-GENERAL-WEAKNESS"}


def test_scenarios_reach_their_expected_decision(graph_client):
    scenarios = json.loads((SAMPLES / "c1_screening_scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    for scenario in scenarios:
        body = graph_client.post("/api/v1/c1/reasoning", json=scenario["payload"]).json()
        decision = (body.get("reasoning") or {}).get("decision")
        assert decision == scenario["expected_decision"], scenario["scenario_id"]
