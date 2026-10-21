# Component 2 Knowledge Graph Schema

This is the consolidated reference for what may exist in the AuraDB graph.
It covers node types, relationships, required properties, identity,
provenance, constraints and validation. Domain meaning is defined in
[`ontology_v1.md`](ontology_v1.md). The provenance extension and the
promotion workflow are in [`stage_e_neo4j_design.md`](stage_e_neo4j_design.md).
This document adds no new types. It describes the schema the code writes
and the validator enforces (`app/db/graph_validation.py`).

## 1. Layers and trust boundary

```
(:Source)<-[:PART_OF]-(:SourceChunk)<-[:FROM_CHUNK]-(:Evidence|:DescriptiveEvidence)
                                                          |
                                                    [:SUPPORTS|:CONTRADICTS]
                                                          v
(concept)-[:SUBJECT_OF]->(:Claim)-[:OBJECT_OF]->(concept)
                            ^
              (:PractitionerFeedback)-[:REVIEWS]
```

- **Only approved knowledge enters the graph.** Unreviewed source text,
  chunks, embeddings and candidate claims stay local
  (`corpus/extracted/`). A candidate becomes a `:Claim` only through
  `promote --apply`, after a named human approval that is recorded in the
  review log.
- **Reasoning reads `:Claim` and `:Evidence` only.**
  - `:DescriptiveEvidence` and `CONTAINS_INGREDIENT` claims are never
    traversed and never affect ranking.
  - `:RetractedClaim` and `:RetractedEvidence` are invisible to every query.
- **A claim records that a cited source states a relation.**
  - A traditional text is not a modern clinical finding: `evidence_type`
    keeps them apart.
  - A traditional use is not proof of efficacy.
  - An ingredient mention is not a therapeutic effect.

## 2. Node types

| Label | Identity property | Purpose | Written by |
|---|---|---|---|
| `Symptom` | `symptom_id` | Observable sign (C1 supplies IDs) | promotion, `save_symptom` |
| `Roga` | `roga_id` | Disease concept, e.g. `R-PANDU` | promotion |
| `Dosha` | `dosha_id` | Vata, Pitta, Kapha | promotion |
| `Dhatu` | `dhatu_id` | Tissue, e.g. Rakta | promotion |
| `TherapeuticPrinciple` | `principle_id` | Treatment principle | reviewer-modelled claims (`model-claim`, then promotion; see §9) |
| `Herb` | `herb_id` | Medicinal plant | promotion |
| `Formulation` | `formulation_id` | Compound preparation | promotion |
| `Diet`, `Lifestyle` | `diet_id`, `lifestyle_id` | Non-drug recommendations | reviewer-modelled claims (see §9) |
| `Claim` | `claim_id` | One reviewed subject-predicate-object statement | promotion, `save_ontology_claim` (concepts must already exist) |
| `Evidence` | `evidence_id` | Approved supporting sentence plus provenance | promotion, `app.retrieval.ingestion` |
| `DescriptiveEvidence` | `evidence_id` (`DEV-…`) | Evidence for descriptive claims only | promotion |
| `Source` | `source_id` | One edition or file identity | promotion |
| `SourceChunk` | `chunk_id` | Location of a cited passage (no text) | promotion |
| `RetractedClaim`, `RetractedEvidence` | as above | Relabelled after an approval is withdrawn (nothing is deleted) | `retract --apply` |
| `PractitionerFeedback` | `feedback_id` | Append-only review note; never changes a claim | `POST /api/v1/c2/feedback` |

The following entity types appear in the addendum but are **not** added:

- **TraditionalTerm, Synonym, Transliteration.** Term variants live in the
  reviewed lexicon (`knowledge/seed_lexicon_v1.json`). They are used for
  matching, not as graph facts. Variants of one term are listed together.
  Different terms, such as Pandu and anaemia, are never merged.
- **EvidenceClaim, EvidenceClassification.** These are covered by `:Claim`
  plus the `evidence_type` and `verification_status` properties.
- **SourceVersion.** This is covered by `Source.content_sha256` plus the
  chunker and normalization versions on `SourceChunk`. A new file version
  gets a new content hash. Reusing a `source_id` for different content
  aborts promotion.
