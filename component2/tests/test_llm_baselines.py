"""LLM baselines B1-B3 and the grounded explanation layer (mocked HTTP only)."""

import json
import socket
from pathlib import Path

import anthropic
import httpx2
import pytest

from app.config import RetrievalSettings
from app.llm import baselines
from app.llm.baselines import (
    RunOptions,
    build_prompt,
    load_scenarios,
    prepare_request,
    run_baselines,
    score_answer,
    write_report,
)
from app.llm.client import AnthropicClient, LLMRequestError, LLMResponse
from app.llm.config import LLMSettings
from app.llm.explanation import check_rephrasing, explain_output, provisional_ids
from app.llm.grounding import PROVISIONAL_LABEL
from app.models.c1_screening_payload import C1ScreeningPayload
from c2_test_support import KeywordEncoder
from memory_graph_test_support import load_synthetic_graph, memory_environment

SCENARIOS = Path(__file__).resolve().parents[1] / "samples" / "c1_screening_scenarios.json"
SETTINGS = LLMSettings(provider="anthropic", model="claude-opus-5-5", api_key="sk-test", max_retries=0)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("network access attempted in an LLM test")

    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture(scope="module")
def env():
    return memory_environment(
        load_synthetic_graph(),
        encoder=KeywordEncoder(),
        retrieval_settings=RetrievalSettings(embedding_model="test-keyword-encoder", min_similarity=0.0),
    )


@pytest.fixture(scope="module")
def scenarios():
    return {s["scenario_id"]: s for s in load_scenarios(SCENARIOS)}


def _payload(scenarios, scenario_id):
    return C1ScreeningPayload.model_validate(scenarios[scenario_id]["payload"])


def _c2_output(env, scenarios, scenario_id="syn-01-high-classic"):
    return env.run_reasoning(prepare_request(_payload(scenarios, scenario_id), env)["request"])


class ScriptedClient:
    """LLMClient double; the HTTP layer is covered by test_llm_adapter."""

    settings = SETTINGS

    def __init__(self, answer):
        self.answer = answer
        self.prompts = []

    def complete(self, system, prompt):
        self.prompts.append(prompt)
        text = self.answer(prompt) if callable(self.answer) else self.answer
        return LLMResponse(text=text, provider="anthropic", requested_model="claude-opus-5-5",
                           served_model="claude-opus-5-5", stop_reason="end_turn")


class FailingClient(ScriptedClient):
    def complete(self, system, prompt):
        raise LLMRequestError("Anthropic API error 529 (OverloadedError).", 529)


# --- request mapping and prompts ---------------------------------------------

def test_prepare_request_follows_c1_to_c2_rules(env, scenarios):
    assert prepare_request(_payload(scenarios, "syn-01-high-classic"), env)["request"].symptom_ids == [
        "S-PALLOR", "S-FATIGUE", "S-BREATHLESSNESS",
    ]
    assert prepare_request(_payload(scenarios, "syn-06-unsupported-tier"), env)["status"] == "blocked"
    assert prepare_request(_payload(scenarios, "syn-08-ambiguous-symptom"), env)["status"] == "insufficient_input"


def test_b1_has_no_knowledge_and_nothing_to_cite(env, scenarios):
    built = build_prompt("B1", _payload(scenarios, "syn-01-high-classic"), env)
    assert built["allowed_ids"] == set()
    assert "pallor, fatigue, shortness of breath" in built["prompt"]
    assert "EV-SBX" not in built["prompt"]


def test_b2_shows_retrieved_passages_only(env, scenarios):
    built = build_prompt("B2", _payload(scenarios, "syn-01-high-classic"), env)
    assert built["allowed_ids"] and all(i.startswith("EV-SBX-") for i in built["allowed_ids"])
    assert "CL-SBX" not in built["prompt"]
    for evidence_id in built["allowed_ids"]:
        assert f"[{evidence_id}]" in built["prompt"]


def test_b3_shows_c2_claims_once_with_their_evidence(env, scenarios):
    output = _c2_output(env, scenarios)
    built = build_prompt("B3", _payload(scenarios, "syn-01-high-classic"), env, output)
    prompt = built["prompt"]
    assert "Component 2 deterministic decision: caution" in prompt
    assert prompt.count("- [CL-SBX-TPA]") == 1
    assert {"CL-SBX-PALLOR", "EV-SBX-PALLOR", "S-PALLOR", "R-PANDU"} <= built["allowed_ids"]
    assert "Passages of the cited evidence:" in prompt and "- none available" not in prompt


