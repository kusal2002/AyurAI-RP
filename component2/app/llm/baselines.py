"""Research baselines B1 (LLM only), B2 (vector RAG) and B3 (KG + RAG).

Each baseline answers the same Component 1 screening scenario with the
same JSON answer format, so the answers can be scored identically:

- B1 sees only the screening summary (no knowledge base).
- B2 also sees evidence passages retrieved by the existing embedding
  retrieval service for the symptom names.
- B3 also sees the Component 2 reasoning output (claim paths, statuses,
  candidates, deterministic decision) plus the passages of the evidence
  those claims cite.

Component 2 runs over the live Neo4j AuraDB graph (configured in .env).

Scoring is deterministic (no LLM judge): JSON validity, agreement with the
Component 2 decision, decision agreement with the scenario's expected
decision (written for the retired synthetic graph, so only indicative on
live data), citation grounding against the IDs
actually shown to the model, provisional labelling and unsafe-phrasing
heuristics. These are research measurements, not clinical validation.

Usage (from component2/):
    python -m app.llm.baselines [--baselines B1,B2,B3]
        [--knowledge-scope approved_and_provisional|approved]
        [--scenarios samples/c1_screening_scenarios.json] [--explain] [--dry-run]

Reports are written to new timestamped files and never overwrite an
existing report.
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.llm.client import LLMClient, LLMRequestError, create_llm_client
from app.llm.config import LLMConfigurationError
from app.llm.grounding import (
    PROVISIONAL_LABEL,
    extract_ids,
    has_provisional_label,
    parse_json_object,
    unsafe_phrases,
)
from app.models.c1_input import Component2ReasoningRequest, RiskTier
from app.models.c1_screening_payload import C1ScreeningPayload
from app.models.c2_output import Component2Output, Decision

COMPONENT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIOS = COMPONENT_ROOT / "samples" / "c1_screening_scenarios.json"
DEFAULT_OUT_DIR = COMPONENT_ROOT / "corpus" / "extracted" / "eval" / "llm_baselines"
BASELINES = ("B1", "B2", "B3")
PROMPT_VERSION = "llm-baselines-v1"
DECISIONS = tuple(d.value for d in Decision)
MAX_PASSAGES = 8
MAX_PASSAGE_CHARS = 700

SYSTEM_PROMPT = f"""You are one baseline in a research evaluation of decision-support \
systems for Ayurvedic practitioners. The input is a synthetic anaemia screening result. \
You never diagnose, prescribe, give doses, or promise that anything is safe or effective; \
every output is only material for a qualified practitioner to review.

Answer with one JSON object and nothing else:
{{"decision": "recommend_for_review" | "caution" | "abstain",
  "candidates": [{{"name": string, "category": "Herb" | "Formulation" | "Diet" | "Lifestyle", "cited_ids": [string]}}],
  "summary": string,
  "cited_ids": [string]}}