- **Ingredient, TraditionalUse.** Ingredients are modelled as `Herb` via
  `CONTAINS_INGREDIENT` (descriptive). Traditional uses are modelled
  through a `TherapeuticPrinciple`, not as a shortcut.

## 3. Relationship types

| Type | From → To | Meaning | Provenance carried |
|---|---|---|---|
| `SUBJECT_OF` | concept → `Claim` | The concept is the claim's subject | claim properties |
| `OBJECT_OF` | `Claim` → concept | The concept is the claim's object | claim properties |
| `SUPPORTS` | `Evidence`/`DescriptiveEvidence` → `Claim` | The quoted passage states the claim | evidence properties |
| `CONTRADICTS` | `Evidence` → `Claim` | The quoted passage states the opposite. It is kept alongside support and never merged. | evidence properties |
| `FROM_CHUNK {sentence_start, sentence_end}` | evidence → `SourceChunk` | The exact character span of the quoted sentence in the chunk text | span on the relationship |
| `PART_OF` | `SourceChunk` → `Source` | Chunk to source edition | `SourceChunk.source_id` |
| `REVIEWS` | `PractitionerFeedback` → `Claim` | A feedback record about a claim | feedback properties |

**Claim predicates** are stored as `Claim.predicate`, not as relationship
types. Allowed values come from `RELATIONSHIP_RULES` (ontology v1.0):

- `INDICATES`
- `ASSOCIATED_WITH_DOSHA`
- `AFFECTS_DHATU`
- `SUGGESTS_PRINCIPLE`
- `USES_HERB`
- `USES_FORMULATION`
- `RECOMMENDS_DIET`
- `RECOMMENDS_LIFESTYLE`

`DESCRIPTIVE_RELATIONSHIP_RULES` (v1.1) adds `CONTAINS_INGREDIENT`. Subject
and object types are checked on write and again on every traversal.

## 4. Required properties

| Node | Required | Notes |
|---|---|---|
| `Claim` | `claim_id`, `subject_id`, `predicate`, `object_id`, `verification_status` | `verification_status` is one of `unverified`, `literature_supported`, `practitioner_verified`, `disputed`. `confidence` stays null unless calibrated. Promoted claims also carry `candidate_id`, `approved_by`, `approved_role`, `approved_at`, `extractor_version`, `lexicon_version` and `promotion_batch_id`. |
| `Evidence` | `evidence_id`, `title`, `source_name`, `evidence_type`, `text`, plus one of `citation`/`source_url`/`page`/`section` | Promoted evidence also has `source_id`, `chunk_id` and `candidate_id`. `citation` names the TEI verse references the chunk covers (e.g. `chunk covers Ca.6.16.1 to Ca.6.16.4`) or the danda verse numbers. |
| `Source` | `source_id`, `content_sha256`, `title` | Plus curated sidecar metadata: edition, languages, `usage_notes` (licence), `evidence_category`. Null values are never written. |
| `SourceChunk` | `chunk_id`, `source_id`, `content_sha256`, `chunker_version`, `normalization_version` | Location fields: pages, lines, `section_heading`, `verse_numbers`, `citation_refs`, `printed_pages`. **No text** (decision D1). |

## 5. Identity rules

- **`source_id`**: curated (`.meta.json`) or `src-<sha256 prefix>`. It
  identifies an edition. The registry assigns stable curated IDs such as
  `sarit-carakasamhita`.
- **`chunk_id`**: `<source_id>#chk-<hash>`. The hash covers the source, the
  exact passage spans, the normalized text and the chunker and
  normalization versions, so it is stable across re-runs.
- **`evidence_id`**: `EV-` (or `DEV-`) followed by a hash of the chunk ID
  and the sentence span.
- **`claim_id`**: `CL-<candidate claim_id>` for promoted claims. Every write uses `MERGE` on
  these IDs, so re-running a promotion creates no duplicates.
  `created_at` is set only `ON CREATE`.
- **Overlapping stores.** The local chunk store and the graph share
  `chunk_id` and `source_id`. The graph never holds unreviewed chunks.
  Evidence in the API's in-memory index carries `source_id` and
  `source_chunk_id` back to the local passage. The two stores are **not**
  synchronized automatically:
  - re-chunking with a new chunker version produces new chunk IDs
  - existing claims keep pointing at the old ones
  - candidates whose passage changed become `stale` and are found by
    `retract`

