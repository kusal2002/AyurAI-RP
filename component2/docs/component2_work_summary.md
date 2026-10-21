# Component 2: work summary

This covers the AyurAI Component 2 data and knowledge layer: dataset
discovery, ingestion, the Neo4j knowledge graph, evidence-grounded
reasoning, C1 integration and the frontend. It records what was built and
verified, and what is still open, as of 2026-10-20.

Detailed references:

- `knowledge_graph_schema.md`: graph model, including §10, the provisional pathway
- `knowledge_ingestion.md`: corpus pipeline and data operations
- `dataset_discovery.md`: sources searched, included and excluded
- `provisional_knowledge_report.md`: the live AuraDB write and the review backlog
- `design_risk_tier_integration.md`: the Option B decision layer
- `c1_integration_testing.md`: C1 → C2 testing
- `component2_implementation.md`: overall design

## 1. What Component 2 does

Component 2 takes a Component 1 anaemia screening result: a risk tier, a
calibrated confidence and symptoms. It maps the symptoms to
knowledge-graph concepts, never guessing. It then traverses evidence-linked
claims, from Symptom to Roga (Pandu), Dosha, Dhatu and therapeutic
principle, and on to herbs, formulations, diet and lifestyle.

Every step carries its quoted source evidence. Component 2 ranks
candidates, checks evidence sufficiency, and returns a structured,
explainable output (`c2-output/0.3.0`) for practitioner review, with a
decision of `recommend_for_review`, `caution` or `abstain`. It never
produces a diagnosis or prescription (`medical_conclusion` is always
null).

## 2. Work completed

### 2.1 Dataset discovery and corpus

- **Source registry.** `corpus/source_registry.csv` lists 57 assessed
  sources: classical texts, translations, modern reviews, terminology and
  NHANES. It records licence, redistribution, category and inclusion
  decision. The CLI provides `sources`, `sources-validate` and
  `manifest-update`.
- **Acquisition.** With approval, 12 open sources, 3 Europe PMC
  open-access reviews and the NHANES files were downloaded with checksums
  (`acquire --apply`).
  - Paywalled and blocked sources were not bypassed (NIH ODS returned 403).
  - A Z-Library-origin file is quarantined pending a decision.
- **Extraction.** Readers for TEI (SARIT) and JATS (PMC) XML keep verse
  and element IDs and `citation_refs`. Chunking keeps nested passages
  together (`_same_or_nested`). Every chunk records its source checksum.
- **Retrieval.** There are local multilingual embedding stores; the
  experimental open store holds 42,215 chunks.
  - Round-2 evaluation reproduces the round-1 baseline (120/120).
  - 32 new pool rows await human relevance judgement.
  - Approved judgements and baseline reports were not changed.

### 2.2 Knowledge graph (Neo4j AuraDB)

- **Connection.** Hardened driver use, read-only health checks, and a
  readiness endpoint that separates connectivity, schema, content,
  ingestion, retrieval and model.
- **Validation.** Read-only graph validation (`python -m
  app.db.graph_validation`) checks labels, relationships, identity, links,
  provenance and pathway isolation.
- **Approved pathway (Stage E).** `:Claim` / `:Evidence` with `SUPPORTS` /
  `CONTRADICTS` and a Source → SourceChunk provenance chain. It supports
  promotion, non-destructive retraction and reviewer-modelled treatment
  claims.
- **Provisional research pathway (new).** Under the chosen review policy
  (Option 3), AI-assisted draft claims are stored with
  `verification_status: unverified`, using separate labels and
  relationships, deterministic IDs and exact quotes. Details are in schema
  §10.
- **Real data in AuraDB.** The `pandu-provisional-v1` dataset was drafted
  from:
  - Caraka Ci.16, Aṣṭāṅgahṛdaya Ni.13 and Suśruta Utt.44 (SARIT, Sanskrit)
  - the Kaviratna English translation
  - three open-access modern reviews
- **Write steps.** The write followed these steps:
  1. dry run (read-only)
  2. explicit authorization from the project owner
  3. MERGE-only write: **235 nodes and 330 relationships created, 0
     deleted**
  4. post-write verification: 50/50 claims, 88/88 evidence
  5. an independent quote read-back (88/88 quotes found verbatim in the
     sources)
  6. graph validation: valid, 0 errors, 0 warnings

### 2.3 Reasoning service

- **Pipeline.** Symptom reasoning → knowledge-chain traversal (bounded) →
  candidates → ranking → sufficiency → explanation → decision.
- **Knowledge scope.**
  - `knowledge_scope=approved` is the default and reads approved claims
    only.
  - `knowledge_scope=approved_and_provisional` is research mode. Every
    provisional claim and evidence item is labelled, can never make a
    candidate sufficient, and adds the reason
    `knowledge:provisional_records_used`.
- **Option B decision layer.** C1 risk context (high tier, missing
  confidence, confidence below 0.5) gates the decision to `caution`. It
  never changes ranking, sufficiency or dispositions. Audit logs record
  the decision, not the tier or confidence.