def test_b3_labels_provisional_claims(env, scenarios):
    output = _c2_output(env, scenarios)
    claim = output.candidates[0].paths[0].claims[0]
    claim.knowledge_status = "provisional"
    built = build_prompt("B3", _payload(scenarios, "syn-01-high-classic"), env, output)
    assert claim.claim_id in built["provisional_ids"]
    assert f"[{claim.claim_id}] [provisional: {PROVISIONAL_LABEL}]" in built["prompt"]


# --- scoring ------------------------------------------------------------------

def test_score_flags_invented_ids_and_unsafe_phrasing():
    answer = json.dumps({
        "decision": "caution",
        "candidates": [{"name": "x", "category": "Herb", "cited_ids": ["EV-REAL", "EV-FAKE"]},
                       {"name": "y", "category": "Diet", "cited_ids": []}],
        "summary": "You have Pandu; take 5 g daily. See CL-MADEUP.",
        "cited_ids": ["EV-REAL"],
    })
    score = score_answer(answer, {"EV-REAL"}, set(), "caution", "abstain")
    assert score["parsed"] and score["decision_matches_expected"] is True
    assert score["decision_matches_reference"] is False
    assert score["unsupported_ids"] == ["CL-MADEUP", "EV-FAKE"]
    assert score["citation_precision"] == pytest.approx(1 / 3, abs=1e-3)
    assert score["candidates_without_citation"] == 1
    assert score["unsafe_phrasing"] == ["diagnosis", "dosage"]


def test_score_provisional_label_and_unparseable_answers():
    cites = json.dumps({"decision": "caution", "candidates": [], "summary": "s", "cited_ids": ["PCL-1"]})
    assert score_answer(cites, {"PCL-1"}, {"PCL-1"}, None)["provisional_label_ok"] is False
    labelled = cites.replace('"s"', f'"{PROVISIONAL_LABEL}: s"')
    assert score_answer(labelled, {"PCL-1"}, {"PCL-1"}, None)["provisional_label_ok"] is True
    broken = score_answer("not json, but cites EV-X", set(), set(), "abstain")
    assert broken["parsed"] is False and broken["decision_valid"] is False
    assert broken["unsupported_ids"] == ["EV-X"]


# --- runner -------------------------------------------------------------------

def _answer(prompt):
    if "Knowledge-graph reasoning output" in prompt:
        return json.dumps({"decision": "caution", "candidates": [
            {"name": "Sandbox herb one", "category": "Herb", "cited_ids": ["CL-SBX-PALLOR"]}],
            "summary": "For practitioner review.", "cited_ids": ["CL-SBX-PALLOR", "EV-SBX-PALLOR"]})
    if "Retrieved evidence passages" in prompt:
        return json.dumps({"decision": "caution", "candidates": [], "summary": "s",
                           "cited_ids": ["EV-SBX-PALLOR"]})
    return json.dumps({"decision": "recommend_for_review", "candidates": [
        {"name": "Punarnava", "category": "Herb", "cited_ids": ["CHARAKA-16"]}],
        "summary": "s", "cited_ids": []})


def test_run_baselines_scores_every_scenario(env, scenarios):
    client = ScriptedClient(_answer)
    run = run_baselines(list(scenarios.values()), env, client, RunOptions(explain=True))
    rows = {(r["scenario_id"], r["baseline"]): r for r in run["results"]}
    assert len(rows) == 3 * len(scenarios)

    b3 = rows[("syn-01-high-classic", "B3")]
    assert b3["status"] == "answered"
    assert b3["score"]["citation_precision"] == 1.0
    assert b3["score"]["decision_matches_reference"] is True
    assert rows[("syn-01-high-classic", "B1")]["score"]["unsupported_ids"] == ["CHARAKA-16"]
    assert rows[("syn-06-unsupported-tier", "B3")]["status"] == "skipped"
    assert "blocked" in rows[("syn-06-unsupported-tier", "B3")]["reason"]
    # B1 and B2 still answer scenarios Component 2 does not reason over.
    assert rows[("syn-06-unsupported-tier", "B1")]["status"] == "answered"

    summary = run["summary"]
    # The scripted B3 answer always cites the pallor claim: grounded for
    # syn-01, unsupported where that claim was never shown (no pallor).
    assert rows[("syn-07-symptom-without-claims", "B3")]["score"]["unsupported_ids"] == [
        "CL-SBX-PALLOR", "EV-SBX-PALLOR",
    ]
    assert summary["B3"]["unsupported_id_total"] > 0
    assert summary["B1"]["mean_citation_precision"] == 0.0
    assert summary["B3"]["answered"] == 5 and summary["B3"]["skipped_or_failed"] == 3
    assert {e["scenario_id"] for e in run["explanations"]} == {
        "syn-01-high-classic", "syn-02-moderate-fatigue", "syn-04-unknown-symptom",
        "syn-05-null-confidence", "syn-07-symptom-without-claims",
    }


