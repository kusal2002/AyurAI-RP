# Source-Document Ingestion (Stages A–E)

This document covers the `app.knowledge_ingestion` package. It turns local
Ayurvedic source files into extracted passages with source locations,
explicit extraction statuses and provenance metadata (Stage A), then into
normalized, traceable chunks (Stage B) and a local embedding store with
semantic search over those chunks (Stage C), then into reviewable
candidate claims (Stage D).

Extraction reproduces what is in a file. It does **not** establish that any
statement in a book is correct, and extracted text is not trusted knowledge.
Curated evidence still enters Neo4j only through the existing
`python -m app.retrieval.ingestion` command (implementation notes §6).

## Status of the planned stages

| Stage | Scope | State |
|---|---|---|
| A | Format readers, source locations, hashes, statuses, manifest, CLI | Implemented |
| B | Unicode-safe normalization, script metadata, chunking, stable chunk IDs, validation | Implemented |
| C | Chunk embedding store, source-chunk search, retrieval evaluation harness | Implemented; source store uses `intfloat/multilingual-e5-small` |
| D | Candidate-claim models, rule-based extraction, review states, conflicts, trust boundary | Implemented (seed lexicon needs expert review) |
| E | Promotion of approved candidates to Neo4j (`docs/stage_e_neo4j_design.md`) | Implemented as dry run; `--apply` not yet run |
| F | Integration with retrieval/reasoning, evaluation harness | Partly done (2026-10-19). Promoted evidence carries `source_id`/`source_chunk_id` into API responses. An end-to-end test covers the path from registry to API. The treatment path is not populated (`knowledge_graph_schema.md` §9). |

## Architecture

```
app/knowledge_ingestion/
  models.py      SourceFormat, ExtractionStatus, SourceLocation,
                 ExtractedPassage, ExtractionResult, SourceMetadata,
                 SourceRecord, SourceManifest
  extractors.py  extract_document() and one extractor per format
  manifest.py    SHA-256 fingerprints, source IDs, sidecar metadata,
                 duplicate and source-ID conflict detection
  normalization.py  normalize_text(), profile_scripts(), find_verse_numbers()
  chunking.py    segment_spans(), chunk_passages(), validate_chunks()
  service.py     process_source(), write_extraction(), build_manifest(),
                 scan_hashes(), chunk_extraction_output(), write_chunks()
  cli.py         python -m app.knowledge_ingestion ...

app/retrieval/
  source_chunks.py  build_embedding_store(), SourceChunkIndex,
                    evaluate_retrieval() (reuses EmbeddingEncoder,
                    SentenceTransformerEncoder, normalize_rows)

app/knowledge_candidates/
  models.py      CandidateClaim, ReviewStatus, ReviewEvent, Conflict,
                 CANDIDATE_PREDICATES, ONTOLOGY_MAPPING
  lexicon.py     curated concept lexicon and script-aware matching
  extractor.py   rule-based LexiconCueExtractor (CandidateExtractor protocol)
  conflicts.py   conflict detection (never auto-resolved)
  review.py      review_candidate(), trusted_candidates(), to_ontology_claim()
  store.py       file-based candidate store and run_extraction()
knowledge/seed_lexicon_v1.json   seed lexicon (unreviewed)
```

None of these modules imports FastAPI or Neo4j. No API endpoint was added:
the CLI and service functions run locally, and no remote client can supply
a filesystem path.

## Supported formats

| Format | Reader | Passage unit | Location fields |
|---|---|---|---|
| PDF (text layer) | `pypdf` | one passage per page | `page` (1-based physical page, not the printed folio) |
| DOCX | standard library (`zipfile` + `ElementTree`) | body paragraph, heading, or table row (cells joined by ` \| `) | `block_index`, `table_index`, `row_index`, `section_heading` |
| EPUB 2/3 | standard library (`zipfile` + `html.parser`) | block element (p, li, h1–h6, tr, …) in spine order | `item_id`, `item_href`, `block_index`, `section_heading` |
| TXT | standard library | blank-line separated paragraph | `line_start`, `line_end`, `block_index` |
| Markdown | standard library | paragraph or ATX heading (`# …`) | as TXT, plus `section_heading` |
| TEI P5 XML (`.xml`, e.g. SARIT) | standard library (`ElementTree`) | `<head>`, `<lg>` (lines kept), `<p>`, `<ab>`, `<l>`, `<item>` | `element_id` (xml:id verse reference, e.g. `Ca.6.16.5`), `printed_page` (`<pb n>`), `section_heading` (nearest `<head>`), `item_id` (`div:` path) |
| JATS XML (`.xml`, Europe PMC full text) | standard library | article title, abstract, section titles, paragraphs, table rows (cells joined by ` \| `) | `element_id` (`id` attribute), `section_heading`, `item_id` (`sec:` path), table and row index |

Not supported: `.doc`, `.rtf`, `.odt`, HTML, images, DRM-protected EPUBs, and
XML that is neither TEI nor JATS. They get the status `unsupported_format`
or `failed`.

**XML specifics:**

- *TEI.* Editorial `<note>` elements (variant readings, cross-references),
  `<label>` reference labels and footnote markers are left out of the
  passage text. Each passage that lost a note is flagged
  `editorial_notes_omitted`, and the total is reported as a warning. XML
  indentation is collapsed. Verse lines and `<lb/>` stay as line breaks.
- *JATS.* `<back>` matter (reference list, acknowledgements) is not
  extracted.
- *Header metadata.* The TEI header and JATS front matter (title, licence,
  DOI) go into `embedded_metadata`, as found. They are never copied into
  curated metadata.
- *Safety.* ElementTree does not resolve external entities, so a file that
  declares one fails to parse.
- *Nested headings.* A part heading followed directly by a nested
  division's heading stays in the same chunk as that division's first
  text. It never forms a heading-only chunk (fixed 2026-10-20; see
  `dataset_discovery.md` §7).
- *Citations in chunks.* Chunks list the element IDs they cover in
  `citation_refs`, and the printed pages in `printed_pages`. Promoted
  evidence cites them, e.g. `chunk covers Ca.6.16.1 to Ca.6.16.4`. These
  are references **as encoded in the file**. They are not validated
  against a canonical numbering.

### Extraction statuses

| Status | Meaning |
|---|---|
| `extracted` | Every page or block produced usable text. Blank PDF pages with no images are listed in `blank_pages` and in a warning. |
| `needs_ocr_or_review` | No usable text: the pages have images but no text layer (a scan), or all the text looks garbled. |
| `partial_extraction` | Some text is usable, but some pages need OCR, failed, or look garbled, or some EPUB items could not be read. |
| `empty_or_unreadable` | The file was read but has no text and no images. |
| `unsupported_format` | The file extension is not supported. |
| `failed` | The file is missing, corrupt, encrypted, too large, mismatched to its extension, or not valid UTF-8. |

