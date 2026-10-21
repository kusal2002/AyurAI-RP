# Stage E — Neo4j Persistence Design

Status:

- **D1–D6 approved on 2026-10-19 and implemented in dry-run form.**
- **D7 (applying the schema) and any `--apply` promotion still need
  explicit confirmation.**
- No schema change, constraint, index, node or relationship has been
  created in AuraDB.

### Implementation

| Piece | Where |
|---|---|
| Additive schema | `app/db/schema.py:initialize_source_schema()` (dry run by default) |
| Promotion | `app/db/source_repository.py`: `plan_promotions()` (no database), `promote(apply=False)` |
| CLI | `source-schema [--apply]`, `promote CANDIDATES --extracted DIR [--manifest FILE] [--apply]`, `retract CANDIDATES [--apply]` |
| Ontology v1.1 | `DESCRIPTIVE_RELATIONSHIP_RULES` in `app/ontology/relationships.py` |
| Tests | `test_stage_e_promotion.py`: fake driver, no live database |

### Correction to D4

The proposal below says `CONTAINS_INGREDIENT` would not affect ranking.
Adding it to `RELATIONSHIP_RULES` *would* have changed reasoning, because
`knowledge_chain` traverses every predicate in that map. It is therefore
kept in a separate `DESCRIPTIVE_RELATIONSHIP_RULES` map, which only
`validate_relationship(..., allow_descriptive=True)` accepts. A test shows
that reasoning chains are identical with and without a descriptive claim.

### Audit fixes (2026-10-19)

A read-only audit found the gaps below. Each is now fixed and tested in
`test_stage_e_promotion.py`. Nothing has been applied to AuraDB.

| Finding | Fix |
|---|---|
| A `CONTAINS_INGREDIENT` claim's supporting sentence was written as `:Evidence`. The API evidence index loads every `:Evidence` node, so the sentence could appear in C2 `retrieved_evidence` and set the `retrieved_evidence_not_linked_to_claims` flag. | Descriptive claims now get `:DescriptiveEvidence`, with `DEV-` IDs and `descriptive: true` on the claim. `list_evidence` matches `:Evidence` only, and chain traversal ignores the predicate. |
| An `approved` status with no approval event crashed promotion (`StopIteration`). | `approval_event()` requires the latest review event to be an approval of this candidate by a named reviewer. `trusted_candidates()` uses it, and promotion now skips such candidates with a reason. |
| Hand-edited candidate files were trusted. | Loading a candidate now rejects a status that its review history doesn't produce, including events for another candidate or a broken status chain. The `promote` command also requires the approval event to be present in the append-only `review_log.jsonl`. These are consistency checks, not signatures: someone with write access to both local files can still forge a record. |
| `Claim.created_at` was overwritten on every `--apply`. | `created_at` is set only `ON CREATE`, and is no longer part of the overwritten properties. |
| A `source_id` reused for different file content would silently overwrite `Source.content_sha256`. | Planning skips sources the manifest lists in `source_id_conflicts`. Inside the transaction, a stored `Source` with a different `content_sha256` aborts the whole claim. |
| Withdrawing an approval after promotion left the graph claim active. | `retract` (dry run by default) finds candidates that were approved once but are no longer trusted (withdrawn, superseded or stale). With `--apply` it would relabel `:Claim` as `:RetractedClaim`, and evidence that supports no active claim as `:RetractedEvidence`. **Nothing is deleted.** Re-approving and promoting restores the original labels. |
| Neo4j errors inside a transaction and rejected candidates were untested. | Tests added for both, plus tests for the review-log check, manifest conflicts, the source-hash guard and retraction. |
| `test_neo4j_connection.py` connected to AuraDB at import, so pytest collection alone contacted the live database. | The check now runs in `main()`, only when the script is executed directly. A test proves importing it opens no connection. |

The schema dry run now lists **7** additive statements. Three were added to
support descriptive evidence and non-destructive retraction (see §3).

### First real dry run (2026-10-19)

- `source-schema`: the statements in §3, not applied.
- `promote`: 12 candidates, **0 to promote**, all skipped as
  `not approved (candidate)`.
- Even once approved, every current source would also be skipped as
  `source metadata has no title`, because no `.meta.json` sidecars exist
  yet. Promotion therefore needs both review decisions and curated source
  metadata.

The rest of this document is the approved proposal.

Original inspection note: no schema change, constraint, index, node or
relationship has been created. Everything below came from a
read-only inspection on 2026-10-19: the session used `READ` access mode and
`execute_read`, and printed metadata and counts only.

## 1. What the live AuraDB has today