## 6. Constraints

| Constraint | Status in AuraDB (2026-10-19) |
|---|---|
| `<label>_id_unique` for the 11 core labels (`initialize_schema`) | Present |
| `source_id_unique`, `sourcechunk_id_unique`, `descriptiveevidence_id_unique`, plus 4 indexes (`initialize_source_schema`) | **Not applied.** `source-schema --apply` needs explicit authorization. |
| `PractitionerFeedback.feedback_id` uniqueness | Not present. Enforced in application code only (known limitation). |

The server is Neo4j 5.27-aura enterprise, which supports node-key and
uniqueness constraints and vector indexes. No vector index is created
(decision D2).

## 7. Validation (read-only)

```bash
python -m app.db.graph_validation            # summary; exit 1 on errors, 3 if DB unavailable
python -m app.db.graph_validation --json     # full report
curl http://127.0.0.1:8000/health/graph-validation
```

The validator runs only in READ sessions with per-query timeouts. It
returns counts and IDs, never text.

| Check | Severity |
|---|---|
| Relationship types outside §3 | error |
| Labels outside §2 | warning |
| Missing core constraints | error |
| Stage E schema not applied | info |
| Claim missing required property / unknown predicate / unknown status | error |
| Claim without exactly one matching `SUBJECT_OF` / `OBJECT_OF` | error |
| Claim without supporting evidence | warning |
| Orphaned evidence (supports nothing) | warning |
| Evidence with incomplete provenance or empty text | warning |
| Evidence naming a `chunk_id` without the `FROM_CHUNK` link | error |
| Evidence naming a `source_id` with no `Source` | error |
| `SourceChunk` without its `PART_OF` source | error |
| `SourceChunk` cited by no evidence | warning |
| `Source` without `content_sha256` or `title` | error |
| Missing or empty identity properties | error |
| Duplicate IDs (checked only where no constraint exists) | error |
| Repeated identical relationships | warning |
| Graph has no claims | info: reasoning will abstain |

**Current result: valid.** The graph holds 0 nodes and 0 relationships, so
the two info findings above apply.

## 8. Bounded traversal

- Reasoning follows outgoing claims only.
- The depth limit is 5 and the chain limit is 100 per symptom. Truncation
  is flagged.
- Cycles are prevented.
- Concepts are fetched in one batch query.
- Graph access is bounded:
  - Each distinct concept is queried once per trace. A concept reached by
    several chains is served from a per-trace cache.
  - Each claim's supporting and contradicting evidence comes back in that
    same concept query, so there is no separate per-claim evidence query.
  - The trace reports `graph_queries`.
  - A level-wise batch query (one query per depth) is a possible further
    step if graphs grow large.

## 9. Treatment path: reviewer-modelled claims

Rule-based extraction can only produce the three predicates that map
directly to the ontology:

- `INDICATES` (from `HAS_SYMPTOM`)
- `ASSOCIATED_WITH_DOSHA`
- `AFFECTS_DHATU`

Treatment is Roga → `SUGGESTS_PRINCIPLE` → TherapeuticPrinciple →
`USES_HERB` / `USES_FORMULATION` / `RECOMMENDS_*`. These claims are
authored by a reviewer with `model-claim`
(`app/knowledge_candidates/modelled.py`, stored in
`candidates/modelled_claims.jsonl`, with an append-only
`modelled_log.jsonl`).

A modelled claim is refused unless all of these hold:

- the predicate is a v1.0 reasoning predicate
- the concept types satisfy that predicate's rule
- the quote occurs exactly once in the cited chunk's text
- a named reviewer, a role and a rationale note are given

The evidence text is copied from the chunk at the quoted span, never
typed in.

`promote` plans modelled claims with the same checks as candidates:

- curated source metadata
- a current chunk whose text still contains the quote ("stale" otherwise)
- the creation event present in the log

Promoted modelled claims carry `modelled: true`, `modelling_note`,
`approved_by` and `approved_role`. `withdraw-modelled` followed by
`retract` stops using a claim without deleting anything.

`test_dataset_to_api.py` covers this path end to end: a modelled
principle claim and a herb claim are promoted with an extracted
`INDICATES` claim, and the API returns a herb candidate whose evidence
references point to the quoted source chunks.

