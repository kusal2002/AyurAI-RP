# AyurAI Component 2 — Implementation Notes (Phase 8)

Status legend used in this document:

- **Implemented** – code exists and is covered by unit and/or live tests.
- **Prototype** – implemented, but the policy/values are provisional and
  need supervisor and practitioner review before research use.
- **Not implemented** – proposed or required, but no code exists yet.

Passing software tests shows that the code behaves as specified on
synthetic data. It is **not** clinical validation of any Ayurvedic
relationship, ranking or recommendation.

## 1. Purpose

Component 2 receives an approved Component 1 screening summary, maps the
supplied symptom IDs onto stored Ayurvedic concepts, traverses
evidence-linked ontology claims, checks the linked evidence with a neural
embedding model, and returns a structured, traceable result (or an
explicit abstention) for Component 3 safety assessment and practitioner
review. It does not diagnose, prescribe or assess patient safety.

## 2. Architecture and module responsibilities

| Stage | Module | Status |
|---|---|---|
| Input contract | `app/models/c1_input.py` (`Component2ReasoningRequest`) | Implemented |
| Symptom → concept mapping | `app/reasoning/symptom_reasoner.py` (existing, reused) | Implemented |
| Per-claim evidence evaluation | `app/reasoning/evaluator.py` (existing, reused) | Implemented |
| Ontology chain traversal | `app/reasoning/knowledge_chain.py` (existing, reused) | Implemented |
| Batch concept lookup / evidence listing | `app/db/repository.py` (`get_concepts`, `list_evidence`) | Implemented |
| Candidate extraction + ontology type validation | `app/reasoning/candidates.py` | Implemented |
| Embedding encoder | `app/retrieval/embedding.py` | Implemented, real inference verified |
| Vector index + chunking | `app/retrieval/evidence_index.py` | Implemented |
| Retrieval service | `app/retrieval/service.py` | Implemented |
| Evidence ingestion | `app/retrieval/ingestion.py` | Implemented (no approved corpus yet) |
| Ranking | `app/reasoning/ranking.py` | Prototype |
| Sufficiency / abstention | `app/reasoning/sufficiency.py` | Prototype |
| Explanation | `app/reasoning/explanation.py` | Implemented (deterministic) |
| Pipeline orchestration | `app/reasoning/pipeline.py` | Implemented |
| Output contract | `app/models/c2_output.py` | Implemented |
| Component 3 handoff | `app/models/c3_handoff.py` | Implemented (contract only) |
| Practitioner feedback | `app/models/feedback.py`, `app/feedback/service.py` | Implemented (API only, no UI) |
| Audit metadata | `app/governance/audit.py` | Implemented (log emission only) |
| API | `app/api/c2.py` | Implemented |

Pipeline order (`run_component2_reasoning`):

1. Validate request (Pydantic).
2. `reason_about_symptoms` → which symptom IDs exist and their
   `INDICATES` claims.
3. `trace_knowledge_chains` from every found symptom (max depth 5,
   max 100 chains per symptom; truncation is flagged).
4. `get_concepts` for every concept on every chain (one batch query).
5. `extract_candidate_paths`: each claim in a chain is re-validated against
   `RELATIONSHIP_RULES` using the concept's real Neo4j label. A chain stops
   at the first invalid/missing/ambiguous concept and is reported in
   `rejected_paths`. Prefixes ending at Herb/Formulation/Diet/Lifestyle
   become candidate paths; Roga/Dosha/Dhatu/TherapeuticPrinciple concepts
   become the `interpretation`.
6. Semantic retrieval (see §9).
7. Ranking (§10) and sufficiency (§11) per candidate.
8. Request-level status, abstention, explanation, output.
9. The API layer emits an audit record (§15).

## 3. Input schema and Component 1 integration

`Component2ReasoningRequest` reuses the existing `RiskTier` enum
(`low|moderate|high`) and the existing field name `calibrated_confidence`
from `C1Input`; `screening_confidence` is accepted as an alias.

| Field | Rule |
|---|---|
| `request_id` | optional; generated as `c2req-<uuid4>`; 1–128 chars `[A-Za-z0-9._:-]`; must not contain patient identifiers |
| `risk_tier` | `low`, `moderate`, `high` only |
| `calibrated_confidence` | number in [0, 1]; booleans and strings rejected |
| `symptom_ids` | 1–50 non-empty IDs, trimmed, de-duplicated (order kept) |
| any other field | rejected (`extra="forbid"`) so free text cannot leak in |

The risk tier and screening confidence are passed through to
`output.upstream` as metadata only. They do not influence traversal,
ranking or sufficiency (a unit test asserts identical candidate scores for
confidence 0.01 and 0.99). No symptoms are inferred.