No page is dropped silently. Every PDF page ends up in exactly one of
these places:

- `passages`
- `pages_needing_ocr`
- `blank_pages`
- `page_issues` (extraction failed for that page)

### What is preserved and what is changed

- Passage text is kept as decoded. Stage A applies no Unicode
  normalization, no transliteration and no translation.
- TXT/Markdown: line terminators become `\n`. Line content is unchanged.
- EPUB: only ASCII whitespace is collapsed, as a browser does. No-break
  spaces and the ZWJ/ZWNJ joiners used in Sinhala and Devanagari are kept.
- `<script>`, `<style>` and `<head>` content is removed.
- DOCX: text deleted in tracked changes is excluded. Headers, footers,
  footnotes and comments are not extracted yet.
- Metadata embedded in a file (PDF info dictionary, DOCX core properties,
  EPUB Dublin Core) is reported in `embedded_metadata` exactly as found. It
  is never copied into the curated metadata automatically.

### Text encodings

TXT and Markdown files must be one of:

- UTF-8, with or without a BOM
- UTF-16 or UTF-32 with a BOM

Other encodings are **not guessed**, because a wrong guess silently corrupts
Sinhala or Devanagari. Such files fail with the byte offset of the first
invalid byte. Convert them to UTF-8 first.

### Garbled-text detection

A passage is flagged `suspect_characters` when more than 5% of its visible
characters (configurable) are one of:

- U+FFFD replacement characters
- private-use code points
- stray control characters

This catches PDFs whose fonts have no Unicode mapping.

It does **not** catch legacy non-Unicode Sinhala fonts such as FM-Abhaya.
Those produce plausible-looking Latin letters. Check a sample of
`*.passages.jsonl` by eye for every Sinhala source.

## OCR

Stage A does **not** run OCR. It only finds pages that need it:

- `pages_needing_ocr`
- the `needs_ocr_or_review` and `partial_extraction` statuses

No OCR engine has been added or evaluated. Notes for a future OCR adapter:

- Prefer a local engine (for example Tesseract with the `sin`, `san`/`hin`
  and `eng` language packs) so that copyrighted books are never sent to a
  cloud service.
- A missing language pack must be reported as a configuration error, not
  as low-quality text.
- Sinhala and Sanskrit OCR quality varies by engine and typeface, so it must
  be measured on sample pages before it is relied on.

## Source identity and provenance

- `content_sha256` identifies the exact file bytes. It is computed by
  streaming the file in 1 MB chunks.
- `source_id` identifies the work or edition. Its value is either:
  - the `source_id` supplied in the metadata (`source_id_origin = "metadata"`), or
  - derived from the content as `src-<first 16 hex of sha256>` (`source_id_origin = "content_hash"`).

  A corrected file or a different edition therefore never merges silently
  with another file.
- Identical content stored under two paths is reported as a duplicate group.
  It is never merged.
- One `source_id` used for files with different content is reported as a
  `source_id_conflicts` entry. This is how a re-scanned or changed edition
  that kept the old ID shows up.

### Curated metadata (sidecar file)

Put a `<file name>.meta.json` next to the book, for example
`corpus/raw/charaka.pdf.meta.json`:

```json
{
  "source_id": "charaka-samhita-chaukhambha-2011",
  "title": "Charaka Samhita",
  "editor": null,
  "edition": "2011 reprint",
  "publication_year": 2011,
  "publisher": null,
  "source_language": "sa",
  "script": "Deva",
  "translation_language": "en",
  "translator": null,
  "usage_notes": "Personal research copy; do not redistribute."
}
```

- Every field is optional. Leave unknown values `null`; nothing is filled in
  automatically.
- Unknown keys are rejected, to catch typos.
- An invalid sidecar does not stop extraction. It is reported in the
  record's `errors`, and the content-derived `source_id` is used instead.

## Normalization and chunking (Stage B)

### Normalization

Every chunk stores two texts:

- `original_text`: the exact extracted wording. Spans from different
  passages are joined by a blank line.
- `text`: a normalized copy, used for search and embeddings.

Normalization (`normalize_text`, version `NORMALIZATION_VERSION`) does only
the following:

- Applies Unicode NFC. NFKC is not used, because it would also rewrite
  compatibility characters.
- Expands Latin ligatures (`ﬁ` becomes `fi`, `ﬂ` becomes `fl`, and so on).
- Removes soft hyphens, byte-order marks, stray control characters and
  private-use code points (icon fonts, unmapped PDF glyphs).
- Turns tabs and space separators, including no-break spaces, into a single
  space, and strips spaces at line ends.
- Keeps line breaks, which matter for verse lines. Three or more line breaks
  collapse to a blank line.
- **Never** removes ZWJ or ZWNJ, changes dandas or digits, transliterates,
  translates or corrects spelling.

Chunk `quality_flags` combine the flags of the passages a chunk came from
with these normalization flags:

- `private_use_removed`
- `detached_diacritics`: spacing accents such as `˜` next to a letter.
- `letter_spaced`: text like `y o g a`, left by bad conversions.
- `symbol_noise`: more than 25% of words have symbols inside them, for
  example legacy-font Devanagari read as ASCII (`f^fcbfrHd <*j|`) or
  markup debris. The threshold was calibrated on this corpus. Lower values
  also flagged mixed chunks that hold a broken verse line next to a useful
  English translation.
- `repetitive_text`: fewer than 20% distinct words, such as table or menu
  debris (`TTA TTA TTAA ...`).

Quality flags only describe text. They never change it, so adding a flag
does not change chunk IDs or require re-embedding.
- `exceeds_max_chars`: a single unit that grew past the limit after
  ligature expansion.

### Script and language metadata

- `primary_script` and `scripts` are counted from the Unicode ranges of
  the letters only.
- Codes are `Deva`, `Sinh`, `Latn`, or `Zyyy` (any other script).
  `primary_script` is a single code when that script holds at least 80% of
  the letters, `mixed` otherwise, and `unknown` when a chunk has fewer than
  three letters.
- `iast_present` is true when the text contains IAST letters (ā, ṛ, ṣ,
  ś and others). This marks transliterated Sanskrit as distinct from
  Devanagari.
- **Language is never guessed.** Devanagari can be Sanskrit, Hindi or
  Marathi. `declared_source_language` and `declared_translation_language`
  are copied from the curated metadata sidecar and stay `null` without one.
- `verse_numbers` lists numbers printed in danda verse markers, such as
  `॥ १२ ॥` or `|| 12 ||`, with digits converted to ASCII. They are labels
  as printed, not verified verse references. Bracketed numbers like
  `[ 5-6 ]` are ignored, because research papers use them for citations.

### Chunking

`chunk_passages` (version `CHUNKER_VERSION`) works in two steps.

