# Dataset Discovery and Corpus Audit (2026-10-19)

This report records what the Component 2 corpus contains today, which
additional sources were researched, and why each one is included,
deferred or excluded. The machine-readable version is
[`corpus/source_registry.csv`](../corpus/source_registry.csv). It has one row
per source, with the licence, permitted uses, checksum and decision.

Two rules apply throughout:

- Licences and contents were checked on the **source page or API itself** on
  2026-10-19. The `licence_evidence` column says where each one was read.
  Search-engine summaries were used only to find pages, never as proof.
- **Downloads happened only after approval.** Nothing was downloaded
  while this report was being prepared. The 12 included files were
  acquired later, on 2026-10-19, with approval (see §6).

## 1. Audit of the existing corpus

Counts come from `python -m app.knowledge_ingestion ingest-report`, the live
read-only graph validator, and the existing evaluation files.

| Item | Finding |
|---|---|
| Files | 2,175 sources: 21 books in `ayurveda_books/` and 2,154 web pages in `ayurveda_texts/` |
| Extraction | 2,148 `extracted`, 24 `partial_extraction`, 3 `needs_ocr_or_review` |
| Scanned, no text | P. V. Sharma *Charaka Samhita* (916 pages), Meulenbeld *Madhava Nidana* (729 pages), `heart_diseases.pdf` (30 pages) |
| Duplicates | 136 identical-content groups, 180 redundant files (all web pages) |
| Curated metadata | 1 of 2,175 sources has a `.meta.json` sidecar. None has a declared licence or evidence category apart from that one. |
| Chunks / embeddings | 28,128 chunks of 18 books embedded with MiniLM and `multilingual-e5-small`. The web pages are not embedded. |
| Scripts | 27,161 Latin-script chunks, 967 Devanagari (all from one Hindi public-health book), **0 Sinhala** |
| Pandu term | 0 chunks with Devanagari पाण्डु/पांडु, 0 with IAST *pāṇḍu*, 24 with ASCII `pandu` |
| Candidates | 13 rule-extracted candidate claims (9 stale), **0 approved** |
| Neo4j AuraDB | Neo4j 5.27-aura. 11 core uniqueness constraints. **0 nodes, 0 relationships.** Stage E provenance schema not applied. |
| Human-reviewed eval | Round 1 (209 pooled rows) approved by the project owner. AI-drafted labels are kept separately as drafts. |

### Licence and provenance problems found

1. **Seven books are Z-Library copies** (registry rows EX-004 to EX-006,
   EX-010, EX-011, EX-014, EX-017, EX-021). Z-Library is not an authorized
   distributor, so the project has no verified right to hold these copies.
   Rows that matter to the research are marked `quarantine_recommended`, and
   off-topic ones are marked `exclude`. Nothing was moved or deleted. Moving
   the files is your decision.
   - One of these books is the source of the only structurally supported
     candidates: Khare, *Evidence-Based Ayurveda* (Triphala ingredients).
   - Another, the Lippincott nursing textbook, supplies 301 of the 440
     lexical "Pandu" smoke labels. It distorts the evaluation as well as
     being an unlicensed copy.
2. **The modern editions are copyrighted.** P. V. Sharma (Chaukhambha) and
   Meulenbeld (Brill) are in copyright. If the copies are held lawfully,
   local OCR for private research is the most that is defensible. Their
   text must never be uploaded to AuraDB or redistributed.
3. **The web-scraped pages remain under each site's copyright.** Most of
   them are commercial health pages. They are useful as discovery leads, not
   as evidence.
4. **Most book editions are unidentified.** `Ashtank_Hirdaya.txt`,
   `Sushruta_Samhita.txt`, `Parada_vigyanam.txt` and others have no
   translator, edition or rights information.

### Does the corpus support the Pandu research questions?

Not yet, for four reasons:

- **The key classical sources are missing or unreadable.** Charaka
  Cikitsāsthāna 16 (*pāṇḍurogacikitsita*) and Mādhavanidāna ch. 8 exist only
  as scans without text.
- **No same-script targets exist.** The Devanagari, IAST and Sinhala Pandu
  queries can only be answered cross-lingually, which both models mostly
  fail (see `docs/knowledge_ingestion.md`, smoke comparison).
- **Modern evidence is incidental.** No open-access study of Pandu or
  iron-deficiency anaemia in Ayurveda is in the corpus.
- **No reviewed knowledge has reached the graph.** Every reasoning request
  therefore abstains, which is the correct behaviour.

## 2. Discovery avenues searched

| Avenue | Result |
|---|---|
| SARIT (TEI editions on GitHub) | **Caraka, Suśruta, Aṣṭāṅgahṛdaya** in IAST, CC BY-SA 3.0, with verse IDs |
| Internet Archive metadata API | Public-domain English Charaka (Kaviratna) and Suśruta (Bhishagratna) with OCR text and checksums. Many uploads of modern editions carry an uploader-added CC0 mark that does not establish rights. |
| Europe PMC REST API | 150 open-access hits for `(pandu OR "pandu roga") AND ayurveda`. Three relevant articles with explicit CC licences were selected. |
| WHO IRIS / publications | Ayurveda terminology (2022) and haemoglobin cutoff guideline (2024), both CC BY-NC-SA 3.0 IGO |
| NLM MeSH | Free with attribution, for modern-term mapping |
| ICD-11 TM2 | CC BY-ND 3.0 IGO: codes may be cited, derived mappings need WHO permission |
| GRETIL | "For scholarly purposes only", per file. SARIT supersedes it here. |
| carakasamhitaonline.com | CC BY-NC-SA 4.0, but prior permission is required. Excluded until permission is obtained. |
| NAMASTE (Ministry of Ayush) | Host did not resolve on 2026-10-19. Deferred. |
| Cologne Sanskrit dictionaries | No licence statement on the home page. Deferred. |
| Sinhala sources | No openly licensed Sinhala Pandu text was found. Only print holdings appear in library catalogues. |
| TKDL | Access restricted. Excluded; access controls are never bypassed. |

## 3. Selected sources and why

| ID | Source | Licence | Why it is appropriate |
|---|---|---|---|
| N-001 | SARIT *Carakasaṃhitā* (TEI, commit `1b819c4`) | CC BY-SA 3.0 | Root text of the classical source named first in the proposal (Table 3). Includes Ci. 16 Pandu. IAST fills the 0-chunk *pāṇḍu* gap. Verse IDs (`Ca.6.16.n`) give exact citations. |
| N-002 | SARIT *Aṣṭāṅgahṛdayasaṃhitā* (commit `debcc08`) | CC BY-SA 3.0 | Named in the proposal. Ni. 13 and Ci. 16 cover Pandu. A scholarly transcription (Das & Emmerick). |
| N-003 | SARIT *Suśrutasaṃhitā* (commit `6eadd5e`) | CC BY-SA 3.0 | Uttaratantra 44 (*pāṇḍurogapratiṣedha*) |
| N-004 | Kaviratna, *Charaka-Samhita* English translation (1890–1908, BIU Santé) | Etalab Licence Ouverte | The only openly licensed complete English Charaka. Pairs with N-001 for cross-lingual retrieval. |
| N-005a–c | Bhishagratna, *Sushruta Samhita* English translation (1907–1916, U. Toronto) | Public domain | An identified public-domain edition. May replace the unidentified EX-018 after a duplicate check. |
| N-012 | WHO *International Standard Terminologies on Ayurveda* (2022) | CC BY-NC-SA 3.0 IGO | Authoritative Devanagari and IAST terms with definitions, for **human** lexicon review. Reference only. |
| N-017 | Davkare et al. 2025, *Management of Pandu (IDA) through Ayurveda* (PMC12991589) | CC BY-NC-SA | Directly on topic. The curator confirms the article type. |
| N-018 | Nair et al. 2026, *Punarnavayolepa Choornam in IDA* (PMC13227311) | CC BY | Formulation study. Preclinical findings must not be read as clinical efficacy. |
| N-019 | Joshi et al. 2025, *GRAYU* (PMC12872832) | CC BY | Related-work and schema reference. Reference only. |
| N-021 | WHO haemoglobin cutoff guideline (2024) | CC BY-NC-SA 3.0 IGO | Documents the C1 screening thresholds. Background only, never C2 graph evidence. |

