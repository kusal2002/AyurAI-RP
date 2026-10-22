"""End-to-end Component 2 reasoning pipeline.

Approved Component 1 input
  -> symptom concept mapping (reason_about_symptoms)
  -> ontology knowledge-chain traversal (trace_knowledge_chains)
  -> ontology type validation and candidate extraction
  -> semantic evidence retrieval (embedding model, if available)
  -> provisional ranking and sufficiency assessment
  -> deterministic explanation
  -> structured Component2Output

The pipeline reuses the existing evaluator, symptom reasoner and chain
tracer. It never creates candidates from retrieval alone, never promotes
claim verification status and never outputs a medical conclusion.
"""

from typing import Any

from neo4j import Driver

from app.db.repository import get_concepts
from app.models.c1_input import Component2ReasoningRequest
from app.models.c2_output import (
    DEFAULT_LIMITATIONS,
    Abstention,
    Candidate,
    CandidateCategory,
    CandidateDisposition,
    Component2Output,
    RetrievalInfo,
    RetrievedEvidenceItem,
    SufficiencyStatus,
    SymptomMapping,
    UpstreamScreeningMetadata,
)
from app.reasoning.candidates import concept_botanical_name, concept_name, extract_candidate_paths
from app.reasoning.explanation import (
    explain_abstention,
    explain_caution,
    explain_candidate,
    explain_interpretation,
    explain_symptom_mappings,
)
from app.reasoning.knowledge_chain import trace_knowledge_chains
from app.reasoning.ranking import RankingPolicy, rank_candidate
from app.reasoning.risk_context import RiskContextPolicy, decide, evaluate_risk_context
from app.reasoning.sufficiency import (
    SufficiencyPolicy,
    assess_candidate,
    assess_request,
)
from app.reasoning.symptom_reasoner import reason_about_symptoms
from app.retrieval.embedding import EmbeddingModelUnavailableError
from app.retrieval.service import EvidenceRetrievalService


def _map_symptoms(symptom_reasoning: dict[str, Any]) -> list[SymptomMapping]:
    mappings = []
    for result in symptom_reasoning["results"]:
        symptom = result.get("symptom") or {}
        mappings.append(
            SymptomMapping(
                symptom_id=result["symptom_id"],
                found=result["found"],
                name=symptom.get("name"),
                indicates_claim_ids=[
                    claim["claim_id"]
                    for claim in result.get("indicates_claims", [])
                ],
                message=result.get("message"),
            )
        )
    return mappings


def _apply_retrieval(
    retrieval_service: EvidenceRetrievalService | None,
    driver: Driver | None,
    claim_steps: dict[str, Any],
    query_terms: list[str],
    traversed_evidence_ids: set[str],
) -> tuple[RetrievalInfo, list[RetrievedEvidenceItem]]:
    """Score claim-to-evidence relevance and run an open evidence query.

    Mutates claim steps in place by setting retrieval_similarity.
    """
    if retrieval_service is None:
        return RetrievalInfo(mode="not_run"), []

    settings = retrieval_service.settings
    info = RetrievalInfo(
        mode="unavailable",
        model_id=retrieval_service.model_id,
        top_k=settings.top_k,
        min_similarity=settings.min_similarity,
    )

    if not retrieval_service.ensure_ready(driver):
        info.error = retrieval_service.last_error
        return info, []

    info.indexed_chunks = retrieval_service.index.size
    retrieved: list[RetrievedEvidenceItem] = []

    try:
        # Neuro-symbolic check: does each claim's own supporting evidence
        # actually discuss what the claim states?
        for step in claim_steps.values():
            supporting_ids = [
                ref.evidence_id for ref in step.supporting_evidence
            ]
            if not step.statement or not supporting_ids:
                continue
            hits = retrieval_service.search(
                step.statement,
                top_k=1,
                restrict_to_evidence_ids=supporting_ids,
                include_below_threshold=True,
            )
            info.query_count += 1
            if hits:
                step.retrieval_similarity = hits[0].similarity

        # Open retrieval using stored concept names only (no free text).
        if query_terms:
            hits = retrieval_service.search(" ; ".join(query_terms))
            info.query_count += 1
            for hit in hits:
                chunk = hit.chunk
                retrieved.append(
                    RetrievedEvidenceItem(
                        chunk_id=chunk.chunk_id,
                        evidence_id=chunk.evidence_id,
                        similarity=hit.similarity,
                        below_threshold=hit.below_threshold,
                        linked_to_traversed_claim=(
                            chunk.evidence_id in traversed_evidence_ids
                        ),
                        title=chunk.title,
                        source_name=chunk.source_name,
                        evidence_type=chunk.evidence_type,
                        section=chunk.section,
                        page=chunk.page,
                        citation=chunk.citation,
                        source_url=chunk.source_url,
                        source_id=chunk.source_id,
                        source_chunk_id=chunk.source_chunk_id,
                        knowledge_status=chunk.knowledge_status,
                        evidence_role=chunk.evidence_role,
                    )
                )
    except EmbeddingModelUnavailableError as exc:
        for step in claim_steps.values():
            step.retrieval_similarity = None
        info.error = str(exc)
        return info, []

    info.mode = "neural_embedding"
    return info, retrieved