The existing `/api/v1/c1/screening-result` endpoint and `C1Input` are
unchanged. **Assumption:** Component 1 will supply canonical symptom IDs
that match stored `Symptom.symptom_id` values; mapping from free-text
symptom summaries is not implemented.

## 4. Embedding model choice and configuration

- Default: `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0,
  ~90 MB, 384-dimensional, CPU-friendly). Suitable for the ~4 GB VPS.
- Real inference was verified in this environment (Windows, Python 3.13.3,
  torch 2.14.1+cpu, sentence-transformers 6.1.0): a related sentence pair
  scored 0.50 and an unrelated pair ≈0.00; in the live pipeline test,
  claim-to-evidence similarities were 0.77–0.84 for synthetic paraphrases.
- No LLM is used.

Environment variables (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `C2_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HF model ID or local directory |
| `C2_EMBEDDING_DEVICE` | `cpu` | torch device |
| `C2_EMBEDDING_BATCH_SIZE` | `32` | encode batch size |
| `C2_EMBEDDING_CACHE_DIR` | HF default cache | model cache folder |
| `C2_RETRIEVAL_TOP_K` | `5` | open-retrieval hits |
| `C2_RETRIEVAL_MIN_SIMILARITY` | `0.30` | provisional relevance threshold |
| `C2_CHUNK_MAX_CHARS` | `800` | chunk size |
| `C2_CHUNK_OVERLAP_CHARS` | `100` | chunk overlap |

## 5. Model loading and deployment

- The model is loaded lazily on the first index refresh/search, never at
  import (a test asserts that importing `app.main` does not load it).
- The first load downloads the model to the Hugging Face cache
  (`~/.cache/huggingface` by default; first download took ~2 minutes
  here). After that, set `HF_HUB_OFFLINE=1` to stop Hub checks.
- Model weights are never committed. To pin a reviewed copy, download it
  once and set `C2_EMBEDDING_MODEL` to the local directory.
- If loading fails, `EmbeddingModelUnavailableError` is raised internally,
  the pipeline reports `retrieval.mode = "unavailable"` with the error,
  adds `semantic_retrieval_unavailable`, and (with the default policy) no
  candidate can be `sufficient_for_review`. There is **no** keyword or fake
  embedding fallback.
- Installation (CPU only, avoids the multi-GB CUDA build):

```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1
pip install -r requirements.txt
```

## 6. Evidence ingestion and metadata

`python -m app.retrieval.ingestion <file.json|file.jsonl> [--dry-run]`
validates every record with `EvidenceRecord` and the existing
`validate_evidence_provenance`, reports invalid and duplicate IDs, and
saves nothing if any record is invalid. It does not scrape or generate
text.

**Blocker:** `corpus/raw`, `corpus/processed` and `corpus/metadata` are
empty. No approved classical or contemporary corpus exists in the
repository, so real-world semantic retrieval is not yet meaningful. After
ingesting, call `POST /api/v1/c2/evidence-index/refresh`.

Index chunks keep `evidence_id`, `chunk_id` (`<evidence_id>#chunk-<n>`),
title, source name, evidence type, section, page, citation, URL and
practitioner-verified flag.

## 7. Neo4j graph structure

Unchanged domain ontology (`docs/ontology_v1.md`, `RELATIONSHIP_RULES`).
Claims: `Concept-[:SUBJECT_OF]->Claim-[:OBJECT_OF]->Concept`,
`Evidence-[:SUPPORTS|CONTRADICTS]->Claim`.

New non-domain review records: `(:PractitionerFeedback)-[:REVIEWS]->(:Claim)`.
They carry no clinical meaning and never modify the claim.

## 8. Symbolic reasoning flow

Implemented as described in §2. Direction is preserved (only outgoing
claims are followed), cycles are prevented, depth/chain limits apply, and
every claim's verification status, stored confidence and evidence are kept.
Claims inserted outside `save_ontology_claim` are re-validated; violations
appear in `rejected_paths` and the `ontology_invalid_paths_rejected` flag.

Known inefficiency: the existing tracer calls `get_connected_knowledge`
and `evaluate_claim` per claim (N+1 queries). Acceptable for the current
graph size; batch traversal is future work.

## 9. Semantic retrieval flow

The index is an in-process NumPy cosine-similarity matrix (no FAISS or
ChromaDB service; unnecessary at the current corpus size). It is refreshed
incrementally by fingerprint: only changed evidence is re-embedded; deleted
evidence is removed; records without text are reported in
`skipped_evidence_ids`.

Two retrieval uses in the pipeline:

1. **Claim–evidence check (neuro-symbolic link):** for each traversed claim
   with supporting evidence, the claim statement is searched against only
   that claim's supporting evidence chunks. The best similarity is stored
   as `ClaimStep.retrieval_similarity`. This tests whether the linked
   evidence text actually discusses what the symbolic claim states.
2. **Open retrieval:** the stored names of the mapped symptoms and
   interpreted concepts form a query over the whole index. Hits are
   returned in `retrieved_evidence` with `linked_to_traversed_claim`.
   Unlinked hits raise `retrieved_evidence_not_linked_to_claims` for review.
   Retrieval **never** creates a candidate.

Similarity is retrieval relevance only.

## 10. Candidate extraction and experimental ranking (Prototype)

No approved weighting formula was found in the repository, so
`RankingPolicy` (`prototype-ranking-v0.1-provisional`) is used. All weights
are provisional and isolated for revision.

Per path (weakest-link minimums):

| Component | Formula | Default weight |
|---|---|---|
| status | min status weight (practitioner_verified 1.0, literature_supported 0.7, unverified 0.2, disputed 0.0) | 0.4 |
| support | min over claims of min(independent supporting sources, 3)/3 | 0.3 |
| contradiction | −max over claims of min(contradicting sources, 3)/3 | 0.3 |
| provenance | −share of supporting refs with incomplete provenance | 0.1 |
| retrieval | min claim–evidence similarity, clipped to [0,1] (0 if unavailable) | 0.2 |

Independent sources: references with the same source name and the same
citation/URL/title count once. The candidate uses its best path; ties are
broken deterministically. Ordering puts forwarded candidates first, then
score, category and ID — ranking never overrides sufficiency. The score is
labelled `experimental_ranking_score_not_clinical_confidence`.

## 11. Evidence sufficiency and abstention (Prototype)

`SufficiencyPolicy` (`prototype-sufficiency-v0.1-provisional`):

- each claim needs ≥1 independent supporting source;
- accepted statuses: `literature_supported`, `practitioner_verified`;
- complete provenance required (title, source name, evidence type, and one
  of citation/URL/page/section);
- claim–evidence retrieval similarity ≥ `C2_RETRIEVAL_MIN_SIMILARITY` and
  retrieval must be available (`require_semantic_retrieval_support=True`).

Candidate status: `conflicting_evidence` if any path has contradicting
evidence or a disputed claim (never outvoted); otherwise
`sufficient_for_review` if one path passes; otherwise `unverified_claims` if
a path fails only on verification; otherwise `insufficient_evidence`.

Request status / abstention reasons:

| Situation | Status | `abstention.reasons` |
|---|---|---|
| no supplied symptom found | `out_of_scope` | `no_supplied_symptom_mapped_to_stored_concept` |
| no valid candidate path | `insufficient_evidence` | `no_valid_candidate_path_found` |
| candidates, none sufficient | most severe of conflicting > unverified > insufficient | `no_candidate_sufficient_for_review`, `dominant_candidate_status:<status>` |
| ≥1 sufficient | `sufficient_for_review` | none (abstain = false) |

Also returned: `uncertainty_flags`, `evidence_gaps` (e.g.
`no_supporting_evidence:<claim_id>`), `review_required`.

## 12. Component 2 output schema

`Component2Output` (`c2-output/0.1.0`): `request_id`, `generated_at`,
`upstream` (risk tier, calibrated confidence), `input_symptom_ids`,
`symptom_mappings`, `interpretation`, `candidates` (rank, category, name,
ranking breakdown, disposition, paths with full claim steps and evidence
references, claim/evidence IDs, verification statuses, conflict flags,
sufficiency, rationale), `rejected_paths`, `retrieval` (mode, model ID,
threshold, errors), `retrieved_evidence`, `sufficiency_status`,
`uncertainty_flags`, `evidence_gaps`, `review_required`, `abstention`,
`explanation`, `traversal_truncated`, `limitations`, `score_semantics`,
`medical_conclusion: null`.

The four numeric quantities (screening confidence, retrieval similarity,
ranking score, stored claim confidence) are documented in
`score_semantics`. There is no overall medical confidence.

## 13. Component 3 interface

No Component 3 API exists in this repository, so only the contract is
implemented: `Component3Handoff` (`c2-to-c3/0.1.0`) built by
`build_component3_handoff(output)` and served by
`POST /api/v1/c2/reasoning/component3-handoff`. Per candidate it carries ID,
category, display name, experimental rank/score, disposition, claim paths,
claim IDs, evidence IDs, supporting/contradicting evidence with citations,
verification statuses, sufficiency status, uncertainty/conflict flags,
review flag and rationale. `safety_assessment_performed_by_component2` is
always `false`. Component 3 safety logic is not duplicated here.