decision meanings: recommend_for_review = the evidence shown is enough to put candidates \
in front of a practitioner; caution = candidates may be shown but with explicit caution \
(high upstream risk, missing confidence, conflicting or unverified evidence); abstain = \
the evidence shown is not enough to suggest anything.
Cite only identifiers that appear in the provided context, copied exactly. Never invent \
identifiers, sources or quotations. If an item is marked provisional, any statement that \
relies on it must include the exact label "{PROVISIONAL_LABEL}". Keep the summary under \
120 words."""


# --- scenarios and environment -------------------------------------------------

def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = data["scenarios"] if isinstance(data, dict) else data
    for scenario in scenarios:
        if "scenario_id" not in scenario or "payload" not in scenario:
            raise ValueError("Every scenario needs scenario_id and payload.")
    return scenarios


@dataclass
class BaselineEnvironment:
    """Graph and retrieval access shared by all baselines."""

    graph_source: str
    knowledge_scope: str
    # symptom reference -> {"status", "symptom", "candidates"}
    resolve_symptom: Callable[[str], dict[str, Any]]
    run_reasoning: Callable[[Component2ReasoningRequest], Component2Output]
    retrieval: Any = None
    close: Callable[[], None] = lambda: None


def live_environment(knowledge_scope: str = "approved") -> BaselineEnvironment:
    """Neo4j AuraDB from .env. Provisional records need approved_and_provisional."""
    from app.db.neo4j import close_neo4j_driver, get_neo4j_driver
    from app.db.repository import resolve_symptom_reference
    from app.reasoning.pipeline import run_component2_reasoning
    from app.retrieval.service import get_research_retrieval_service, get_retrieval_service

    driver = get_neo4j_driver()
    graph = None
    retrieval = get_retrieval_service()
    if knowledge_scope == "approved_and_provisional":
        from app.db.research_repository import ResearchGraphAccess

        graph = ResearchGraphAccess(driver)
        retrieval = get_research_retrieval_service()
    retrieval.ensure_ready(driver)
    return BaselineEnvironment(
        graph_source="live:neo4j",
        knowledge_scope=knowledge_scope,
        resolve_symptom=lambda reference: resolve_symptom_reference(reference, driver),
        run_reasoning=lambda request: run_component2_reasoning(
            request, driver=driver, retrieval_service=retrieval, graph=graph
        ),
        retrieval=retrieval,
        close=close_neo4j_driver,
    )


def prepare_request(payload: C1ScreeningPayload, env: BaselineEnvironment) -> dict[str, Any]:
    """Same mapping rules as app.integration.c1_to_c2, over env's resolver."""
    try:
        risk_tier = RiskTier(payload.screening_result.risk_level.strip().lower())
    except ValueError:
        return {"status": "blocked", "reason": "unsupported_upstream_risk_tier", "request": None}
    symptom_ids: list[str] = []
    for symptom in payload.symptoms:
        if not symptom.present:
            continue
        result = env.resolve_symptom(symptom.name)
        symptom_id = (result.get("symptom") or {}).get("symptom_id")
        if result["status"] == "resolved" and symptom_id and symptom_id not in symptom_ids:
            symptom_ids.append(symptom_id)
    if not symptom_ids:
        return {"status": "insufficient_input", "reason": "no_present_symptoms_resolved", "request": None}
    request = Component2ReasoningRequest(
        risk_tier=risk_tier,
        calibrated_confidence=payload.screening_result.screening_confidence,
        symptom_ids=symptom_ids,
    )
    return {"status": "ready", "reason": None, "request": request}


# --- context building ----------------------------------------------------------

def screening_summary(payload: C1ScreeningPayload) -> str:
    result = payload.screening_result
    present = [s.name for s in payload.symptoms if s.present]
    absent = [s.name for s in payload.symptoms if not s.present]
    confidence = (
        "not provided" if result.screening_confidence is None else f"{result.screening_confidence:.2f}"
    )
    return (
        f"Screening (synthetic): condition {result.condition}; upstream risk tier "
        f"{result.risk_level}; screening confidence {confidence}.\n"
        f"Symptoms reported present: {', '.join(present) or 'none'}.\n"
        f"Symptoms reported absent: {', '.join(absent) or 'none'}."
    )


def _passage_lines(chunks) -> list[str]:
    lines = []
    for item in chunks[:MAX_PASSAGES]:
        chunk = item.chunk
        status = chunk.knowledge_status or "approved"
        label = f" [provisional: {PROVISIONAL_LABEL}]" if status == "provisional" else ""
        text = " ".join(chunk.text.split())[:MAX_PASSAGE_CHARS]
        lines.append(
            f"- [{chunk.evidence_id}]{label} {chunk.title or 'untitled'}"
            f" ({chunk.source_name or 'unknown source'}): {text}"
        )
    return lines


def _unique_by_evidence(chunks):
    seen, unique = set(), []
    for item in chunks:
        if item.chunk.evidence_id not in seen:
            seen.add(item.chunk.evidence_id)
            unique.append(item)
    return unique


def retrieve_passages(env: BaselineEnvironment, query: str, evidence_ids=None):
    """Retrieved chunks (one per evidence record), or raises on failure."""
    retrieval = env.retrieval
    if retrieval is None:
        raise RuntimeError("no retrieval service configured")
    if not retrieval.ensure_ready(None):
        raise RuntimeError(retrieval.last_error or "retrieval unavailable")
    return _unique_by_evidence(
        retrieval.search(
            query,
            top_k=MAX_PASSAGES * 2,
            restrict_to_evidence_ids=evidence_ids,
            include_below_threshold=evidence_ids is not None,
        )
    )