def _indicates_statuses(symptom_reasoning, mappings):
    """(mapping, knowledge_status) for every INDICATES claim found."""
    by_id = {m.symptom_id: m for m in mappings}
    for result in symptom_reasoning["results"]:
        mapping = by_id.get(result["symptom_id"])
        for claim in result.get("indicates_claims", []):
            yield mapping, claim.get("knowledge_status", "approved")


def candidate_order_key(candidate: dict[str, Any]) -> tuple:
    """Order of candidates in the output (rank 1 first).

    1. Forwarded candidates first: ranking never overrides sufficiency.
    2. Then candidates reached through a matched Roga type (for example
       Pittaja Pandu from burning and thirst) before the general remedies of
       the parent Roga, so the patient's type shapes the list.
    3. Then the experimental ranking score, which this order never changes.
    """
    return (
        candidate["disposition"] != CandidateDisposition.FORWARD_FOR_SAFETY_ASSESSMENT,
        not candidate.get("matched_subtypes"),
        -candidate["ranking"].score,
        candidate["category"].value,
        candidate["candidate_id"],
    )


def run_component2_reasoning(
    request: Component2ReasoningRequest,
    driver: Driver | None = None,
    retrieval_service: EvidenceRetrievalService | None = None,
    ranking_policy: RankingPolicy | None = None,
    sufficiency_policy: SufficiencyPolicy | None = None,
    max_depth: int = 5,
    max_chains: int = 100,
    risk_policy: RiskContextPolicy | None = None,
    graph: Any = None,
) -> Component2Output:
    """Run the pipeline. `graph` selects the knowledge scope: None reads
    approved knowledge only (the default, unchanged); a
    `ResearchGraphAccess` also reads provisional, unverified records."""
    knowledge_scope = getattr(graph, "knowledge_scope", "approved")
    ranking_policy = ranking_policy or RankingPolicy()
    sufficiency_policy = sufficiency_policy or SufficiencyPolicy()
    risk_policy = risk_policy or RiskContextPolicy()

    # 1-2. Map supplied symptoms to stored Symptom concepts.
    symptom_reasoning = reason_about_symptoms(request.symptom_ids, driver, graph=graph)
    mappings = _map_symptoms(symptom_reasoning)
    mapped_ids = [m.symptom_id for m in mappings if m.found]

    # 3. Ontology-constrained traversal from each mapped symptom.
    chain_results = []
    truncated = False
    for symptom_id in mapped_ids:
        result = trace_knowledge_chains(
            symptom_id, driver, max_depth=max_depth, max_chains=max_chains, graph=graph
        )
        truncated = truncated or result["truncated"]
        chain_results.append(result)

    concept_ids = {
        concept_id
        for result in chain_results
        for chain in result["chains"]
        for concept_id in chain["concept_ids"]
    }
    concept_lookup = graph.get_concepts if graph is not None else get_concepts
    concepts = concept_lookup(sorted(concept_ids), driver) if concept_ids else {}

    # 4. Type-validated candidate extraction.
    extracted = extract_candidate_paths(chain_results, concepts)
    candidate_paths = extracted["candidate_paths"]
    claim_steps = extracted["claim_steps"]
    interpretation = extracted["interpretation"]

    traversed_evidence_ids = {
        ref.evidence_id
        for step in claim_steps.values()
        for ref in step.supporting_evidence + step.contradicting_evidence
    }

    # 5. Semantic retrieval.
    query_terms = [m.name for m in mappings if m.found and m.name] + [
        c.name for c in interpretation if c.name
    ]
    retrieval_info, retrieved = _apply_retrieval(
        retrieval_service,
        driver,
        claim_steps,
        query_terms,
        traversed_evidence_ids,
    )
    retrieval_available = retrieval_info.mode == "neural_embedding"
    min_similarity = (
        retrieval_service.settings.min_similarity
        if retrieval_service is not None
        else 1.0
    )

    # Roga types (e.g. Pittaja Pandu) reached from the patient's symptoms.
    subtype_ids = {
        concept_id
        for concept_id, entry in concepts.items()
        if (entry.get("properties") or {}).get("subtype_of")
    }

    # 6-8. Ranking and sufficiency per candidate.
    unranked = []
    for candidate_id, paths in candidate_paths.items():
        category = CandidateCategory(paths[0].claims[-1].object_type)
        ranking = rank_candidate(paths, ranking_policy)
        sufficiency = assess_candidate(
            paths, sufficiency_policy, retrieval_available, min_similarity
        )
        steps = {c.claim_id: c for p in paths for c in p.claims}
        conflict_flags = sorted(
            flag
            for flag in sufficiency.uncertainty_flags
            if flag in {
                "supporting_and_contradicting_evidence",
                "contradicting_evidence_only",
                "disputed_claim",
                "paths_disagree",
            }
        )
        disposition = (
            CandidateDisposition.FORWARD_FOR_SAFETY_ASSESSMENT
            if sufficiency.status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW
            else CandidateDisposition.WITHHELD_PENDING_REVIEW
        )
        unranked.append(
            dict(
                candidate_id=candidate_id,
                category=category,
                name=concept_name(concepts, candidate_id),
                botanical_name=concept_botanical_name(concepts, candidate_id),
                ranking=ranking,
                disposition=disposition,
                paths=paths,
                claim_ids=sorted(steps),
                supporting_evidence_ids=sorted(
                    {
                        r.evidence_id
                        for c in steps.values()
                        for r in c.supporting_evidence
                    }
                ),
                contradicting_evidence_ids=sorted(
                    {
                        r.evidence_id
                        for c in steps.values()
                        for r in c.contradicting_evidence
                    }
                ),
                verification_statuses=sorted(
                    {c.verification_status for c in steps.values()}
                ),
                conflict_flags=conflict_flags,
                matched_subtypes=sorted(
                    {cid for p in paths for cid in p.concept_ids if cid in subtype_ids}
                ),
                sufficiency=sufficiency,
            )
        )

    unranked.sort(key=candidate_order_key)
    path_claim_ids = {
        step.claim_id for data in unranked for path in data["paths"] for step in path.claims
    }
    candidates = []
    for rank, data in enumerate(unranked, start=1):
        candidate = Candidate(rank=rank, **data)
        candidate.rationale = explain_candidate(candidate)
        candidates.append(candidate)

    # Request-level sufficiency and abstention.
    status, abstention_reasons = assess_request(
        len(mapped_ids), [c.sufficiency.status for c in candidates]
    )

    flags: set[str] = set()
    gaps: set[str] = set()
    for candidate in candidates:
        flags |= set(candidate.sufficiency.uncertainty_flags)
        gaps |= set(candidate.sufficiency.evidence_gaps)
    if any(not m.found for m in mappings):
        flags.add("unmapped_symptom_ids")
    if extracted["rejected_paths"]:
        flags.add("ontology_invalid_paths_rejected")
    if truncated:
        flags.add("traversal_truncated")
    if retrieval_info.mode != "neural_embedding":
        flags.add("semantic_retrieval_unavailable")
    elif any(
        not item.linked_to_traversed_claim for item in retrieved
    ):
        flags.add("retrieved_evidence_not_linked_to_claims")

    # Request-level decision (FR9): evidence status gated by upstream risk.
    # Ranking, candidate sufficiency and dispositions are already final.
    risk_context = evaluate_risk_context(
        request.risk_tier,
        request.calibrated_confidence,
        risk_policy,
        urgent_clinician_review=request.urgent_clinician_review,
    )
    decision, decision_reasons = decide(status, risk_context, risk_policy)
    provisional_used = any(
        step.knowledge_status == "provisional"
        for candidate in candidates for path in candidate.paths for step in path.claims
    ) or any(
        mapping.found and claim_status == "provisional"
        for mapping, claim_status in _indicates_statuses(symptom_reasoning, mappings)
    )
    if provisional_used:
        flags.add("provisional_unverified_knowledge_used")
        if "knowledge:provisional_records_used" not in decision_reasons:
            decision_reasons = decision_reasons + ["knowledge:provisional_records_used"]

    explanation = explain_symptom_mappings(mappings) + explain_interpretation(
        interpretation
    )
    if decision.value == "caution":
        explanation.append(explain_caution(decision_reasons, risk_context.escalation))
    abstain = bool(abstention_reasons)
    abstention = Abstention(abstain=abstain, reasons=abstention_reasons)
    if abstain:
        statement = explain_abstention(abstention_reasons)
        abstention.explanation = statement.text
        explanation.append(statement)

    limitations = list(DEFAULT_LIMITATIONS)
    if knowledge_scope != "approved":
        limitations.append(
            "Research scope: includes provisional, AI-assisted draft claims quoted from sources "
            "but not verified by a practitioner (verification_status 'unverified'). They are "
            "shown for research demonstration only and are never sufficient for a recommendation."
        )
    return Component2Output(
        request_id=request.request_id,
        knowledge_scope=knowledge_scope,
        limitations=limitations,
        upstream=UpstreamScreeningMetadata(
            risk_tier=request.risk_tier,
            calibrated_confidence=request.calibrated_confidence,
        ),
        input_symptom_ids=list(request.symptom_ids),
        symptom_mappings=mappings,
        interpretation=interpretation,
        candidates=candidates,
        interpretation_claims=[
            step
            for claim_id, step in sorted(claim_steps.items())
            if claim_id not in path_claim_ids
        ],
        rejected_paths=extracted["rejected_paths"],
        retrieval=retrieval_info,
        retrieved_evidence=retrieved,
        sufficiency_status=status,
        decision=decision,
        decision_reasons=decision_reasons,
        risk_context=risk_context,
        uncertainty_flags=sorted(flags),
        evidence_gaps=sorted(gaps),
        review_required=(
            abstain
            or decision.value != "recommend_for_review"
            or bool(flags)
            or any(c.sufficiency.review_required for c in candidates)
        ),
        abstention=abstention,
        explanation=explanation,
        traversal_truncated=truncated,
    )