**Inclusion criteria applied:**

- an explicit licence, read on the source itself
- a lawful public access route
- direct relevance to Pandu, its symptoms, doshas or dhatus, formulations
  or terminology
- an identifiable edition or version
- a format the pipeline can read, or a new reader justified by the data

**Exclusion criteria applied:**

- unverifiable rights, including uploader-asserted CC0 marks on modern
  editions
- permission requirements that have not been met
- access restrictions
- off-topic content
- an unauthorized copy

## 4. Gaps that remain

- **Sinhala.** No lawful open source was found. A practitioner-supplied or
  permission-cleared text is needed, and Sinhala retrieval quality cannot be
  claimed until one exists.
- **Mādhavanidāna and Bhāvaprakāśa.** Old Devanagari editions exist (N-006,
  N-007), but rights or OCR quality are unverified.
- **Standard Treatment Guidelines and the Pharmacopoeia.** No official
  ministry URL was verified. A third-party mirror was found and not used.
- **NAMASTE terminology.** It was unreachable. Retry access and read its
  terms first.
- **Modern clinical evidence.** Only three articles are registered. A
  systematic screen of the 150 Europe PMC hits is future work, with one
  registry row per accepted article.

## 5. What the new sources change, and how it will be measured

The retrieval failure analysis found two separate causes for the failed
IAST and Devanagari Pandu queries: **corpus gaps** and **cross-lingual
model weakness**. The SARIT texts address only the first. Their effect must
be measured, not assumed.

Planned controlled experiment. It is not run yet, because the sources are
not acquired.

1. Keep the existing stores and the approved round-1 labels unchanged.
2. Build the SARIT and Kaviratna chunks into a **separate** store root,
   for example `corpus/extracted/embeddings_exp_sarit/`. Use the same model
   (`multilingual-e5-small`), the same prefixes and the same chunker
   version, so that only the corpus differs.
3. Run `search-pool` with the same 12 smoke cases into a new pool file.
   Have it human-reviewed as round 2. The approved round-1 files are never
   edited.
4. Compare the IAST and Devanagari cases with `review-eval`. Report per
   script, and keep the cross-lingual cases separate from the same-script
   cases.
5. Only if same-script retrieval still fails, evaluate a different model or
   transliteration-aware query expansion as a separate experiment.

## How to acquire the included sources

Acquisition needs your approval because it downloads 12 files, about 24 MB,
from four hosts:

- raw.githubusercontent.com (SARIT, 3 files)
- archive.org (Kaviratna and Bhishagratna OCR text, 4 files)
- www.ebi.ac.uk (Europe PMC full text, 3 files)
- iris.who.int (WHO PDFs, 2 files)

The command checks every file against the registry checksum before using
it, and never overwrites a local file.

```bash
python -m app.knowledge_ingestion sources-validate corpus/source_registry.csv
python -m app.knowledge_ingestion acquire corpus/source_registry.csv --raw corpus/raw            # dry run
python -m app.knowledge_ingestion acquire corpus/source_registry.csv --raw corpus/raw --apply    # downloads
```

Downloaded files and their extracted text stay in the git-ignored
`corpus/raw/` and `corpus/extracted/` folders. The CC BY-SA, CC BY-NC-SA and
Etalab licences permit redistribution with attribution. The project still
keeps derived chunks local by default (Stage E decision D1).