1. It cuts each passage into units at the largest boundary that fits the
   limit, trying these in order:

   1. paragraphs (blank lines)
   2. verse ends (`॥ n ॥`, `॥`, `|| n ||`) and sentence ends (`.`, `?`,
      `!`, `෴`)
   3. half-verse dandas (`।`), clause punctuation and line breaks
   4. whitespace
   5. a hard cut that never separates a combining mark, virama, ZWJ or ZWNJ
      from its letter

   So a verse is split only when it alone exceeds the limit, and no
   English-only tokenizer is involved.

2. It packs units into chunks of at most `C2_INGEST_CHUNK_MAX_CHARS`
   normalized characters:

   - A heading, a new section heading, or a new EPUB document starts a new
     chunk.
   - Consecutive headings stay together with the text that follows them.
   - Within a section, a new chunk repeats whole trailing units of the
     previous one, up to `C2_INGEST_CHUNK_OVERLAP_CHARS`.
   - Chunks may cross PDF pages, and `page_start`/`page_end` record the
     range.

Every chunk keeps the source location:

- `passage_spans`: the exact `[start, end)` ranges in each passage.
- `page_start` and `page_end`.
- `line_start` and `line_end`, for text files.
- `section_heading` and `item_id`.
- The declared languages.

`chunk_id` is `<source_id>#chk-<hash>`. The hash covers the source ID, the
exact spans, the normalized text and the chunker and normalization versions.

- Re-chunking unchanged input gives identical IDs and an identical file.
- An edit in one part of a book leaves chunk IDs elsewhere unchanged.
- A new chunker or normalization version produces new IDs, so stale
  embeddings cannot be matched to changed text.

### Validation

`validate_chunks` checks every chunk file against its passages:

- IDs are unique and in order.
- Every span lies inside its passage.
- The spans reproduce `original_text`.
- `text` equals the normalization of `original_text`.
- The hash and ID recompute.
- No chunk exceeds the size limit unless it is flagged `exceeds_max_chars`.
- Every non-whitespace character of every passage is in at least one chunk.
  Characters that normalization removes are exempt.

## Embeddings and source-chunk search (Stage C)

### Trust boundary

Source chunks are **unreviewed source text**:

- Every search hit carries `evidence_status = "unreviewed_source_text"`.
- The chunk index is **not** connected to `EvidenceRetrievalService` or the
  reasoning pipeline.
- The existing C1/C2 API, its output models, and the curated evidence index
  are unchanged.

The index is for finding passages during curation, and later for candidate
extraction in Stage D. Book text reaches reasoning only after review.

### Store layout

One directory per embedding model under the store root (for example
`corpus/extracted/embeddings/`, which is git-ignored):

```
<store>/<model slug>/manifest.json   model ID, dimension, query/passage prefixes,
                                     chunk and source counts, chunker and
                                     normalization versions, library versions
<store>/<model slug>/vectors.npy     float32, one L2-normalized row per chunk
<store>/<model slug>/chunks.jsonl    row -> chunk_id, source_id, spans, pages,
                                     lines, section, verse numbers, scripts,
                                     declared languages, quality flags, text
```

The store is designed so vectors and chunks can't drift apart:

- **Separate models:** models never share a directory, and a store refuses an
  encoder whose model ID, prefixes or vector dimension differ
  (`EmbeddingStoreError`, `EmbeddingDimensionError`). Changing model means
  `--rebuild` or a new store.
- **Incremental updates:** only chunks whose `chunk_id` or `content_sha256`
  changed are re-encoded, in batches of `C2_EMBEDDING_BATCH_SIZE`. Chunks
  that are no longer present are dropped.
- **Safe writes:** files are replaced atomically, so a failed or interrupted
  run leaves the previous store intact.
- **Bounded memory:** search memory-maps the vectors and scores them in
  blocks of 20,000 rows.
- **Clear failures:** if the model can't load, the existing
  `EmbeddingModelUnavailableError` is raised. There are no fake embeddings
  and no keyword fallback.

### Search

`SourceChunkIndex.search` takes these options:

- filters by script (`--script Deva`), source ID, or declared language
- `max_per_source`, for source-level deduplication
- `exclude_flags` (`--exclude-flag symbol_noise`, repeatable), which skips
  chunks with those quality flags. It is opt-in: nothing is hidden unless
  you ask, because the heuristics also catch some useful text.
- a `min_similarity` threshold, with an option to include results below it

Similarity is cosine relevance only. It is not reasoning confidence or
evidence strength.

### Evaluation harness

`search-eval` reads a JSON Lines file of hand-labelled cases and reports:

- hit rate at 1 and at k
- mean reciprocal rank
- the rank for each case

Each case looks like this:

```json
{"case_id": "pandu-1", "query": "पाण्डुरोग लक्षण", "relevant_source_ids": ["charaka-samhita-sharma"], "scripts": null}
```

Use the same cases to compare models. A handful of cases is a smoke test,
not a validation. Sinhala and Sanskrit quality can't be claimed without
labelled cases in those languages.

A case may declare how its labels were made with `"label_method"`, for
example `"lexical_pattern"` or `"human_reviewed"`. The field is optional,
so older files still load.

**Diagnostics.** `search-eval … --details` adds a `diagnostics` block to each
case. It doesn't change the scores. The block reports:

- the label method; it is inferred from a note starting "lexical label",
  otherwise `unspecified`
- the query's script
- the labelled chunks by script and by source
- labelled IDs missing from the store
- `answerable_in_query_script`: whether any labelled chunk is written in the
  query's script
- the scripts of the hits, and how many hits carry quality flags

**Pooling for human review.** `search-pool CASES --store ROOT --out FILE
[--model ID …]` writes a CSV with one row per (case, passage) retrieved by
any listed model. Each row has:

- every model's rank and similarity
- provenance: source, pages or lines, section, script, quality flags
- whether the passage is in the existing automatic labels
- the passage text
- empty `judgement`, `reviewer` and `review_notes` columns

Relevance is decided by a reviewer filling those columns; nothing is
labelled automatically, and the cases file is never written (using it as
`--out` is refused). The CSV is UTF-8 with a BOM so spreadsheets keep
Devanagari and Sinhala. It contains source-book text, so keep it in a
git-ignored folder such as `corpus/extracted/eval/`.

### Human-reviewed evaluation (`review-eval`)

Implemented in `app/retrieval/review_eval.py`. The original pool CSV and
the smoke-case JSONL are references: they are read, never written.

**Workflow**

1. Each reviewer copies the pool, for example
   `corpus/extracted/eval/pool_reviewed_<initials>.csv`, and fills three
   columns per row:
   - `judgement`: one of the values below, or blank if the row was not
     reviewed
   - `reviewer`: the reviewer's name, required whenever a judgement is given
   - `review_notes`: optional, but required for `uncertain`
2. Save as **CSV UTF-8**.
3. Run `review-eval <original pool> <copy> [more copies]`.