def c2_context(output: Component2Output) -> tuple[list[str], set[str], set[str]]:
    """Lines describing the C2 output, the IDs shown, and provisional IDs."""
    lines = [
        f"Component 2 deterministic decision: {output.decision.value} "
        f"(reasons: {', '.join(output.decision_reasons) or 'none'}); "
        f"sufficiency {output.sufficiency_status.value}; knowledge scope {output.knowledge_scope}."
    ]
    shown: set[str] = set()
    provisional: set[str] = set()
    for mapping in output.symptom_mappings:
        lines.append(
            f"Symptom {mapping.symptom_id} ({mapping.name or 'unknown'}): "
            f"{'found' if mapping.found else 'not found'}."
        )
        shown.add(mapping.symptom_id)
    for concept in output.interpretation:
        lines.append(
            f"Interpretation {concept.concept_type} {concept.concept_id} ({concept.name}): "
            f"graph association via {', '.join(concept.via_claim_ids)}, not a diagnosis."
        )
        shown.add(concept.concept_id)
    claims = {}
    for candidate in output.candidates:
        paths = "; ".join(
            " -> ".join(path.concept_ids) + " via " + ", ".join(c.claim_id for c in path.claims)
            for path in candidate.paths
        )
        lines.append(
            f"Candidate {candidate.candidate_id} {candidate.name} ({candidate.category.value}): "
            f"disposition {candidate.disposition.value}; sufficiency "
            f"{candidate.sufficiency.status.value}; flags "
            f"{', '.join(candidate.sufficiency.uncertainty_flags) or 'none'}; paths {paths}."
        )
        shown.add(candidate.candidate_id)
        for path in candidate.paths:
            shown.update(path.concept_ids)
            claims.update({claim.claim_id: claim for claim in path.claims})
    if claims:
        lines.append("Claims:")
    for claim in claims.values():
        is_provisional = claim.knowledge_status == "provisional"
        label = f" [provisional: {PROVISIONAL_LABEL}]" if is_provisional else ""
        supporting = [ref.evidence_id for ref in claim.supporting_evidence]
        contradicting = [ref.evidence_id for ref in claim.contradicting_evidence]
        lines.append(
            f"- [{claim.claim_id}]{label} {claim.subject_id} {claim.predicate} "
            f"{claim.object_id}; status {claim.verification_status}; "
            f'statement "{claim.statement or ""}"; supported by '
            f"{', '.join(supporting) or 'none'}; contradicted by "
            f"{', '.join(contradicting) or 'none'}."
        )
        shown.update([claim.claim_id, *supporting, *contradicting])
        if is_provisional:
            provisional.add(claim.claim_id)
        for ref in claim.supporting_evidence + claim.contradicting_evidence:
            if ref.knowledge_status == "provisional":
                provisional.add(ref.evidence_id)
    if not output.candidates:
        lines.append("No candidates were reached.")
    return lines, shown, provisional


def build_prompt(baseline: str, payload: C1ScreeningPayload, env: BaselineEnvironment | None,
                 c2_output: Component2Output | None = None) -> dict[str, Any]:
    """Prompt text plus the IDs shown to the model. Raises on retrieval failure."""
    sections = [screening_summary(payload)]
    allowed: set[str] = set()
    provisional: set[str] = set()
    if baseline == "B1":
        sections.append(
            "No knowledge base is available to you. Answer from general knowledge only; "
            "cited_ids must be empty because there is nothing to cite."
        )
    elif baseline == "B2":
        names = [s.name for s in payload.symptoms if s.present]
        query = "Ayurvedic knowledge relevant to: " + (", ".join(names) or "no symptoms")
        chunks = retrieve_passages(env, query)
        sections.append(
            "Retrieved evidence passages (vector search; use only these):\n"
            + ("\n".join(_passage_lines(chunks)) or "- none retrieved")
        )
        allowed = {item.chunk.evidence_id for item in chunks[:MAX_PASSAGES]}
        provisional = {
            item.chunk.evidence_id for item in chunks[:MAX_PASSAGES]
            if item.chunk.knowledge_status == "provisional"
        }
    elif baseline == "B3":
        lines, allowed, provisional = c2_context(c2_output)
        evidence_ids = sorted({
            evidence_id
            for candidate in c2_output.candidates
            for evidence_id in candidate.supporting_evidence_ids + candidate.contradicting_evidence_ids
        })
        passages: list[str] = []
        if evidence_ids:
            query = " ".join(m.name for m in c2_output.symptom_mappings if m.name) or "evidence"
            try:
                passages = _passage_lines(retrieve_passages(env, query, evidence_ids))
            except Exception:  # passages are optional context for B3
                passages = []
        sections.append("Knowledge-graph reasoning output (Component 2):\n" + "\n".join(lines))
        sections.append(
            "Passages of the cited evidence:\n" + ("\n".join(passages) or "- none available")
        )
    else:
        raise ValueError(f"Unknown baseline {baseline}.")
    sections.append("Return the JSON object now.")
    return {"prompt": "\n\n".join(sections), "allowed_ids": allowed, "provisional_ids": provisional}