- **API.**
  - `POST /api/v1/c2/reasoning`
  - `POST /api/v1/c1/reasoning` (C1 payload with name mapping)
  - `GET /api/v1/c2/research/knowledge` (read-only)
  - `POST /api/v1/c2/feedback`
  - `/health`, `/health/neo4j`, `/health/readiness`
  - A graph outage returns 503, never invented output.
- **Live data only.** The synthetic sandbox server was removed on
  2026-10-20; the service always reads AuraDB. The synthetic graph remains
  only as an offline test fixture.

### 2.4 Component 1 integration and test data

- **C1 payload mapping.** The C1 screening payload contract is mapped
  safely: unknown or ambiguous symptom names are reported, not guessed.
  Nullable upstream confidence is preserved.
- **Synthetic scenarios.** Eight synthetic C1 scenarios, each with an
  expected decision.
- **Reference cases.** 60 real-world-derived reference cases from NHANES
  (haemoglobin with WHO 2024 severity thresholds). These are population
  data, not patients. Their confidence is null, so they correctly produce
  `caution`.
- **C1 output `c1.screening.v1`.** `POST /api/v1/c1/reasoning` accepts both
  formats. In v1, symptoms are names reported present,
  `confidence_percent` (0–100) is the calibrated confidence, and the
  uncalibrated `experimental_reliability_score` is never used. An
  `urgent_clinician_review` flag adds the rule
  `upstream_urgent_clinician_review`, which gates the decision to
  `caution`. On the 10 synthetic v1 fixtures from Component 1:
  - 8 complete
  - 2 have no symptoms, so they are correctly not analysed
  - "heavy active bleeding" and "headache" are reported as unknown
  - every case reaches Component 3 once it accepts a null confidence
- **C2 → C3 handoff (`c2-to-c3/0.1.0`).** Follows the format agreed with
  the Component 3 owner:
  - `upstream`
  - `ayurvedic_interpretation`
  - medicinal candidates only, each with `display_name`, `botanical_name`
    (as stated by the cited translation), `dose: null` (Component 2 never
    prescribes), rank, score, a `{claim_id, text}` rationale and
    evidence IDs

  `POST /api/v1/c1/component3-handoff` returns it directly from a C1
  payload.

### 2.5 Frontend (`ayurai-client`)

- **Pages.**
  - Import C1 output page (single payload, batch or scenario file)
  - decision badges and caution notices
  - source badges (demo or live)
  - system status on the Administration page
- **Knowledge-scope toggle.** On the New screening and Import pages;
  approved by default and never stored.
- **Provisional labels.**
  - research-scope banner on the analysis output
  - "Unverified — practitioner review pending" badge on every provisional
    claim and evidence item
  - evidence-role badges: primary text, translation, modern reference
    (qualifies)
  - uncertainty notes and qualifying modern evidence shown separately
- **Research knowledge (unverified) page.** Lists all provisional claims
  with exact quotes, citations and licences, plus the separate modern
  reference statements.
- **Readiness.** Shows the "provisional only" state, meaning no approved
  claims and N unverified claims usable in research scope.

### 2.6 LLM adapter, research baselines and grounded explanation (`app/llm/`)

Opt-in research tooling. The reasoning pipeline and the API do not use it,
and nothing in it changes a claim, a decision or a stored record.

- **Adapter** (`client.py`, `config.py`). One call,
  `complete(system, prompt)`, for two providers:
  - Claude (primary) through the official `anthropic` SDK. The default
    model is `claude-opus-5-5`. Server-side refusal fallback is on by
    default (`C2_LLM_REFUSAL_FALLBACK=off` disables it), and every
    response records the requested and the serving model.
  - OpenAI (optional comparison) through plain HTTP Chat Completions, so
    no extra dependency is needed. The model must be named explicitly.
  - Configuration comes only from `.env` (`C2_LLM_PROVIDER`,
    `C2_LLM_MODEL`, `C2_LLM_API_KEY` or `ANTHROPIC_API_KEY` /
    `OPENAI_API_KEY`, optional `C2_LLM_BASE_URL` for a third-party gateway;
    see `.env.example`). The key is kept out of `repr`, reports and error
    messages.