| `judgement` | Meaning |
|---|---|
| `relevant` | The passage answers the query |
| `partially_relevant` | On topic, but answers only part of the query |
| `not_relevant` | Does not help answer the query |
| `uncertain` | The reviewer could not decide (a note is required) |
| *(blank)* | Not reviewed |

**Validation.** Metrics are not computed while any of these problems exist:

- an invalid judgement value
- a judgement without a reviewer, or a reviewer without a judgement
- `uncertain` without a note
- a duplicate row in one file
- a row that isn't in the original pool, or pool rows missing from the copy
- a changed `query` or `source_id`
- the same reviewer judging the same row in two files

Rows are matched by (`case_id`, `chunk_id`). Ranks always come from the
original pool, so spreadsheet reformatting can't change them.

**Several reviewers.** Identical judgements from different reviewers agree.
Different judgements on the same row are a **conflict**. Conflicts are
listed in the report and treated as undetermined; they are never resolved
automatically.

**Relevance policy**

| Policy | Counts as relevant |
|---|---|
| `--policy strict` (default) | `relevant` only |
| `--policy lenient` | `relevant` and `partially_relevant` |

`uncertain`, blank and conflicting rows are undetermined: they count neither
as relevant nor as not relevant.

**How metrics are calculated**

1. For each model, ranks 1 to k are read in order. `k` defaults to 10 and
   can't exceed the pool depth.
   - The first relevant rank is that model's rank for the case.
   - A **miss** is recorded only when every rank up to k is decisively not
     relevant.
   - An undetermined passage before the first relevant one makes the case
     *undetermined* for that model.
2. A case is **scored** only if at least one of its pooled passages is
   relevant, and it is determinate for **every** compared model. So E5 and
   MiniLM are always compared on exactly the same queries.
3. Excluded cases are listed with their reason: `no_relevant_in_pool`,
   `insufficient_review (…counts…)`, or `undetermined for <model>: rank N
   is …`. They are never counted as failures.
4. Hit Rate@1, Hit Rate@k and MRR@k are computed over the scored cases.
   With no scored cases they are `null`.

The automatic labels (the smoke JSONL and `in_existing_labels`) never
affect scores. The report includes only a cross-table of automatic labels
against human judgements. Use `--cases` to check that every pooled query
still matches the smoke-case file; a mismatch exits with code 1.

The pool's ranks reflect the stores at the time it was made. After a store
is rebuilt, a new pool and new reviews are needed.

**Known problems with the current smoke labels**
(`retrieval_cases_smoke.jsonl`, audited 2026-10-19):

- **Pandu:** of the 440 chunks labelled relevant to the four Pandu queries,
  408 match only "anemia/anaemia". 301 of those come from the
  maternal–child nursing textbook. A few matches are colour words
  (*pandura*, *paripandura*).
- **No same-script targets:** all 440 labelled chunks are Latin script. The
  corpus has no Sinhala text and no Devanagari or IAST spelling of
  *pāṇḍu*. The Devanagari, Sinhala and IAST Pandu queries can therefore
  only be judged cross-lingually against English or romanized text.
- **Chunk boundaries:** labels require the keyword in the chunk itself. In
  Ashtanga Hridaya, "General properties of triphala" (labelled) continues
  into the next chunk (not labelled), which e5 ranked 6th for the Triphala
  query.

### Comparison: MiniLM vs multilingual-e5-small (smoke level)

**Setup:**
- Corpus: the 18 `ayurveda_books/` sources (28,128 chunks).
- Cases: 12 labelled cases in `corpus/extracted/retrieval_cases_smoke.jsonl`.
  - 7 English, 2 Devanagari, 2 Sinhala and 2 IAST queries.
  - Relevance is labelled by keyword patterns over chunk text, so the labels
    don't depend on either model.
  - The chance of a random top-1 hit is 0.4–2.7% per case.
- Runs: 2026-10-19, CPU only.

| Model | hit@1 | hit@10 | MRR | Embedding time | Top similarity range |
|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | 0.33 | 0.67 | 0.44 | 1,000 s (about 28 chunks/s) | 0.31–0.85 |
| multilingual-e5-small | 0.58 | 0.67 | 0.63 | about 42 min (about 11 chunks/s) | 0.85–0.91 |

Findings:

- **English queries:** e5-small ranks the relevant chunk first more often
  (hit@1 0.58 vs 0.33).
- **Cross-lingual queries mostly fail with both models:**
  - The Devanagari and Sinhala "pandu" queries return off-topic Hindi chunks
    (*Swasthya Vigyan*). The models seem to match by script more than by
    meaning, and the corpus has almost no Sinhala text.
  - e5-small's one cross-lingual success: a Sinhala diabetes query found
    English diabetes chunks at rank 2.
  - IAST "pāṇḍu roga cikitsā" failed with e5-small. MiniLM ranked a
    relevant chunk 8th, but its top results were index pages and garbled
    text.
- **No domain knowledge:** "three fruit formula" found neither model's
  triphala passages.
- **Thresholds don't transfer between models:** e5-small similarities fall
  in a narrow band (0.85–0.91), so `C2_RETRIEVAL_MIN_SIMILARITY = 0.30`
  rejects nothing. Each model needs its own threshold, calibrated before any
  threshold-based filtering.
- **Excluding flagged chunks barely changed the scores.** Mixed
  garbled/translation chunks (for example in *Ashtanga Hridaya*) fall below
  the `symbol_noise` threshold. Broken sources need curation per source, or
  re-extraction.

Twelve weakly labelled cases cannot validate a model. Judging Sanskrit,
Hindi and Sinhala retrieval needs:

- queries in those languages that practitioners have labelled
- Sinhala sources in the corpus
- OCR of the scanned classical texts

### Model and prefixes

The source-chunk store has its own settings (`load_source_retrieval_settings`)
and is independent of the curated evidence index behind the API. That index
keeps `C2_EMBEDDING_MODEL` (MiniLM) and its 0.30 threshold unchanged.

- **Model:** `C2_SOURCE_EMBEDDING_MODEL`, default
  `intfloat/multilingual-e5-small`. It was adopted after the comparison
  above.
- **Prefixes:** for e5-family models these default to `query: ` and
  `passage: `. To override them, set `C2_SOURCE_EMBEDDING_QUERY_PREFIX` or
  `C2_SOURCE_EMBEDDING_PASSAGE_PREFIX` in `.env`, quoted, because the
  trailing space matters. A store refuses a query whose prefix differs from
  the one it was built with.
- **Threshold:** `C2_SOURCE_RETRIEVAL_MIN_SIMILARITY` defaults to 0.0 (no
  filtering), because no calibrated value exists for e5.

### Model downloads

`embed`, `search` and `search-eval` run with `HF_HUB_OFFLINE=1` unless
`--allow-download` is given. A model that isn't cached therefore fails with
a clear error and is never downloaded silently. Cached at present:

- `intfloat/multilingual-e5-small` (471 MB, downloaded with approval on
  2026-10-18)
- `sentence-transformers/all-MiniLM-L6-v2` (88 MB)

Embedding the 28,128 book chunks used about 1.4–1.6 GB of RAM with
e5-small (measured), and took about 42 minutes on CPU.

## Candidate knowledge and review (Stage D)

### What a candidate is

A candidate claim records that **a source passage appears to state** a
relation, for example `Punarnava TRADITIONALLY_INDICATED_FOR Pandu`. It is
not a medical fact. Candidates are never read by the reasoning pipeline.
The only way out of review is `trusted_candidates()`, which returns
approved, non-stale candidates only.

Each candidate records:

- a stable `claim_id`
- the subject, predicate and object, as typed concepts
- the cue phrase that triggered it
- the supporting sentence, with chunk, source, page or lines, section,
  verse numbers, script, declared languages and chunk quality flags
- the declared evidence category
- the extraction method, extractor version and lexicon version
- `extraction_confidence = null`, because the rules have no calibrated
  probability and none is invented
- uncertainty notes, review status, review history and conflict IDs

### Extraction (rule-based, offline, no language model)

1. **Lexicon matching.** `knowledge/seed_lexicon_v1.json` lists concepts
   with spelling and script variants of the *same* term, for example Pandu:
   `pandu`, `pāṇḍu`, `pa'ndu`, `पाण्डु`, `පාණ්ඩු`.
   - It never equates different words: *anaemia* is not listed under Pandu.
   - Matches must start at a word boundary.
   - Compounds and inflected forms (`पाण्डुरोगे`, `Vātaja`) match only for
     concepts marked `allow_compound`, and are noted.
   - The seed lexicon is **unreviewed** and needs checking by an Ayurveda
     expert.
2. **Cue rules.** A candidate is created only when two concepts of
   compatible types (`CANDIDATE_PREDICATES`) appear in the same sentence or
   verse, **and** a cue phrase for that predicate appears near them.
   - Cues include "indicated in", "symptoms", "लक्षण", "contraindicated",
     "composed of" and "vitiated".
   - The subject must be within 80 characters of the cue.
   - Co-occurrence alone is stored only as a mention, in
     `mentions/<source>.jsonl`.
3. **Sentence-structure check (extractor v3).**
   - Implemented in `app/knowledge_candidates/structure.py`. The sentence
     is split into list items at commas and semicolons, ignoring those
     inside parentheses.
   - A relation counts as stated only when:
     - the sentence is a single clause, or
     - the cue and both concepts share one list item, or
     - the cue sits in the subject's item and governs the enumeration
       ("Triphala was composed of A, B, and C").

     In that last case the object may be further than 80 characters away.
   - Otherwise the pair is only listed together. The candidate is still
     produced, so a reviewer sees it, but it is flagged
     `relation_not_supported_by_sentence_structure`.
   - That flag **blocks approval**, excludes the candidate from
     `trusted_candidates()`, makes promotion skip it, and makes `retract`
     list it if it was approved earlier.
   - The check is deliberately conservative. A real relation phrased with
     the cue next to the object ("Useful in pandu: triphala, punarnava") is
     flagged too. It is never dropped.
4. **Uncertainty notes.** These are attached, never interpreted:
   - `negation_cue_in_sentence`
   - `dosage_statement_in_sentence`: dosage text is reproduced from the
     source only. It is never a recommendation.
   - `period_or_proportion_qualifier` (extractor v4): the sentence limits the
     statement to a historical period or to stated proportions. Examples:
     "during the period of …", "… century", "two parts of …", "equal
     parts", "in the ratio …".
     - This note does not block approval, but like every note it means the
       reviewer must add a note when approving.
     - Promoted claims carry `qualified_statement: true`, and the evidence
       text keeps the qualifying sentence verbatim.
   - `ambiguous_term`, for example *kamala* (also lotus) or *rakta*
   - `matched_inside_compound_word`
   - `list_context`: sentences with five or more commas
   - `source_text_quality_flagged`
   - `evidence_category_not_declared`

The extractor sits behind a `CandidateExtractor` protocol, so a local model
could be added later. None is called by default, and nothing is sent to an
external service.

### Evidence category

Declare it per source in the metadata sidecar with `"evidence_category"`.
The values are `traditional_text`, `modern_clinical_research`,
`systematic_review`, `practitioner_interpretation` or `other`.

It is never inferred. A traditional text is not recorded as clinical
evidence.

### Review states and rules

States: `candidate`, `uncertain`, `needs_more_sources`, `approved`,
`rejected`, `superseded`.

- **Reviewer:** every decision needs a named reviewer and a role
  (`practitioner` or `researcher`). It is appended to the candidate's
  history and to `review_log.jsonl`. Nothing is deleted, and a rejected
  candidate keeps its passage.
- **Notes:** every decision other than approval needs a note. Approving a
  candidate that has uncertainty notes also needs one.
- **Restricted transitions:**
  - A rejected candidate can only be reopened (to `uncertain` or
    `needs_more_sources`), not approved directly.
  - `superseded` is final and must name an existing replacement candidate.
  - An approval can be withdrawn.
- **Stale candidates:** a candidate whose passage changed is marked
  `stale`. It is kept, and it cannot be approved or trusted until it is
  re-extracted.

### Conflicts

Two kinds of conflict are detected:

- `indication_vs_caution`: the same herb or formulation and condition are
  indicated in one passage and cautioned against in another.
- `polarity`: the same relation is stated in one passage and negated in
  another.

Conflicts are linked to their candidates and **never resolved
automatically**. An open conflict blocks approval unless the reviewer
acknowledges it with `--acknowledge-conflicts` and a note. That marks it
`acknowledged`, not resolved. A new conflicting passage creates a new, open
conflict.

### From approved candidate to graph claim (for Stage E)

`to_ontology_claim()` turns an approved candidate into the existing `Claim`
model **only** when the candidate predicate maps directly to the ontology:

- `HAS_SYMPTOM(Roga, Symptom)` becomes `INDICATES(Symptom, Roga)`
- `ASSOCIATED_WITH_DOSHA` and `AFFECTS_DHATU` map one to one
- `TRADITIONALLY_INDICATED_FOR`, `HAS_CAUTION` and `CONTAINS_INGREDIENT`
  return `None`. The ontology models treatment through a
  TherapeuticPrinciple, so a reviewer must model these explicitly.

The resulting `verification_status` is:

| Situation | Status |
|---|---|
| The candidate has any conflict | `disputed` |
| A practitioner approved it | `practitioner_verified` |
| A researcher approved it | `literature_supported` (a source states it) |

The claim's confidence is `null`. Nothing is written to Neo4j yet.

### Extractor v4 cue change (2026-10-19)