# --- scoring -------------------------------------------------------------------

def score_answer(text: str, allowed_ids: set[str], provisional_ids: set[str],
                 expected_decision: str | None, reference_decision: str | None = None) -> dict[str, Any]:
    parsed = parse_json_object(text)
    decision = parsed.get("decision") if parsed else None
    candidates = parsed.get("candidates") if parsed and isinstance(parsed.get("candidates"), list) else []
    cited: set[str] = set()
    if parsed:
        cited.update(str(i) for i in parsed.get("cited_ids") or [] if isinstance(i, str))
        for candidate in candidates:
            if isinstance(candidate, dict):
                cited.update(str(i) for i in candidate.get("cited_ids") or [] if isinstance(i, str))
        cited.update(extract_ids(str(parsed.get("summary") or "")))
    else:
        cited.update(extract_ids(text))
    unsupported = sorted(cited - allowed_ids)
    provisional_used = sorted(cited & provisional_ids)
    return {
        "parsed": parsed is not None,
        "decision": decision if decision in DECISIONS else None,
        "decision_valid": decision in DECISIONS,
        "expected_decision": expected_decision,
        "decision_matches_expected": (
            None if expected_decision is None else decision == expected_decision
        ),
        "reference_decision": reference_decision,
        "decision_matches_reference": (
            None if reference_decision is None else decision == reference_decision
        ),
        "candidate_count": len(candidates),
        "candidates_without_citation": sum(
            1 for c in candidates if not (isinstance(c, dict) and c.get("cited_ids"))
        ),
        "cited_ids": sorted(cited),
        "unsupported_ids": unsupported,
        "citation_precision": (
            None if not cited else round(len(cited & allowed_ids) / len(cited), 4)
        ),
        "provisional_ids_cited": provisional_used,
        "provisional_label_present": has_provisional_label(text),
        "provisional_label_ok": (not provisional_used) or has_provisional_label(text),
        "unsafe_phrasing": unsafe_phrases(text),
    }


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for baseline in BASELINES:
        rows = [r for r in results if r["baseline"] == baseline]
        if not rows:
            continue
        scored = [r["score"] for r in rows if r.get("score")]
        summary[baseline] = {
            "scenarios": len(rows),
            "answered": len(scored),
            "skipped_or_failed": len(rows) - len(scored),
            "parse_rate": _mean([float(s["parsed"]) for s in scored]),
            "decision_accuracy": _mean(
                [float(s["decision_matches_expected"]) for s in scored
                 if s["decision_matches_expected"] is not None]
            ),
            "agreement_with_c2": _mean(
                [float(s["decision_matches_reference"]) for s in scored
                 if s["decision_matches_reference"] is not None]
            ),
            "mean_citation_precision": _mean([s["citation_precision"] for s in scored]),
            "unsupported_id_total": sum(len(s["unsupported_ids"]) for s in scored),
            "provisional_label_compliance": _mean(
                [float(s["provisional_label_ok"]) for s in scored if s["provisional_ids_cited"]]
            ),
            "unsafe_phrasing_answers": sum(1 for s in scored if s["unsafe_phrasing"]),
        }
    return summary


# --- runner --------------------------------------------------------------------