**State on 2026-10-19:** no modelled claims exist in the real store.
Authoring them is practitioner work. A modelled claim records a
reviewer's reading of a traditional text, not clinical efficacy.

## 10. Provisional research pathway

Approved knowledge (`:Claim` / `:Evidence`, §1–§9) requires a named human
approval. The provisional pathway stores AI-assisted draft claims taken
from classical texts. It sits next to the approved pathway, and the two
never mix.

**Labels and relationships.** Provisional records use their own labels and
relationship types only:

| Element | Name |
|---|---|
| Claim node | `:ProvisionalClaim` (`claim_id` = `PCL-` + sha256(subject, predicate, object)[:20]) |
| Evidence node | `:ProvisionalEvidence` (`evidence_id` = `PEV-` + sha256(source_id, passage_index, start, end)[:20]) |
| Concept → claim | `PROVISIONAL_SUBJECT_OF` |
| Claim → concept | `PROVISIONAL_OBJECT_OF` |
| Quote → claim | `PROVISIONALLY_SUPPORTS` (primary text or translation) |
| Modern reference → claim | `PROVISIONALLY_QUALIFIES` (qualifies, never supports) |
| Evidence → chunk → source | `FROM_CHUNK`, `PART_OF` (shared with Stage E) |

Concept nodes are shared with the approved pathway. Missing concepts are
created `ON CREATE` only, marked `concept_status: 'provisional'`. An
existing concept's properties are never changed.

**Fixed status.** Every provisional claim has:

- `verification_status: 'unverified'`
- `knowledge_status: 'provisional'`
- `extraction_method: 'ai_assisted_draft'`
- `review_status: 'pending_practitioner_review'`

The planner refuses any other `extraction_method`. Nothing in this pathway
can set `literature_supported` or `practitioner_verified`.

**Planner checks.** `app/knowledge_provisional/plan.py` rejects a claim
unless:

- every quote occurs exactly once in the cited passage (`element_id`) of an
  extracted source, after NFC and whitespace normalisation
- the quote also lies in a current chunk
- the source has curated title, category and licence metadata
- both concepts are declared
- the triple satisfies the ontology (v1.1, descriptive `CONTAINS_INGREDIENT`
  allowed)
- at least one quote is primary-source text (translation alone is not
  enough)

Duplicate keys or triples are reported, not merged. The same passage span
cannot serve two evidence roles.

**Reading it.** Default reasoning (`knowledge_scope=approved`) never
queries provisional labels. Research scope
(`knowledge_scope=approved_and_provisional`) passes a `ResearchGraphAccess`
object through the reasoning code. That object reads both pathways and
tags every claim and evidence item with `knowledge_status`.

`sufficiency._assess_path` treats any provisional claim as unverified
(flag `provisional_unverified_claim`). A candidate path that contains one
can therefore never reach `sufficient_for_review`. The request-level
decision gets the reason `knowledge:provisional_records_used`.

**Validation.** `app/db/graph_validation.py` adds `_provisional_checks`:

- status and links are correct
- every claim has a quote and a known predicate
- no approved-pathway relationship touches a provisional node
- every evidence item has a chunk and source chain
- no quote is empty

**Commands.**

```bash
python -m app.knowledge_provisional plan   knowledge/provisional/pandu_traditional_v1.json --extracted corpus/extracted --check-graph --out <report>   # dry run, read-only
python -m app.knowledge_provisional apply  knowledge/provisional/pandu_traditional_v1.json --extracted corpus/extracted --confirm-live-write --out <report>
python -m app.knowledge_provisional verify knowledge/provisional/pandu_traditional_v1.json --extracted corpus/extracted --out <report>          # read-only
python -m app.db.graph_validation
```

`apply` refuses to run without `--confirm-live-write` or when the plan has
rejections. Writes are MERGE-only, in one transaction per claim, with
before and after snapshots.

**State on 2026-10-20:** `pandu-provisional-v1` was applied to AuraDB in
batch `prov-20261020T100212Z`. See `docs/provisional_knowledge_report.md`.

**Promotion.** A provisional claim becomes approved knowledge only through
the existing Stage E route: a practitioner authors it as a modelled claim
(§9) with a named reviewer, and it is then promoted. The provisional
record is kept as history; nothing is converted in place.