The bare word *dosha* (`dosa`, `doṣa`, `दोष`) is no longer a cue for
`ASSOCIATED_WITH_DOSHA`. It occurs inside disease names (*grahani dosa*)
and in lists of actions (*kapha vata hara*), where it states no relation
between a disease and a dosha. Causal and aggravation cues remain:
"vitiated", "aggravated", "predominant", "prakopa", "due to", "caused by",
"प्रकोप".

Expected effect on the next `candidates-extract` run over the Ashtanga
Hridaya:

- The two flagged candidates whose only cue was `dosa` are no longer
  produced. These are `cand-2e8f6a071992b806689b` (Pandu–Vata) and
  `cand-bc1e197cc8e9a8e4ca09` (Pandu–Kapha).
- They become stale (`newly_stale=2`). They are kept with their review
  status and history, and are never deleted.
- Candidate IDs stay on the v2 scheme. Candidates that are still produced
  keep their IDs and history and get `extractor_version` 4.

### Structure check on the books (2026-10-19, extractor v3)

Trial re-extraction on a copy of the candidate store:

- **IDs and history:** the IDs of the 5 current candidates are unchanged.
  Candidate IDs keep the v2 scheme (`CLAIM_ID_SCHEME_VERSION`), and
  re-extraction refreshes their analysis while keeping review status,
  history and first extraction time.
- **Flagged (3):** these were list co-occurrences:
  - `Triphala TRADITIONALLY_INDICATED_FOR fatigue`: a drug-group
    catalogue (Khare, lines 10445–10449)
  - `Pandu ASSOCIATED_WITH_DOSHA Vata`: an indication list (Ashtanga
    Hridaya, lines 35572–35575)
  - `Pandu ASSOCIATED_WITH_DOSHA Kapha`: the same list
- **Supported (2):** `Triphala CONTAINS_INGREDIENT` Haritaki and Bibhitaki
  (Khare, line 10079).
- **New:** `Triphala CONTAINS_INGREDIENT Amalaki`, which the old 80-character
  window missed.

The fatigue candidate cannot be expressed accurately in the current
ontology:

- Ontology v1.1 has no Formulation→Symptom or Principle→Symptom
  relationship.
- Treatment is modelled only as Roga → `SUGGESTS_PRINCIPLE` →
  TherapeuticPrinciple → `USES_FORMULATION`/`USES_HERB`. Fatigue is a
  Symptom, which relates only to a Roga (`INDICATES`).
- The source term (*śramahara*, "alleviating fatigue") names a classical
  drug group, that is, an action category. The ontology has no concept
  type for that.
- Even with such a type, this passage does not tie Triphala to the group.

Representing it would need an ontology decision, such as an action or
drug-group concept, plus a passage that states the attribution. No mapping
is invented.

### First run on the books (2026-10-19)

**Setup:**
- Corpus: 18 `ayurveda_books/` sources, 28,128 chunks.
- Lexicon: seed-2 (21 concepts).
- Extractor: v2.

**Results:** 5,992 mentions, but only **5 current candidates**.

- Correct: 2 (`Triphala CONTAINS_INGREDIENT Haritaki` and `Bibhitaki`, from
  Sushruta 38:56 as quoted in a modern book).
- Questionable: 3. Two come from indication lists and carry
  `list_context`. One "curative of fatigue" sentence is ambiguous.

Recall is low because:
- the key classical texts (Charaka, Madhava Nidana) are scans with no text
  yet;
- the seed lexicon is tiny;
- older translations use other spellings.

This shows the pipeline is traceable end to end. It is **not** a usable
knowledge yield yet.

## Data operations (quick reference)

Run from `component2/` with the project venv. No command below writes to
Neo4j unless it says `--apply` and is marked **WRITE**. Output is counts
and identifiers, never passage text, except `search`.

| Task | Command |
|---|---|
| List registered sources | `python -m app.knowledge_ingestion sources corpus/source_registry.csv [--decision include]` |
| Validate the registry | `python -m app.knowledge_ingestion sources-validate corpus/source_registry.csv` |
| Plan downloads (dry run) | `python -m app.knowledge_ingestion acquire corpus/source_registry.csv --raw corpus/raw` |
| Download included sources (network; needs approval) | `... acquire corpus/source_registry.csv --raw corpus/raw --apply [--id N-001]` |
| Validate / inspect one source file | `python -m app.knowledge_ingestion inspect corpus/raw/<file> [--json]` |
| Dry-run extraction of one file | `python -m app.knowledge_ingestion extract corpus/raw/<file> --out <scratch dir> --root corpus/raw` |
| Extract everything and write the manifest | `python -m app.knowledge_ingestion manifest corpus/raw --out corpus/extracted/manifest.json --extract-dir corpus/extracted` |
| Add new sources without re-extracting the corpus | `python -m app.knowledge_ingestion manifest-update corpus/extracted/manifest.json --root corpus/raw --path-prefix classical_open/ --extract-dir corpus/extracted` (keeps a timestamped backup of the old manifest) |
| Chunk and validate chunks | `... chunk corpus/extracted` then `... validate corpus/extracted` |
| Ingestion report | `python -m app.knowledge_ingestion ingest-report corpus/extracted/manifest.json --extracted corpus/extracted --candidates corpus/extracted/candidates [--out report.json]` |
| Generate embeddings (separate store per model) | `... embed corpus/extracted --store corpus/extracted/embeddings [--path-filter P ...] [--exclude-source ID ...]` (filters are repeatable; any match is included) |
| Read-only retrieval | `... search "pāṇḍuroga lakṣaṇa" --store corpus/extracted/embeddings --top-k 5` |
| Retrieval evaluation | `... search-eval <cases.jsonl> --store ...`; `... search-pool ... [--model ID ...]` or, to compare corpora with one model, `--system baseline=STORE --system extended=STORE`; `... review-eval <pool> <reviewed copies>` |
| Candidate extraction and review | `... candidates-extract ... [--path-filter P ...] [--exclude-source ID ...]`; `... review ... --reviewer NAME --role practitioner --note ...` |
| Reviewer-modelled treatment claims | `... model-claim corpus/extracted/candidates --extracted corpus/extracted --chunk-id ID --quote "exact text" --subject Roga:R-PANDU:Pandu --predicate SUGGESTS_PRINCIPLE --object TherapeuticPrinciple:TP-…:Label --statement … --reviewer NAME --role practitioner --note …`; `... modelled ...`; `... withdraw-modelled ...` |
| Promotion plan (dry run) | `... promote corpus/extracted/candidates --extracted corpus/extracted` |
| **WRITE** schema / promotion / retraction | `... source-schema --apply`, `... promote ... --apply`, `... retract ... --apply`. Each needs explicit authorization first. |
| Validate the graph (read-only) | `python -m app.db.graph_validation [--json]` |
| Service diagnostics (read-only) | `GET /health`, `GET /health/neo4j`, `GET /health/readiness`, `GET /health/graph-validation` |
| Tests (offline, no live DB) | `python -m pytest -q` |
| C1 sample payloads | `python -m app.integration.c1_reference_samples …` (see `docs/c1_integration_testing.md`) |