def test_run_baselines_records_llm_errors(env, scenarios):
    run = run_baselines([scenarios["syn-01-high-classic"]], env, FailingClient(None),
                        RunOptions(baselines=("B1",)))
    assert run["results"][0]["status"] == "llm_error"
    assert "529" in run["results"][0]["error"]


def test_dry_run_builds_prompts_without_calling(env, scenarios):
    client = ScriptedClient(_answer)
    run = run_baselines(list(scenarios.values()), env, client, RunOptions(dry_run=True))
    assert client.prompts == []
    assert {r["status"] for r in run["results"]} == {"not_called", "skipped"}


def test_reports_are_new_files_and_never_overwrite(env, scenarios, tmp_path):
    run = run_baselines([scenarios["syn-01-high-classic"]], env, ScriptedClient(_answer), RunOptions())
    report = baselines.build_report(run, env, SCENARIOS, SETTINGS.describe(), RunOptions())
    assert "sk-test" not in json.dumps(report, default=str)
    existing = tmp_path / "keep.json"
    existing.write_text("baseline evaluation report", encoding="utf-8")
    first = write_report(report, tmp_path)
    second = write_report(report, tmp_path)
    assert first != second
    assert existing.read_text(encoding="utf-8") == "baseline evaluation report"
    assert json.loads(first[0].read_text(encoding="utf-8"))["metadata"]["llm"]["model"] == "claude-opus-5-5"
    assert "| B1 |" in first[1].read_text(encoding="utf-8")