## 14. Practitioner feedback flow

`POST /api/v1/c2/feedback` accepts `PractitionerFeedback` (feedback/request
IDs, claim/candidate/evidence IDs, `review_outcome`, `issue_category`,
rationale, ≤10 refinement terms of ≤64 chars, suggested concept IDs,
`reviewer_role`, pseudonymous `reviewer_ref`). It:

1. stores an append-only `PractitionerFeedback` node (duplicate ID → 409);
2. links it with `REVIEWS` to existing claims only (unknown IDs reported);
3. builds an explicit `RefinementQuery` from the terms plus stored names of
   suggested concepts, and runs semantic retrieval with it;
4. returns `claims_modified: false`.

No claim or verification status is changed. **Not implemented:** a
practitioner UI, an approved verification-status workflow, and automatic
re-running of reasoning with refined evidence.

## 15. Privacy and audit metadata

`build_audit_record` produces one JSON line on logger `ayurai.c2.audit`
with: request ID, timestamp, schema/policy IDs, retrieval mode, model ID,
retrieval error, symptom counts, claim IDs traversed, evidence IDs
referenced/retrieved, candidate IDs returned/forwarded, sufficiency status,
abstention and reasons, review flag.

Excluded: symptom IDs, risk tier, screening confidence, free text, feedback
rationale and reviewer reference. API errors return generic bodies without
credentials, hosts or stack traces.

Limitations: claim IDs can indirectly reveal the supplied symptoms; no
log storage, retention, encryption or access control is implemented; no
regulatory compliance is claimed. These belong to Component 4, whose
contract is not present in this repository.

### Additional prototype limitations

- **Authentication and authorization:** The Component 2 reasoning, feedback, and evidence-index refresh endpoints do not currently implement authentication or role-based authorization. The submitted `reviewer_role` and pseudonymous `reviewer_ref` fields are not independently verified credentials.
- **Feedback storage:** The feedback rationale is stored in the `PractitionerFeedback` record in Neo4j. Its exclusion from audit logs does not mean it is excluded from database storage. Until appropriate privacy controls are implemented, use synthetic or properly de-identified research data and do not submit patient-identifying information.
- **Feedback identifier integrity:** Duplicate feedback IDs are checked at the application level, but a database uniqueness constraint is not implemented. Concurrent requests could therefore create duplicate records.
- **Deployment boundary:** These endpoints are intended for a controlled research prototype. Public deployment and use with real patient data require appropriate authentication, authorization, privacy protections, retention controls, and database integrity guarantees.

## 16. Running the unit tests

```bash
cd component2
python -m pytest -q
```

Unit tests run offline: an in-memory `FakeGraph` replaces Neo4j and a
test-only `KeywordEncoder` replaces the model (`c2_test_support.py`).
One test (`test_invalid_model_path_raises_clear_error`) is skipped if
sentence-transformers is not installed.

## 17. Running the Neo4j integration tests

```bash
python test_neo4j_repository.py
python test_neo4j_pipeline.py
```

Both use synthetic data only and delete it in a `finally` block;
`test_neo4j_pipeline.py` uses IDs prefixed `TEST-C2PIPE-`, verifies that no
such nodes remain, and loads the real embedding model.

## 18. Configuration

Neo4j: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` in `component2/.env`
(git-ignored). Model/retrieval: §4.

## 19. Known limitations and unimplemented items

- No approved evidence corpus; no real Pandu knowledge graph content
  verified here. All demonstrations use synthetic data.
- Ranking and sufficiency values are provisional engineering choices.
- `min_similarity = 0.30` was not calibrated on real Ayurvedic text; MiniLM
  is a general English model and may handle Sanskrit terms poorly.
- Free-text symptom summaries are not mapped to symptom IDs.
- No Component 3 or Component 4 service integration (contracts only).
- No practitioner UI or verification-status workflow.
- In-memory index is rebuilt per process; not shared across workers.
- N+1 queries in chain traversal.
- No uniqueness constraint for `PractitionerFeedback.feedback_id` (append-only
  is enforced by the save query, not by a schema constraint).

## 20. Requirements for future practitioner validation

- Curate and approve the classical/contemporary corpus with complete
  provenance; ingest with the ingestion tool.
- Have qualified practitioners review each domain claim and define the
  workflow that may change `verification_status`.
- Review ranking weights, status weights, sufficiency rules and the
  retrieval threshold; record the approved values and rationale.
- Evaluate retrieval quality on an annotated query set (e.g. recall@k for
  known claim–evidence pairs), including Sanskrit/transliterated terms.
- Evaluate abstention behaviour on expert-labelled cases before any claim
  of usefulness is made.