Where to look next:

- the source registry, licences and the acquisition decision:
  `docs/dataset_discovery.md`
- graph identity and the validation rules: `docs/knowledge_graph_schema.md`

## How to use it

Install the dependency into the project venv once:

```bash
cd component2
.venv/Scripts/python -m pip install pypdf==6.18.0
```

Keep the books in `corpus/raw/` and outputs in `corpus/extracted/`. Both are
git-ignored. Then run the commands from `component2/`.

1. Summarize one file. This prints metadata and counts, never passage text:

   ```bash
   python -m app.knowledge_ingestion inspect corpus/raw/book.pdf
   python -m app.knowledge_ingestion inspect corpus/raw/book.pdf --json
   ```

2. Extract one file into `<source_id>.extraction.json` and
   `<source_id>.passages.jsonl`:

   ```bash
   python -m app.knowledge_ingestion extract corpus/raw/ayurveda_books/book.pdf --out corpus/extracted --root corpus/raw
   ```

   **Use `--root` when re-extracting a corpus file.**
   - With `--root`, the source is recorded by its path relative to the
     root, with `/` separators (`ayurveda_books/book.pdf`). That is exactly
     what `manifest` records, so `--path-filter ayurveda_books/` keeps
     matching it.
   - A file outside the root is rejected, with no fallback to the file name.
   - Without `--root`, only the file name is recorded. That is the earlier
     behaviour, kept for compatibility, and path filters based on folders
     will then miss the source.

3. Process a whole directory and write a manifest. This also writes the
   passages:

   ```bash
   python -m app.knowledge_ingestion manifest corpus/raw --out corpus/extracted/manifest.json --extract-dir corpus/extracted
   ```

4. Show statuses from a manifest. The exit code is 1 while any source is not
   fully `extracted`:

   ```bash
   python -m app.knowledge_ingestion status corpus/extracted/manifest.json
   ```

5. Find identical files. This only hashes the files, so it is fast:

   ```bash
   python -m app.knowledge_ingestion duplicates corpus/raw
   ```

6. Chunk the extraction output into `<source_id>.chunks.jsonl`. This works
   on one `*.extraction.json` file or a whole directory, and never
   re-reads the books:

   ```bash
   python -m app.knowledge_ingestion chunk corpus/extracted [--verbose]
   ```

7. Validate the chunks. The exit code is 1 if any source has problems:

   ```bash
   python -m app.knowledge_ingestion validate corpus/extracted
   ```

8. Embed the chunks with the model set in `C2_EMBEDDING_MODEL`. Runs are
   incremental, and `--path-filter` restricts the run to some sources:

   ```bash
   python -m app.knowledge_ingestion embed corpus/extracted --store corpus/extracted/embeddings [--path-filter ayurveda_books/] [--allow-download] [--rebuild]
   ```

9. Search the store, or evaluate it against labelled cases:

   ```bash
   python -m app.knowledge_ingestion search "pandu roga lakshana" --store corpus/extracted/embeddings --top-k 5 [--script Deva] [--max-per-source 1]
   python -m app.knowledge_ingestion search-eval cases.jsonl --store corpus/extracted/embeddings
   ```

   `--store` is the **store root**, not a model folder. The configured
   model's store is looked up as `<store root>/<model slug>`, for example
   `corpus/extracted/embeddings/intfloat__multilingual-e5-small`. If no
   store is found, the error names the full path it checked. It also says
   whether the root is missing, whether a model folder was passed instead
   of the root, and which model stores do exist under the root.

10. Extract candidate claims (offline). Re-running keeps review decisions:

    ```bash
    python -m app.knowledge_ingestion candidates-extract corpus/extracted --out corpus/extracted/candidates [--path-filter ayurveda_books/] [--lexicon my_lexicon.json]
    ```

    The command reports these counters (from `run_extraction` in
    `app/knowledge_candidates/store.py`):

    | Counter | Meaning |
    |---|---|
    | `new` | Produced for the first time |
    | `kept_with_review_state` | Produced again. Review status, history and first extraction time are kept. |
    | `refreshed_analysis` | Produced again, with a changed analysis field: subject, predicate, object, cue, passage, evidence category, extraction method or version, lexicon version, confidence, or uncertainty notes |
    | `revived` | Was stale and was produced again |
    | `newly_stale` | Was current, and was not produced again for a processed source |
    | `still_stale` | Was already stale and is still not produced |

    Sources excluded by `--path-filter` are not processed, and their
    candidates are left unchanged and uncounted. The filter is matched
    against each source's recorded `relative_path`.

11. Preview, review, and check conflicts. Nothing is written to Neo4j:

    ```bash
    python -m app.knowledge_ingestion candidates corpus/extracted/candidates --status candidate --show-sentence [--concept R-PANDU]
    python -m app.knowledge_ingestion review corpus/extracted/candidates CLAIM_ID --status approved --reviewer NAME --role practitioner --note "Checked against the printed text."
    python -m app.knowledge_ingestion conflicts corpus/extracted/candidates --open-only
    ```

12. Promote approved candidates to Neo4j. This is a **dry run** by default
    and writes only with `--apply`. Promotion needs approved candidates and
    a source sidecar with `title` and `evidence_category`. Skipped
    candidates are listed with reasons:

    ```bash
    python -m app.knowledge_ingestion source-schema            # show the 7 additive statements
    python -m app.knowledge_ingestion promote corpus/extracted/candidates --extracted corpus/extracted
    python -m app.knowledge_ingestion retract corpus/extracted/candidates   # withdrawn approvals; relabels only
    ```

    Promotion also requires the approval to be present in
    `review_log.jsonl`. It skips sources that the manifest lists under
    `source_id_conflicts`. Descriptive claims (`CONTAINS_INGREDIENT`) are
    written with `:DescriptiveEvidence`, so the API evidence index never
    loads them.

### Re-running and recovering from failures

- Extraction is idempotent. Re-running replaces the output files for the
  same `source_id`, and passage content and order are deterministic.
- A failure in one file never stops a directory run. The file's status and
  error appear in the manifest. Fix or convert the file (for example, OCR
  it or re-save it as UTF-8), then run `manifest` again.
- Output files contain source-book text. Do not commit or publish them.

## Configuration

These environment variables can be set in `component2/.env`:

| Variable | Default | Purpose |
|---|---|---|
| `C2_INGEST_MAX_FILE_BYTES` | 536870912 (512 MB) | Reject larger files |
| `C2_INGEST_MAX_ARCHIVE_MEMBER_BYTES` | 67108864 (64 MB) | Limit any single DOCX/EPUB member, as a zip-bomb guard |
| `C2_INGEST_MIN_PAGE_TEXT_CHARS` | 20 | Below this many visible characters, a PDF page has no usable text layer |
| `C2_INGEST_MAX_SUSPECT_CHAR_RATIO` | 0.05 | Threshold for `suspect_characters` |
| `C2_INGEST_CHUNK_MAX_CHARS` | 800 | Maximum normalized characters per chunk (same default as `C2_CHUNK_MAX_CHARS`) |
| `C2_INGEST_CHUNK_OVERLAP_CHARS` | 100 | Maximum overlap, made of whole units; must be smaller than the maximum |
| `C2_EMBEDDING_MODEL`, `C2_EMBEDDING_BATCH_SIZE`, `C2_EMBEDDING_DEVICE`, `C2_EMBEDDING_CACHE_DIR` | see implementation notes §4 | Shared with the evidence index |
| `C2_SOURCE_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Model for the source-chunk store (not the evidence index) |
| `C2_SOURCE_EMBEDDING_QUERY_PREFIX`, `C2_SOURCE_EMBEDDING_PASSAGE_PREFIX` | `query: ` / `passage: ` for e5 models, otherwise empty | Role prefixes for the source-chunk store |
| `C2_SOURCE_RETRIEVAL_MIN_SIMILARITY` | 0.0 | Similarity threshold for source-chunk search (not calibrated) |

These are engineering safeguards and have not been calibrated on real books.

## Resources

- Everything in Stages A and B runs locally on the CPU and needs no network access.
- Books are processed one at a time. Only one book's passages are held in
  memory at once, so a few MB of text per book is fine on a 4 GB VPS.
- Stage C runs locally too. The only network access is downloading a
  model, which needs `--allow-download`.
- Measured here: `all-MiniLM-L6-v2` embedded 2,201 chunks in 103 s on CPU,
  about 21 chunks/s. The full corpus of 82,862 chunks would take about
  65 minutes. Larger models are several times slower.
- Vector storage for 82,862 chunks: about 127 MB at 384 dimensions, 255 MB
  at 768, and 340 MB at 1024.
- `pypdf` is pure Python (a wheel of about 400 kB) with no system
  dependencies. AES-encrypted PDFs would also need the `cryptography`
  package, which is not installed. Such files fail with a clear error.

## Tests

```bash
cd component2
.venv/Scripts/python -m pytest -q test_knowledge_extraction.py test_knowledge_manifest.py test_knowledge_chunking.py test_source_chunk_embeddings.py test_knowledge_candidates.py test_stage_e_promotion.py test_knowledge_tei.py test_source_registry.py test_dataset_to_api.py test_graph_health.py
```

- `test_knowledge_tei.py`: the TEI and JATS readers, verse IDs, editorial
  notes, chunk citation references.
- `test_source_registry.py`:
  - the committed registry validates
  - acquisition with a fake HTTP opener: dry run, checksum verification,
    resume, no overwrite, sidecar creation
  - the ingestion report
- `test_dataset_to_api.py`: the end-to-end path.
  1. registry
  2. download (fake opener)
  3. TEI extraction, chunking and validation
  4. candidate extraction
  5. practitioner approval
  6. promotion plan and write transaction (recording fake driver)
  7. reasoning API

  It also covers abstention, missing metadata and graph outage.
- `test_graph_health.py`: connectivity classification, URI encryption,
  readiness, and the read-only validator (fake driver; asserts no write
  queries).

- The tests build synthetic PDF, DOCX, EPUB, TXT and Markdown files in
  temporary directories (`ingestion_test_support.py`).
- No real books, network access or Neo4j connection are needed.
  `test_neo4j_connection.py`, `test_neo4j_schema.py`,
  `test_neo4j_repository.py` and `test_neo4j_pipeline.py` are manual
  scripts for the live database. They contain no pytest tests, and they
  connect only when run directly with `python <file>`.
- The Unicode tests use short synthetic Sinhala, Devanagari and IAST
  phrases.
- The PDF fixtures use the standard Helvetica font, so Unicode PDF text
  extraction is **not** covered by tests. It depends on each PDF's font
  mappings and must be checked on real files.

## Known limitations

- No OCR. Scanned books are only flagged for it.
- Unicode extraction from PDFs depends on each file's ToUnicode font maps.
  Many Indic-script PDFs produce broken text; check the output.
- Legacy-font Sinhala text cannot be detected automatically.
- PDF text can contain typographic ligatures (`ﬁ`, `ﬂ`) and detached
  accents (for example `Pe˜na` for `Peña`). These are kept in the original
  text. The normalized copy expands ligatures. Detached accents are only
  flagged (`detached_diacritics`), not repaired.
- pypdf parser warnings (for example, that `fontTools` is needed for some
  CFF fonts) are recorded as extraction warnings. `fontTools` is not
  installed, so such fonts may map some characters incorrectly.
- Language is not detected, only scripts. Chunk language comes from curated
  metadata, so sources without a sidecar have `null` languages.
- Verse numbers are read only from danda markers. Chapter and sthana
  context, and citation styles such as `Ci. 3, 113cd`, are not parsed.
- Line-end hyphenation (`activ-` + `ity`) is not joined, because a hyphen at
  a line end can be genuine (`cow-urine`).
- OCR noise already present in TXT books (for example the existing
  Sushruta Samhita and Hindi texts) is kept as is. Only letter-spacing is
  flagged.
- Sentence segmentation is punctuation-based. It has not been evaluated on
  real Sinhala or Sanskrit prose.
- The source-chunk store uses `multilingual-e5-small`. It was evaluated
  only on 12 weakly labelled cases, and cross-lingual queries (Devanagari or
  Sinhala queries against English text) mostly failed. No retrieval-quality
  claim is made for Sinhala, Sanskrit or Hindi.
- Candidate extraction is rule-based. Precision on the first real run was
  2 of 5. Extractor v3 now flags the 3 misreadings as structurally
  unsupported. Recall is very low, and the structure check is heuristic:
  sentence and list splitting is punctuation-based and has not been
  evaluated on Sanskrit or Sinhala verse. It depends on an unreviewed seed lexicon
  and on English, IAST or Devanagari cue phrases. There are no Sinhala cue
  phrases yet.
- The corpus is about 99% Latin-script chunks, with only 2 Sinhala chunks.
  Sinhala retrieval cannot be meaningful until Sinhala sources are added.
- Source chunks are not yet in Neo4j. Choosing between an AuraDB vector
  index and the local store is a Stage E decision.
- DOCX headers, footers, footnotes and comments are not extracted.
- EPUB page-list (print page) mapping is not used.

## Copyright and provenance

- Source books may be under copyright. Keep them, and every extracted output,
  outside version control and off public servers.
- Record usage restrictions in `usage_notes`.
- Extraction never contacts an external service.
- Extracted passages are raw content. They become evidence only after
  curation and review, through the existing evidence ingestion path or the
  later review stages.