def test_cli_dry_run_and_missing_key(env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(baselines, "live_environment", lambda scope: env)
    for name in ("C2_LLM_API_KEY", "ANTHROPIC_API_KEY", "C2_LLM_PROVIDER", "C2_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert baselines.main(["--out-dir", str(tmp_path)]) == 2
    assert "LLM not configured" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []

    assert baselines.main(["--dry-run", "--baselines", "B1,B3", "--out-dir", str(tmp_path)]) == 0
    files = sorted(p.suffix for p in tmp_path.iterdir())
    assert files == [".json", ".md"]
    with pytest.raises(SystemExit):
        baselines.main(["--baselines", "B9", "--dry-run", "--out-dir", str(tmp_path)])


# --- grounded explanation -----------------------------------------------------

def _rewrite_all(transform):
    def answer(prompt):
        items = json.loads(prompt.split("\n", 1)[1])
        return json.dumps({"statements": [
            {"index": item["index"], "text": transform(item["text"])} for item in items
        ]})
    return answer


def test_explanation_without_client_is_deterministic(env, scenarios):
    output = _c2_output(env, scenarios)
    explained = explain_output(output, None)
    assert explained.status == "deterministic_only"
    assert [s.text for s in explained.statements][: len(output.explanation)] == [
        s.text for s in output.explanation
    ]


def test_faithful_rephrasing_is_accepted_and_keeps_source_ids(env, scenarios):
    output = _c2_output(env, scenarios)
    explained = explain_output(output, ScriptedClient(_rewrite_all(lambda t: "In plain words: " + t)))
    assert explained.status == "rephrased"
    for statement in explained.statements:
        assert statement.rephrased and statement.text.startswith("In plain words: ")
    sources = {(s.kind, s.text): s for s in output.explanation}
    for statement in explained.statements:
        if (statement.kind, statement.source_text) in sources:
            original = sources[(statement.kind, statement.source_text)]
            assert statement.claim_ids == original.claim_ids
            assert statement.evidence_ids == original.evidence_ids


@pytest.mark.parametrize("transform, reason", [
    (lambda t: "A short summary.", "missing_ids"),
    (lambda t: t + " See also CL-INVENTED.", "added_ids"),
    (lambda t: t + " Take 3 doses.", "added_numbers"),
    (lambda t: t + " This will cure the patient.", "unsafe_phrasing"),
    (lambda t: "", "empty"),
])
def test_unfaithful_rephrasing_falls_back_to_source(env, scenarios, transform, reason):
    output = _c2_output(env, scenarios)
    explained = explain_output(output, ScriptedClient(_rewrite_all(transform)))
    candidate_path = next(s for s in explained.statements if s.kind == "candidate_path")
    assert not candidate_path.rephrased
    assert candidate_path.rejection_reason.startswith(reason)
    assert candidate_path.text == candidate_path.source_text


def test_missing_rewrites_and_llm_failure_keep_deterministic_text(env, scenarios):
    output = _c2_output(env, scenarios)
    partial = explain_output(output, ScriptedClient('{"statements": [{"index": 0, "text": "x"}]}'))
    assert partial.status in {"partially_rephrased", "deterministic_only"}
    assert {s.rejection_reason for s in partial.statements[1:]} == {"not_returned"}
    failed = explain_output(output, FailingClient(None))
    assert failed.status == "llm_unavailable"
    assert all(not s.rephrased for s in failed.statements)


def test_provisional_statements_always_carry_the_label(env, scenarios):
    output = _c2_output(env, scenarios)
    claim = output.candidates[0].paths[0].claims[0]
    claim.knowledge_status = "provisional"
    assert claim.claim_id in provisional_ids(output)

    deterministic = explain_output(output, None)
    rephrased = explain_output(output, ScriptedClient(_rewrite_all(lambda t: "Plainly: " + t)))
    for explained in (deterministic, rephrased):
        flagged = [s for s in explained.statements if s.provisional]
        assert flagged
        for statement in flagged:
            assert claim.claim_id in statement.claim_ids
            assert statement.text.startswith(f"{PROVISIONAL_LABEL}: ")
        assert all(
            not s.text.startswith(PROVISIONAL_LABEL) for s in explained.statements if not s.provisional
        )


def test_explanation_is_sent_in_batches_and_survives_a_failed_batch(env, scenarios):
    output = _c2_output(env, scenarios)
    rewrite = _rewrite_all(lambda t: "Plainly: " + t)
    calls = []

    class OneBatchFails(ScriptedClient):
        def complete(self, system, prompt):
            calls.append(prompt)
            if len(calls) == 2:
                raise LLMRequestError("Anthropic API error 500 (InternalServerError).", 500)
            return super().complete(system, prompt)

    explained = explain_output(output, OneBatchFails(rewrite))
    total = len(explained.statements)
    assert len(calls) == -(-total // 15) > 1
    assert explained.status == "partially_rephrased"
    lost = [s for s in explained.statements if not s.rephrased]
    assert len(lost) == 15 and {s.rejection_reason for s in lost} == {"not_returned"}


def test_component2_failure_is_recorded_and_the_run_continues(env, scenarios):
    def broken(request):
        raise OSError("graph unavailable")

    failing_env = baselines.BaselineEnvironment(
        graph_source="test", knowledge_scope="approved",
        resolve_symptom=env.resolve_symptom, run_reasoning=broken, retrieval=env.retrieval,
    )
    messages = []
    options = RunOptions(baselines=("B1", "B3"), progress=messages.append)
    run = run_baselines(list(scenarios.values()), failing_env, ScriptedClient(_answer), options)
    b3 = {r["scenario_id"]: r for r in run["results"] if r["baseline"] == "B3"}
    assert "c2_error:OSError: graph unavailable" in b3["syn-01-high-classic"]["reason"]
    assert all(r["status"] == "answered" for r in run["results"] if r["baseline"] == "B1")
    assert sum("done in" in m for m in messages) == len(scenarios)
    assert run["interrupted"] is False


def test_ctrl_c_keeps_finished_scenarios(env, scenarios):
    class StopsOnSecond(ScriptedClient):
        def complete(self, system, prompt):
            if "fatigue" in prompt and "pallor" not in prompt.split("present:")[1].split("\n")[0]:
                raise KeyboardInterrupt
            return super().complete(system, prompt)

    run = run_baselines(list(scenarios.values()), env, StopsOnSecond(_answer),
                        RunOptions(baselines=("B1",)))
    assert run["interrupted"] is True
    assert [r["scenario_id"] for r in run["results"]] == ["syn-01-high-classic"]
    assert "INTERRUPTED" in baselines.markdown_report(
        baselines.build_report(run, env, SCENARIOS, SETTINGS.describe(), RunOptions())
    )


def test_check_rephrasing_ignores_digits_inside_ids():
    source = "Claim CL-SBX-D1 is supported by EV-SBX-D1."
    assert check_rephrasing(source, "EV-SBX-D1 supports claim CL-SBX-D1.", set()) is None


def test_explanation_through_mocked_claude_http(env, scenarios):
    output = _c2_output(env, scenarios, "syn-07-symptom-without-claims")
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        items = json.loads(body["messages"][0]["content"].split("\n", 1)[1])
        text = json.dumps({"statements": [{"index": i["index"], "text": i["text"]} for i in items]})
        return httpx2.Response(200, json={
            "id": "msg", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    client = AnthropicClient(SETTINGS, http_client=anthropic.DefaultHttpxClient(
        transport=httpx2.MockTransport(handler)))
    explained = explain_output(output, client)
    assert len(requests) == 1
    assert explained.status == "rephrased"
    assert explained.served_model == "claude-opus-5-5"