| Item | Finding |
|---|---|
| Server | Neo4j **5.27-aura**, enterprise edition; Cypher 5 and Cypher 25 available |
| Data | **Empty**: 0 nodes, 0 relationships |
| Constraints | 11 uniqueness constraints from `app/db/schema.py:initialize_schema()`: Symptom, Roga, Dosha, Dhatu, TherapeuticPrinciple, Herb, Formulation, Diet, Lifestyle, Evidence, Claim (each on its ID property) |
| Indexes | The 11 range indexes that back those constraints, plus 2 default LOOKUP indexes. No vector or full-text index. |
| Vector support | Present: `db.index.vector.queryNodes`, `vector.similarity.cosine`, `vector_*` functions |
| Embedding inside the database | `genai.vector.encode` / `encodeBatch` exist. They send text to an external embedding provider, so **this design never uses them**. |
| Tier and limits | Not visible from Cypher. Check the Aura console for node and relationship limits, memory and storage before any bulk load. |

How existing code reads the graph, which sets the trust boundary:

- Reasoning reads `:Claim` nodes only, through `SUBJECT_OF` / `OBJECT_OF`
  from concept nodes, and evidence through `SUPPORTS` / `CONTRADICTS`.
- The API's evidence index (`list_evidence`) loads **every `:Evidence`
  node**. Anything labelled `:Evidence` therefore becomes retrievable API
  evidence immediately.
- `save_claim` requires the subject and object concept nodes to exist
  already. `save_claim` and `link_evidence_to_claim` each open their own
  session, so together they are not one transaction.

## 2. Principles

1. **Additive only.** Use `CREATE CONSTRAINT/INDEX … IF NOT EXISTS`. Nothing
   is dropped, renamed or reset. Existing constraints and code paths are
   unchanged.
2. **Trust boundary in the graph.**
   - Only approved candidates become `:Claim` and `:Evidence`.
   - Raw chunks and unreviewed candidates never get those labels, so no
     existing query can read them as knowledge.
3. **No patient data.** This graph holds source and knowledge records only.
4. **Idempotent and atomic.**
   - `MERGE` on stable IDs: `source_id`, `chunk_id`, `claim_id`, a derived
     `evidence_id`.
   - All writes for one promoted claim run in **one** write transaction, so
     a failure leaves nothing half-written.
5. **Parameterized Cypher only.** Labels and relationship types come from
   fixed allow-lists in code, never from data.
6. **Copyright and privacy.**
   - AuraDB is a hosted external service.
   - Full book text and chunk embeddings are not uploaded by default (see
     D1 and D2).
   - Only a short supporting sentence for an *approved* claim is stored, as
     `Evidence.text`.
7. **Reuse.** Keep `EvidenceRecord`, `Claim`, `validate_evidence_provenance`,
   `validate_relationship` and the existing driver. Do not create a second
   connection pool.

## 3. Proposed graph model

```
(:Source {source_id})              one per edition/file identity
    ^ PART_OF
(:SourceChunk {chunk_id})          provenance only (no text by default)
    ^ FROM_CHUNK
(:Evidence {evidence_id})          existing label: approved supporting sentence
    -[:SUPPORTS]->
(:Claim {claim_id})                existing label: approved, ontology-mapped
    <-[:SUBJECT_OF]- (concept)     existing pattern
    -[:OBJECT_OF]->  (concept)
```

### New labels

**`:Source`** — one per edition or file identity.

- Key: `source_id`.
- Properties:
  - `content_sha256`, `source_format`, `file_name`
  - `title`, `author`, `editor`, `edition`, `publication_year`,
    `publisher`, `translator`
  - `source_language`, `translation_language`
  - `evidence_category`, `usage_notes`
  - `extraction_status`, `extractor`, `extractor_version`, `ingested_at`
- Null values are not written, so nothing is fabricated.

**`:SourceChunk`** — the location of an approved supporting sentence.

- Key: `chunk_id`.
- Properties:
  - `source_id`, `chunk_index`
  - `page_start`, `page_end`, `line_start`, `line_end`
  - `section_heading`, `verse_numbers`
  - `primary_script`, `scripts`
  - `content_sha256`, `chunker_version`, `normalization_version`,
    `quality_flags`
- **No `text`** by default (D1).
- Chunks are created only when an approved claim cites them. They are not
  bulk-loaded (D2).

### Existing labels, extended additively

**`:Evidence`** — written through the existing `EvidenceRecord` and
`save_evidence` validation.