@dataclass
class RunOptions:
    baselines: tuple[str, ...] = BASELINES
    dry_run: bool = False
    explain: bool = False
    include_prompts: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
    # Called with one line per finished step (the CLI prints it).
    progress: Callable[[str], None] = lambda message: None


def run_baselines(scenarios: list[dict[str, Any]], env: BaselineEnvironment,
                  client: LLMClient | None, options: RunOptions) -> dict[str, Any]:
    """Run every scenario. A failing scenario is recorded and the run goes
    on; Ctrl+C stops the run but keeps the finished scenarios."""
    results: list[dict[str, Any]] = []
    explanations: list[dict[str, Any]] = []
    interrupted = False
    for number, scenario in enumerate(scenarios, 1):
        started = time.monotonic()
        try:
            _run_scenario(scenario, env, client, options, results, explanations)
        except KeyboardInterrupt:
            interrupted = True
            options.progress("Interrupted: saving the scenarios finished so far.")
            break
        options.progress(
            f"[{number}/{len(scenarios)}] {scenario['scenario_id']} done in "
            f"{time.monotonic() - started:.0f}s"
        )
    return {"results": results, "summary": summarise(results),
            "explanations": explanations, "interrupted": interrupted}


def _run_scenario(scenario, env, client, options, results, explanations) -> None:
    from app.llm.explanation import explain_output

    scenario_id = scenario["scenario_id"]
    expected = scenario.get("expected_decision")
    try:
        payload = C1ScreeningPayload.model_validate(scenario["payload"])
    except ValidationError as exc:
        for baseline in options.baselines:
            results.append({"scenario_id": scenario_id, "baseline": baseline,
                            "status": "invalid_payload", "error": f"{exc.error_count()} validation error(s)"})
        return

    c2_output = None
    c2_status = None
    if "B3" in options.baselines or options.explain:
        prepared = prepare_request(payload, env)
        if prepared["request"] is not None:
            try:
                c2_output = env.run_reasoning(prepared["request"])
            except Exception as exc:  # graph outage or malformed data
                c2_status = f"c2_error:{type(exc).__name__}: {str(exc)[:300]}"
                options.progress(f"  Component 2 failed for {scenario_id}: {c2_status}")
        else:
            c2_status = f"{prepared['status']}:{prepared['reason']}"
    reference = c2_output.decision.value if c2_output else None

    for baseline in options.baselines:
        row: dict[str, Any] = {"scenario_id": scenario_id, "baseline": baseline}
        if baseline == "B3" and c2_output is None:
            row.update(status="skipped", reason=f"component2_not_run ({c2_status})")
            results.append(row)
            continue
        try:
            built = build_prompt(baseline, payload, env, c2_output)
        except Exception as exc:
            row.update(status="skipped", reason=f"context_unavailable ({type(exc).__name__}: {exc})")
            results.append(row)
            continue
        row["context_ids"] = sorted(built["allowed_ids"])
        row["provisional_context_ids"] = sorted(built["provisional_ids"])
        if options.include_prompts or options.dry_run:
            row["prompt"] = built["prompt"]
        if options.dry_run or client is None:
            row["status"] = "not_called"
            results.append(row)
            continue
        try:
            response = client.complete(SYSTEM_PROMPT, built["prompt"])
        except LLMRequestError as exc:
            row.update(status="llm_error", error=str(exc))
            results.append(row)
            continue
        row.update(
            status="answered",
            served_model=response.served_model,
            fallback_used=response.fallback_used,
            stop_reason=response.stop_reason,
            usage=response.usage,
            answer=response.text,
            score=score_answer(
                response.text, built["allowed_ids"], built["provisional_ids"],
                expected, reference,
            ),
        )
        results.append(row)

    if options.explain and c2_output is not None:
        try:
            explanation = explain_output(c2_output, None if options.dry_run else client)
        except Exception as exc:
            explanations.append({"scenario_id": scenario_id, "status": "error",
                                 "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
        else:
            explanations.append({"scenario_id": scenario_id, **explanation.model_dump()})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markdown_report(report: dict[str, Any]) -> str:
    meta = report["metadata"]
    lines = [
        "# LLM baseline run",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Provider/model: {meta['llm'].get('provider')} / {meta['llm'].get('model')}",
        f"- Graph source: {meta['graph_source']}; knowledge scope: {meta['knowledge_scope']}",
        f"- Scenarios: {meta['scenario_file']} (sha256 {meta['scenario_sha256'][:12]})",
        f"- Dry run: {meta['dry_run']}",
        *(["- INTERRUPTED: partial results only."] if report.get("interrupted") else []),
        "",
        "Deterministic research scores, not clinical validation. Synthetic scenarios.",
        "",
        "| Baseline | Answered | Parse | Decision acc. | Agree C2 | Citation precision | Unsupported IDs | Provisional label | Unsafe |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for baseline, s in report["summary"].items():
        lines.append(
            f"| {baseline} | {s['answered']}/{s['scenarios']} | {s['parse_rate']} | "
            f"{s['decision_accuracy']} | {s['agreement_with_c2']} | {s['mean_citation_precision']} | "
            f"{s['unsupported_id_total']} | {s['provisional_label_compliance']} | "
            f"{s['unsafe_phrasing_answers']} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    """Write JSON + Markdown to new files. Never overwrites."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tag = "dryrun" if report["metadata"]["dry_run"] else report["metadata"]["llm"].get("provider", "llm")
    base = out_dir / f"llm_baselines_{stamp}_{tag}"
    json_path, md_path = base.with_suffix(".json"), base.with_suffix(".md")
    with json_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
    with md_path.open("x", encoding="utf-8") as handle:
        handle.write(markdown_report(report))
    return json_path, md_path


def build_report(run: dict[str, Any], env: BaselineEnvironment, scenario_path: Path,
                 llm_meta: dict[str, Any], options: RunOptions) -> dict[str, Any]:
    retrieval = env.retrieval
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
            "baselines": list(options.baselines),
            "dry_run": options.dry_run,
            "llm": llm_meta,
            "graph_source": env.graph_source,
            "knowledge_scope": env.knowledge_scope,
            "retrieval_model": getattr(retrieval, "model_id", None),
            "scenario_file": str(scenario_path),
            "scenario_sha256": _sha256(scenario_path),
            "notice": (
                "Research baselines over synthetic scenarios. Scores are deterministic "
                "heuristics and not clinical validation; no output is a medical conclusion."
            ),
            **options.extra,
        },
        **run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.llm.baselines")
    parser.add_argument("--baselines", default=",".join(BASELINES))
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--knowledge-scope", choices=("approved_and_provisional", "approved"),
                        default="approved_and_provisional",
                        help="approved_and_provisional also reads unverified research records")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--explain", action="store_true", help="also run the grounded explanation layer")
    parser.add_argument("--include-prompts", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="build prompts only; no LLM call, no key needed")
    args = parser.parse_args(argv)

    baselines = tuple(b.strip().upper() for b in args.baselines.split(",") if b.strip())
    unknown = set(baselines) - set(BASELINES)
    if unknown or not baselines:
        parser.error(f"--baselines must be a subset of {','.join(BASELINES)}")
    options = RunOptions(baselines=baselines, dry_run=args.dry_run, explain=args.explain,
                         include_prompts=args.include_prompts,
                         progress=lambda message: print(message, flush=True))
    # The live graph queries emit one deprecation notice per call; keep the
    # console readable so real errors stay visible.
    logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

    client = None
    llm_meta: dict[str, Any] = {"provider": None, "model": None}
    if not args.dry_run:
        try:
            client = create_llm_client()
        except LLMConfigurationError as exc:
            print(f"LLM not configured: {exc} (use --dry-run to build prompts only)", file=sys.stderr)
            return 2
        llm_meta = client.settings.describe()

    scenarios = load_scenarios(args.scenarios)
    started = time.monotonic()
    options.progress("Connecting to the live graph and preparing the evidence index...")
    env = live_environment(args.knowledge_scope)
    options.progress(
        f"Ready in {time.monotonic() - started:.0f}s. Running {len(scenarios)} scenario(s)."
    )
    try:
        run = run_baselines(scenarios, env, client, options)
    finally:
        env.close()
    report = build_report(run, env, args.scenarios.resolve(), llm_meta, options)
    json_path, md_path = write_report(report, args.out_dir)
    print(markdown_report(report))
    print(f"Report: {json_path}\nSummary: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