## 6. Acquisition result (2026-10-19, approved)

**Download.**

- `acquire --apply` downloaded all 12 files, with 0 errors.
- 7 files matched the checksums recorded in advance (git blob SHA-1 or
  MD5).
- The other 5 had no published checksum. Their SHA-256 was recorded in
  the registry after download.
- Each file was checked to be the format it claims (PDF or JATS/TEI XML).

**Extraction.**

- The new files were extracted with `manifest-update`. That command
  processes only the new paths, so the existing 2,175 records were not
  re-extracted.
- The previous manifest is kept as `manifest.before-update-*.json`.
- **No Neo4j writes.** Nothing was embedded or promoted.

| Source | Chunks | With verse refs | Chunks with *pāṇḍu* (IAST) | Notes |
|---|---|---|---|---|
| SARIT Carakasaṃhitā | 1,901 | 1,839 | 124 | Ci. 16 present as 21 chunks citing `Ca.6.16.n` |
| SARIT Aṣṭāṅgahṛdaya | 1,219 | 1,213 | 104 | 1,094 chunks flagged `editorial_notes_omitted` (its variant readings) |
| SARIT Suśrutasaṃhitā | 1,615 | 1,608 | 105 | |
| Kaviratna Charaka (English) | 6,466 | 0 | 0 (11 ASCII `pandu`, 51 "anaemia") | OCR text |
| Bhishagratna Suśruta v1/v2/v3 | 1,477 / 2,201 / 1,348 | 0 | 0 (22 ASCII `pandu` in total) | |
| Europe PMC (3 articles) | 155 | 47 (JATS ids) | 0 (12 ASCII `pandu`) | |
| WHO Ayurveda terminologies | 1,645 | 0 | 19 | **Devanagari is garbled by the PDF font mapping.** Use its IAST and English only. |
| WHO haemoglobin cutoffs | 349 | 0 | 0 | Reference only |

**Chunk validation:** 0 problems in all 12 sources.

**Corpus totals.**

- Sources went from 2,175 to 2,187.
- Sources with curated metadata and a licence went from 1 to 13.
- IAST *pāṇḍu* chunks went from 0 to 352.

**Findings.**

1. *EX-018 is a duplicate.* The unidentified `Sushruta_Samhita.txt` has
   the same text as Bhishagratna item `englishtranslati00susruoft`
   (N-005b): 100% 5-gram overlap in both directions. EX-018 is now
   `exclude`, to avoid duplicate retrieval hits. The file is kept.
2. *Garbling can be invisible.* PDF text extraction can produce
   valid-looking but wrong Devanagari (`पाण्ुिोगः` for पाण्डुरोगः). This
   kind of garbling is not caught by `suspect_characters` or
   `symbol_noise`.
3. *Devanagari and Sinhala are still missing.* The new sources add no
   correct Devanagari *pāṇḍu* and no Sinhala text. Devanagari and Sinhala
   queries can therefore still only be judged cross-lingually.

**Next steps (not run).**

- Embed the new sources into a separate experimental store and run the
  controlled comparison in §5.
- Extract candidates from the new chunks with the reviewed lexicon. The
  seed lexicon already lists `pāṇḍu` and `pāṇḍuroga`.

## 7. Round-2 corpus experiment (2026-10-20)

This is the controlled comparison planned in §5. The two systems use the
same model (`multilingual-e5-small`), the same prefixes, the same chunker
and the same 12 smoke queries. **Only the corpus differs.**

| System | Store root | Corpus |
|---|---|---|
| `baseline` | `corpus/extracted/embeddings/` (unchanged) | 18 books, 28,128 chunks |
| `open_sources` | `corpus/extracted/embeddings_exp_open/` | The baseline plus 3 SARIT texts, Kaviratna, Bhishagratna v1 and v3, and two Europe PMC articles: 26 sources, 42,215 chunks |

Bhishagratna v2 is excluded because it duplicates EX-018, which is already
in the baseline. The reference-only sources are excluded.