| Field | Value |
|---|---|
| `evidence_id` | `EV-` + hash of (chunk_id, sentence span) |
| `title`, `source_name` | From the source's curated metadata. **Required**: a source without a metadata sidecar cannot be promoted. |
| `evidence_type` | Mapped from `evidence_category` (D6) |
| `page`, `section` | From the chunk |
| `text` | The supporting sentence |
| `citation` | Verse numbers, when present |
| `practitioner_verified` | True if a practitioner approved it |
| Extra properties | `chunk_id`, `source_id`, `candidate_id` |

**`:Claim`** — produced by `to_ontology_claim()` for mappable predicates.

- `verification_status` is `practitioner_verified`, `literature_supported`
  or `disputed`, as already implemented.
- Extra properties: `candidate_id`, `approved_by`, `approved_role`,
  `approved_at`, `extraction_method`, `extractor_version`,
  `lexicon_version`, `descriptive`.
- `qualified_statement` (extractor v4): true when the supporting sentence
  limits the claim to a historical period or to stated proportions. Read
  the evidence text before using such a claim.
- Confidence stays null.

**Concept nodes** (`:Roga`, `:Herb` and so on) are `MERGE`d by ID only when
an approved claim needs them. Properties: `name` (the lexicon label),
`lexicon_version`, `created_by = "candidate_promotion"` (D5).

### New relationships

| Relationship | Purpose |
|---|---|
| `(:SourceChunk)-[:PART_OF]->(:Source)` | Chunk to source |
| `(:Evidence)-[:FROM_CHUNK {sentence_start, sentence_end}]->(:SourceChunk)` | Exact location of the quoted sentence. Descriptive claims use `(:DescriptiveEvidence)` with the same relationship. |

### Additive schema (all `IF NOT EXISTS`)

```cypher
CREATE CONSTRAINT source_id_unique IF NOT EXISTS
  FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
CREATE CONSTRAINT sourcechunk_id_unique IF NOT EXISTS
  FOR (c:SourceChunk) REQUIRE c.chunk_id IS UNIQUE;
CREATE INDEX sourcechunk_source_id IF NOT EXISTS
  FOR (c:SourceChunk) ON (c.source_id);
CREATE INDEX claim_candidate_id IF NOT EXISTS
  FOR (c:Claim) ON (c.candidate_id);
CREATE CONSTRAINT descriptiveevidence_id_unique IF NOT EXISTS
  FOR (e:DescriptiveEvidence) REQUIRE e.evidence_id IS UNIQUE;
CREATE INDEX retractedclaim_claim_id IF NOT EXISTS
  FOR (c:RetractedClaim) ON (c.claim_id);
CREATE INDEX retractedevidence_evidence_id IF NOT EXISTS
  FOR (e:RetractedEvidence) ON (e.evidence_id);
```

These touch no existing data. The empty database means there is nothing to
backfill.

## 4. Vector index in AuraDB vs the local store

The local store is
`corpus/extracted/embeddings/<model>/vectors.npy + chunks.jsonl`.

| | AuraDB vector index | Local store (current) |
|---|---|---|
| Works now | Supported by 5.27; not created | Built and tested; 28,128 book chunks embedded with e5-small |
| Content leaving the machine | Chunk vectors and IDs, and chunk text if search results must show it. These are derived from copyrighted books and go to a hosted service. | None |
| Size | ~82,862 × 384 float32 ≈ 127 MB raw, plus index overhead. Must fit the Aura tier's memory and storage. | 127 MB file, memory-mapped |
| Query embedding | Still computed locally (e5 on the VPS). `genai.vector.encode` would send queries out, so it is not used. | Computed locally |
| Shared across workers and machines | Yes | No; copied or rebuilt per machine |
| Joins with graph provenance | In one query | By `chunk_id` lookup |
| Who can see it | Anyone with database access | Only this machine |

**Recommendation:**

- Keep **source-chunk vectors in the local store**. **Do not** create an
  Aura vector index for book chunks now.
- Revisit only if several workers need shared search *and* the source
  licences allow hosting derived data.
- A small Aura vector index over approved `:Evidence` sentences (a few
  hundred short quotes) is a reasonable later option. It needs its own
  approval.

## 5. Candidates and reviews: local or in Aura?

Today's local file store (`candidates.jsonl`, `review_log.jsonl`,
`conflicts.json`) keeps unreviewed machine output out of the shared graph
completely.

**Recommendation:**

- Keep candidates and reviews **local** for now.
- Push only approved results, with the approval summary as properties on
  `:Claim`.
- The full review log stays local. It is append-only and can be backed up
  as a file.
- Mirror candidates to Aura (as a separate `:CandidateClaim` label that
  existing queries never match) only when a multi-reviewer UI needs it.