- **Baselines** (`baselines.py`). All three use the same prompt contract
  and JSON answer format (decision, candidates with cited IDs, summary):
  - B1, LLM only: the screening summary and nothing else.
  - B2, vector RAG: adds passages from the existing embedding retrieval
    service for the reported symptom names.
  - B3, KG + RAG: adds the Component 2 output (symptom mappings,
    interpretations, candidates, each claim once with status and evidence
    IDs, the deterministic decision) and the passages of the cited
    evidence. Provisional items carry the label
    "Unverified — practitioner review pending".

  Scoring is deterministic, with no LLM judge:
  - JSON validity
  - decision accuracy against each scenario's `expected_decision`
  - agreement with the Component 2 decision
  - citation precision against the IDs actually shown to the model
  - unsupported (invented) IDs
  - provisional-label compliance
  - unsafe-phrasing heuristics (diagnosis, prescription, dosage, efficacy
    promise)

  Run it from `component2/` over `samples/c1_screening_scenarios.json`:

  ```
  python -m app.llm.baselines [--baselines B1,B2,B3]
      [--knowledge-scope approved_and_provisional|approved] [--explain] [--dry-run]
  ```

  - It always reads the live AuraDB graph. The default scope,
    `approved_and_provisional`, includes the unverified research records;
    `approved` reads approved knowledge only.
  - The scenarios' `expected_decision` values were written for the retired
    synthetic graph, so on live data "Agree C2" is the meaningful decision
    measure.
  - Progress is printed per scenario. A failing scenario is recorded and
    the run continues; Ctrl+C keeps the finished scenarios.
  - `--dry-run` builds every prompt without calling a provider and needs
    no key.
  - Reports go to new timestamped files, `llm_baselines_<UTC>_<provider>`
    `.json` and `.md`, under `corpus/extracted/eval/llm_baselines/`
    (git-ignored). Files are opened in exclusive-create mode, so no
    report, including the baseline evaluation reports, is overwritten.
  - B3 is reported as skipped when Component 2 does not reason over a
    scenario (blocked tier, no resolvable symptom).
- **Grounded explanation** (`explanation.py`, `--explain`). The LLM may
  only rephrase the existing deterministic explanation statements. Each
  rewrite is rejected, and the deterministic text kept, if it:
  - drops or adds an ID
  - introduces a number that is not in the source
  - adds unsafe phrasing
  - is missing from the answer

  `claim_ids` and `evidence_ids` are always copied from the source
  statement. Statements resting on provisional records always start with
  the exact label "Unverified — practitioner review pending", applied in
  code, not by the model. Without a key, or on a provider error, the
  deterministic statements are returned unchanged.
- **Status.** Tested with mocked HTTP only. First real runs went through
  a third-party Claude gateway on 2026-10-20 (reports in
  `corpus/extracted/eval/llm_baselines/`). B3 on the live graph cited no
  unsupported IDs, kept the provisional label every time and agreed with
  the Component 2 decision in 5 of 6 scenarios. The gateway's token
  counts are not reliable.

## 3. Tests

The backend suite has **675 tests, all passing** (49 of them for the LLM
layer, which use mocked HTTP transports and a socket guard, so no
network or key is needed). They use mocks and
synthetic fixtures, so they need no live database. Areas covered:

- provenance and stable IDs
- duplicate and unsupported-claim rejection
- translation-only rejection
- source-metadata rejection
- MERGE-only writes isolated from the approved labels
- the CLI refusing to write without confirmation
- verification catching tampering and leaks
- approved-scope isolation
- research-scope labelling with never-sufficient candidates
- the API scope parameter (and 422 on bad values)
- a 503 on outage
- risk-context decisions and ranking invariants
- C1 mapping and the scenario paths (over an in-memory test graph)
- graph health and validation
- the LLM adapter (request shape, refusal and fallback handling, errors
  that never echo the key), baseline prompts and scoring, reports that
  never overwrite, and explanation rewrites that are rejected when they
  drop IDs, invent IDs or numbers, or drop the provisional label

The frontend passes type-check (`tsc`) and lint (`eslint`), and was
checked in the browser against the live service.

## 4. Governance boundaries kept

- No claim was marked approved, literature-supported or
  practitioner-verified by AI.
- Approved records, retrieval judgements and baseline evaluation reports
  were not modified.
- No destructive database operation was run. The single live write was
  explicitly authorized and is fully reported.
- Credentials stay in `.env` only and are never printed or placed in code,
  configuration or documentation.
- No patient data is used; NHANES data is aggregate-derived reference
  material.
- Copyright and licences are respected: only open-licence or
  public-domain texts are quoted, and licence notes are stored on every
  evidence item.

## 5. Open items

Human work, which cannot be automated:

1. **Practitioner review** of the 50 provisional claims (backlog in
   `provisional_knowledge_report.md` §6). Accepted claims become approved
   knowledge only through Stage E modelled-claim promotion.
2. Human relevance judgement of the 32 round-2 retrieval pool rows.
3. Lexicon review, including Sinhala terminology (no Sinhala source has
   been found yet).
4. Decisions R-D4 to R-D6 in `design_risk_tier_integration.md`; Option C
   remains design only.
5. The decision on the quarantined Z-Library-origin file.

Engineering:

6. **LLM baselines and explanation: first real run.** The adapter, the
   B1–B3 baselines and the grounded explanation layer are implemented
   (§2.6). What remains:
   - first live runs are done (2026-10-20): B1/B2 on `claude-opus-5`,
     B3 on `claude-haiku-4-5`
   - re-run all three on one model for a like-for-like table
   - review the reports

   The grounded explanation is not exposed through the API or the
   frontend yet.
7. Extending provisional coverage, for example Kāmalā, Halīmaka and
   lifestyle sources, once review of version 1 shows the drafting is
   reliable.