**Controls held.**

- All 28,128 baseline vectors were reused unchanged.
- The `baseline` system reproduces the round-1 e5 ranks exactly, on 120 of
  120 rows.

### Defect found and fixed during the experiment

**Symptom.** The first pool showed the IAST query *pāṇḍu roga cikitsā*
ranking eight **heading-only chunks** first, for example "Part 4
Cikitsāsthānam".

**Cause.** In TEI, a part heading followed directly by a nested chapter
`<div>` started a new chunk, because the nested division has a different
`item_id`.

**Fix.**

- The chunker now keeps a heading group with the first text of a *nested*
  division (`_same_or_nested`).
- Book corpus chunk IDs are unaffected: they have no `item_id`, and three
  sources were checked to be identical.
- The six XML sources were re-chunked. 29 heading-only chunks were removed,
  and 43 chunks were re-embedded.
- `CHUNKER_VERSION` was **not** bumped. Bumping it would have changed every
  chunk ID in the corpus and invalidated the round-1 labels. Only TEI and
  JATS output changed, and those sources had no labels, approvals or
  promotions yet. Chunk IDs still hash the exact spans, so changed chunks
  received new IDs anyway.

### Results

**Human labels.** The approved round-1 labels were carried forward
unchanged, under their original reviewer, into
`eval/pool_round2_corpus_review.csv`:

- 120 of 152 pooled rows are judged
- **32 rows are new passages that still need human review**

With those labels, 5 cases are scored under the strict policy and 6 under
the lenient policy. On them the two systems are identical:

| Policy | System | Hit@1 | MRR@10 |
|---|---|---|---|
| strict | both | 0.20 | 0.50 |
| lenient | both | 1.00 | 1.00 |

That is expected, because the new sources do not cover those topics. Every
Pandu case, plus jaundice, Triphala and the Sinhala diabetes case, is
**undetermined** until the 32 rows are reviewed. Reports:
`eval/review_report_round2_partial_{strict,lenient}.json`.

**Label-free diagnostics** (`eval/round2_label_free_diagnostics.json`). Term
presence is not relevance:

| Case | Top-10 hits from new sources | Pandu-term hits (baseline → open) | First Pandu-term rank | Unreviewed |
|---|---|---|---|---|
| `iast-pandu` (*pāṇḍu roga cikitsā*) | 10 | 0 → 5 | none → 2 | 10 |
| `deva-pandu` | 6 | 0 → 6 | none → 1 | 6 |
| `sinh-pandu` | 3 | 0 → 2 | none → 1 | 3 |
| `en-pandu` (symptom description, no term) | 2 | 0 → 0 | n/a | 2 |

**Interpretation, provisional until review.**

- **The corpus gap was real.** The Pandu queries could only start
  retrieving Pandu passages once such passages existed.
- **The model gap remains.**
  - The IAST query still ranks 5 passages without the term in its top 10.
    Two of them are short chunks of under 80 characters, which e5-small
    tends to score highly.
  - The Devanagari and Sinhala queries now reach Pandu passages only
    *cross-lingually* (English or IAST text), because the corpus still has
    no correct Devanagari or Sinhala Pandu text.
- **Next experiment**, if review confirms these numbers: a lexical or
  transliteration-aware hybrid (exact or BM25 matching of lexicon variants
  combined with e5), and a minimum chunk length for search. Compare them on
  the same pool after review. Do not change the model first.

### What the reviewer needs to do

1. Copy `eval/pool_round2_corpus_review.csv`.
2. Fill `judgement`, `reviewer` and `review_notes` for the 32 rows whose
   `judgement` is blank. The 120 carried rows are already judged.
3. Run:

```bash
python -m app.knowledge_ingestion review-eval corpus/extracted/eval/pool_round2_corpus.csv <your copy> --policy strict --cases corpus/extracted/retrieval_cases_smoke.jsonl
```