## 6. Predicates the ontology cannot express yet

`to_ontology_claim()` maps three candidate predicates directly:

- `HAS_SYMPTOM` becomes `INDICATES`, with subject and object swapped
- `ASSOCIATED_WITH_DOSHA` maps one to one
- `AFFECTS_DHATU` maps one to one

Three do not map:

| Candidate predicate | Issue | Recommendation |
|---|---|---|
| `CONTAINS_INGREDIENT` (Formulation → Herb) | Not in ontology v1.0 | Add to an ontology **v1.1** as a descriptive predicate. It doesn't affect candidate ranking. |
| `TRADITIONALLY_INDICATED_FOR` (Herb/Formulation → Roga/Symptom) | The ontology routes treatment through a TherapeuticPrinciple | Don't add a shortcut. A reviewer models it as `SUGGESTS_PRINCIPLE` + `USES_HERB` claims, or it stays a reviewed candidate only. |
| `HAS_CAUTION` | Safety content; Component 3 owns safety assessment | Don't feed it into C2 ranking. Discuss handing it to C3 (contract change, needs approval). |

## 7. Implementation plan once approved

1. **Schema function.** Add `initialize_source_schema(driver, dry_run=True)`
   in `app/db/schema.py`:
   - It is a new function; the existing `initialize_schema` is left alone.
   - Dry run prints the four statements.
   - It applies them only with `--apply`.
2. **Promotion function.** Add `promote_approved_candidates(store, driver,
   dry_run=True)` in a new `app/db/source_repository.py`. For each trusted,
   mappable candidate it validates everything first: source metadata
   complete, evidence type mappable, ontology relation valid. Then it runs
   **one `execute_write` transaction** that MERGEs, in order:
   1. the Source
   2. the SourceChunk
   3. the concept nodes
   4. the Evidence (via `EvidenceRecord`)
   5. the Claim (same Cypher pattern as `save_claim`)
   6. the `SUPPORTS` and `FROM_CHUNK` links

   Dry run reports what would be created and every candidate that is
   skipped, with the reason.
3. **CLI.** Add `python -m app.knowledge_ingestion promote
   corpus/extracted/candidates [--apply]`, with dry run as the default.
4. **Evidence refresh.** After applying, refresh the API evidence index
   (existing `/api/v1/c2/evidence-index/refresh`) so approved evidence
   becomes retrievable.
5. **Tests.**
   - A fake or mocked driver that records Cypher and parameters.
   - Re-running the promotion is idempotent.
   - Unapproved, stale and unmappable candidates are never written.
   - Writes are atomic: a simulated failure mid-transaction leaves nothing
     behind.
   - A clear error when the database is unavailable.
   - The existing C2 API regression tests keep passing.
   - No live AuraDB is needed. An optional integration test cleans up only
     nodes it created, using IDs prefixed `TEST-STAGEE-`, following
     `test_neo4j_pipeline.py`.
6. **Before the first `--apply`:**
   - Take an Aura console snapshot (your action).
   - Run the dry run on the real candidate store and review the output.
7. **Retraction and rollback.**
   - When an approval is withdrawn, use `retract` (dry run by default). It
     relabels claims and unsupported evidence and never deletes anything.
   - Every promotion writes `promotion_batch_id` on the nodes it creates.
     Removing a whole batch would mean deleting the nodes and relationships
     carrying that ID. No such function exists, and deleting is a separate
     action that needs your approval.

## 8. Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| D1 | Store chunk **text** in Aura? | **No.** Store provenance and hashes only. Only the approved supporting sentence goes into `Evidence.text`. |
| D2 | Create an Aura **vector index** for source chunks? | **No.** Keep the local e5 store. |
| D3 | Candidates and review log in Aura? | **No**, local only. Push approved claims only. |
| D4 | Ontology v1.1 additions | Add `CONTAINS_INGREDIENT` only. Keep `TRADITIONALLY_INDICATED_FOR` out (model it through a principle). Raise `HAS_CAUTION` with the C3 owners. |
| D5 | Concept nodes from the lexicon | Create only those an approved claim needs, marked with `lexicon_version`. The seed lexicon still needs expert review first. |
| D6 | `evidence_category` to existing `EvidenceType` | `traditional_text` → `classical`; `modern_clinical_research` and `systematic_review` → `modern_research`; `practitioner_interpretation` → `practitioner`; `other` → **block promotion**, since there's no honest mapping. |
| D7 | Apply the four additive schema statements | Only after D1–D6 are agreed, and after a dry run. |

Nothing in this document has been executed against the database.
