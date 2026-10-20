# Provisional knowledge ingestion report: `pandu-provisional-v1`

**Status: Unverified. Practitioner review pending.**

These are AI-assisted draft claims. Each one is quoted from a cited
classical text. They are not approved knowledge and not clinical evidence
of efficacy.

| Item | Value |
|---|---|
| Dataset | `knowledge/provisional/pandu_traditional_v1.json`, version 1, drafted 2026-10-20 |
| Extraction method | `ai_assisted_draft` |
| Review status | `pending_practitioner_review` |
| Live write | batch `prov-20261020T100212Z`, AuraDB (Neo4j 5.27-aura), authorized by the project owner on 2026-10-20 |
| Reports (local, not committed data) | `corpus/extracted/provisional/{dry_run_report,apply_report,verify_report,graph_validation_report,live_reasoning_sample}.json` |

## 1. What was written

| Measure | Planned (dry run) | Written | Verified in graph |
|---|---|---|---|
| Provisional claims | 50 | 50 | 50 / 50 |
| Provisional evidence | 88 | 88 | 88 / 88 |
| Concepts (all new, `concept_status: provisional`) | 47 | 47 | — |
| Sources | 7 | 7 | — |
| Source chunks | 43 | 43 | — |
| **Nodes created** | 235 | **235** | — |
| **Relationships created** | 330 | **330** | — |
| Nodes / relationships deleted | 0 | **0 / 0** | — |
| Schema statements (`IF NOT EXISTS`) | 10 | 10 | 16 constraints/indexes present |

The 10 schema statements are the 7 additive Stage E statements plus 3
provisional ones:

- `provisionalclaim_id_unique`
- `provisionalevidence_id_unique`
- `provisionalclaim_dataset`

Relationships created:

| Type | Count |
|---|---|
| PROVISIONAL_SUBJECT_OF | 50 |
| PROVISIONAL_OBJECT_OF | 50 |
| PROVISIONALLY_SUPPORTS | 98 |
| PROVISIONALLY_QUALIFIES | 1 |
| FROM_CHUNK | 88 |
| PART_OF | 43 |

Before the write the database held 0 nodes. Approved `:Claim` and
`:Evidence` counts are 0 before and after; nothing approved was created or
changed.

## 2. How correctness was checked

1. **Planner (before the write).** Each quote was located exactly once in
   its cited passage of the extracted source text, then in a current
   chunk. Results: 0 rejections, 0 duplicates.
2. **Post-write verification (`verify_plan`).** Every claim's triple,
   statement, status and links matches the plan. Every evidence item's
   text, source, chunk, source checksum, span and role matches. No
   provisional record leaked into the approved labels or relationships.
   Result: `verified`.
3. **Independent read-back (separate script, not the planner).** All 88
   stored quotes were re-read from AuraDB. Each was found verbatim in the
   on-disk extracted passages of its source. All 88
   evidence → chunk → source chains are consistent.
4. **Graph validation.** `python -m app.db.graph_validation` reported
   *valid, 0 errors, 0 warnings*, with the provisional checks included.
   Approved-pathway relationships touching provisional nodes: 0.
5. **Reasoning, live (pallor + fatigue + breathlessness, moderate tier).**
   - Approved scope: `abstain`, 0 candidates. Provisional data is
     invisible by default.
   - Research scope: `caution` with reasons `evidence:unverified_claims`
     and `knowledge:provisional_records_used`. The 19 candidates are all
     `withheld_pending_review`, and all 171 claim steps are labelled
     `provisional`. `medical_conclusion` is null.
6. **Frontend, live.** The Research knowledge page lists the 50 claims with
   their quotes and licences. The Import C1 page sends
   `knowledge_scope=approved_and_provisional` when research mode is
   selected. The analysis page shows the research-scope banner and the
   "Unverified — practitioner review pending" label on every provisional
   claim.

## 3. Sources

| Source ID | Work | Role | Evidence items |
|---|---|---|---|
| `sarit-carakasamhita` | Carakasaṃhitā, Cikitsāsthāna 16 (SARIT TEI, CC BY-SA 3.0) | primary text | 36 |
| `sarit-astangahrdaya` | Aṣṭāṅgahṛdayasaṃhitā, Nidānasthāna 13 (SARIT TEI, CC BY-SA 3.0) | primary text | 10 |
| `sarit-susrutasamhita` | Suśrutasaṃhitā, Uttaratantra 44 (SARIT TEI, CC BY-SA 3.0) | primary text | 3 |
| `kaviratna-charaka-1890` | Kaviratna, English translation of Caraka (1890, public domain) | translation | 28 |
| `epmc-pmc7509542` | Europe PMC open-access review | modern reference (diet) | 5 |
| `epmc-pmc9029079` | Europe PMC open-access review | modern reference (clinical, diet, safety) | 3 |
| `epmc-pmc5558393` | Europe PMC open-access review | modern reference (clinical, safety) | 3 |

Breakdown:

- Evidence type: 77 classical, 11 modern research.
- Script: all 88 quotes are Latin script (IAST transliteration or English).
- Modern statements are stored separately, as `evidence_role:
  modern_reference`. They do not support traditional claims.
- One modern statement qualifies one claim: iron given with milk
  (yathādoṣa / ayorajas) is qualified by modern evidence on inhibitors of
  iron absorption.
- Dose-bearing modern statements were deliberately not quoted.

## 4. Claims by category

| Category | Predicate | Claims |
|---|---|---|
| Symptom indication | INDICATES | 13 |
| Dosha association | ASSOCIATED_WITH_DOSHA | 3 |
| Dhatu effect | AFFECTS_DHATU | 2 |
| Treatment principle | SUGGESTS_PRINCIPLE | 4 |
| Diet | RECOMMENDS_DIET | 4 |
| Formulation use | USES_FORMULATION | 13 |
| Herb use | USES_HERB | 2 |
| Formulation ingredient (descriptive) | CONTAINS_INGREDIENT | 9 |

Independent primary sources per claim:

| Primary sources | Claims |
|---|---|
| 3 | 2 |
| 2 | 13 |
| 1 | 35 |

A claim with a single primary source is honest about that. It is not
padded with translations, which never count as independent support.

## 5. Known gaps (from the dataset)

- **Lifestyle.** No explicit lifestyle recommendation was found in the
  Pandu chapters read. Causes such as day sleep or suppressing urges were
  not turned into recommendations, because that would be inference.
- **Avoidances.** Dietary avoidances (for example Ca.6.16.84) cannot be
  expressed, because the ontology has no avoidance or contraindication
  predicate. Contraindications belong to Component 3.
- **Sinhala.** There is no Sinhala-language source, so no Sinhala terms are
  included.
- **Botanical names.** They are recorded only as stated in the 1890
  translation (`botanical_name_verified: false`).
- **Related conditions.** Kāmalā and Halīmaka are not modelled as separate
  Roga claims.
- **Modern evidence.** It concerns iron-deficiency anaemia, which is not
  equivalent to Pandu, and it is never used as support.

## 6. Practitioner review backlog

Each row needs a practitioner decision:

- **accept:** author it as a modelled claim (schema §9) and promote it
  through Stage E
- **amend**
- **reject**

The provisional record stays as history in every case.

"Sources" counts independent primary-text sources. "Translation" gives the
Kaviratna line range used as translation support.

#### Dhatu effect

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-be018137e3e23851bb45` | Pandu → AFFECTS_DHATU → Medas dhatu | Ah.3.13.005a, Ca.6.16.6 | — | 2 |
| 2 | `PCL-192db3148cfd9fd5d5d1` | Pandu → AFFECTS_DHATU → Rakta dhatu | Ah.3.13.005a, Ca.6.16.6, Su.6.44.3 | lines 96203-96206 | 3 |

#### Diet

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-5d978efac7490878d4b4` | Wholesome diet (pathya) after purification, in Pandu → RECOMMENDS_DIET → Meat soups of dry-land (jāṅgala) animals | Ca.6.16.42 | lines 96391-96396 | 1 |
| 2 | `PCL-e96558754fb9e9841e2d` | Wholesome diet (pathya) after purification, in Pandu → RECOMMENDS_DIET → Old śāli rice, barley and wheat with soups | Ca.6.16.41 | lines 96391-96396 | 1 |
| 3 | `PCL-31005fef7d68fd0ee184` | Wholesome diet (pathya) after purification, in Pandu → RECOMMENDS_DIET → Soups of mung bean, pigeon pea and lentil | Ca.6.16.42 | lines 96391-96396 | 1 |
| 4 | `PCL-ca5cbd7fb2cd314a599a` | Wholesome diet (pathya) after purification, in Pandu → RECOMMENDS_DIET → Water boiled with the sthirādi group of drugs, for drinking and cooking | Ca.6.16.114 | — | 1 |

#### Dosha association

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-f2f5946d6a5e2dc3d1e1` | Pandu → ASSOCIATED_WITH_DOSHA → Kapha | Ca.6.16.23, Ca.6.16.3 | lines 96227-96228 | 1 |
| 2 | `PCL-303ec82e20bf20cab7d0` | Pandu → ASSOCIATED_WITH_DOSHA → Pitta | Ah.3.13.001a, Ca.6.16.4 | — | 2 |
| 3 | `PCL-b4ed69a8446881a9fa6b` | Pandu → ASSOCIATED_WITH_DOSHA → Vata | Ca.6.16.17, Ca.6.16.3 | lines 96192-96196 | 1 |

#### Formulation ingredient

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-9b6fe3fd3bbb413b605c` | Navāyasa cūrṇa → CONTAINS_INGREDIENT → Citraka | Ca.6.16.70 | — | 1 |
| 2 | `PCL-2b2de85faf5b7dd0cbfc` | Navāyasa cūrṇa → CONTAINS_INGREDIENT → Musta | Ca.6.16.70 | lines 96926-96928 | 1 |
| 3 | `PCL-78a4e3b23d5cd7971754` | Navāyasa cūrṇa → CONTAINS_INGREDIENT → Viḍaṅga | Ca.6.16.70 | — | 1 |
| 4 | `PCL-2b005a490c7bc20f2608` | Punarnavā maṇḍūra → CONTAINS_INGREDIENT → Citraka | Ca.6.16.93 | — | 1 |
| 5 | `PCL-ab93fe5543fc7a646fcd` | Punarnavā maṇḍūra → CONTAINS_INGREDIENT → Haridrā | Ca.6.16.94 | — | 1 |
| 6 | `PCL-38e2d3f0e0ce212f7bb4` | Punarnavā maṇḍūra → CONTAINS_INGREDIENT → Musta | Ca.6.16.94 | — | 1 |
| 7 | `PCL-a5e87cb201242dd2bb35` | Punarnavā maṇḍūra → CONTAINS_INGREDIENT → Punarnavā | Ca.6.16.93 | lines 97087-97095 | 1 |
| 8 | `PCL-2a5949256e9c2546e1ac` | Punarnavā maṇḍūra → CONTAINS_INGREDIENT → Trivṛt | Ca.6.16.93 | — | 1 |
| 9 | `PCL-76aa0fdee8d044add90e` | Punarnavā maṇḍūra → CONTAINS_INGREDIENT → Viḍaṅga | Ca.6.16.93 | — | 1 |

#### Formulation use

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-2449e57b7f0817605755` | Oleation with medicated ghee (snehana) in Pandu → USES_FORMULATION → Dāḍimādya ghṛta | Ca.6.16.45 | lines 96416-96418 | 1 |
| 2 | `PCL-b9b8aff90fe3fb934c92` | Oleation with medicated ghee (snehana) in Pandu → USES_FORMULATION → Kalyāṇaka ghṛta | Ca.6.16.43 | lines 96401-96403 | 1 |
| 3 | `PCL-f9f4484b0053df2e2c1e` | Oleation with medicated ghee (snehana) in Pandu → USES_FORMULATION → Mahātikta ghṛta | Ca.6.16.43 | — | 1 |
| 4 | `PCL-8f678da3a99a52f1e2bf` | Oleation with medicated ghee (snehana) in Pandu → USES_FORMULATION → Pañcagavya ghṛta | Ca.6.16.43 | — | 1 |
| 5 | `PCL-acbd6f8a2d3ea40dfc45` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Iron powder macerated in cow's urine, given with milk (ayorajas) (qualified) | Ca.6.16.69 | lines 96920-96922 | 1 |
| 6 | `PCL-ede5804c400f94198c61` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Bījaka ariṣṭa | Ca.6.16.110 | — | 1 |
| 7 | `PCL-beb7bc30811225f25e7d` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Dhātrī ariṣṭa | Ca.6.16.113 | — | 1 |
| 8 | `PCL-daa5fde40cdbe3dbf33d` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Dhātrī avaleha | Ca.6.16.102 | lines 97173-97173 | 1 |
| 9 | `PCL-5ae6ae4735ddfb917ada` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Maṇḍūra vaṭaka | Ca.6.16.76 | lines 96987-96988 | 1 |
| 10 | `PCL-827dd1655af336e2bb73` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Navāyasa cūrṇa | Ca.6.16.71 | lines 96946-96947 | 1 |
| 11 | `PCL-ac8fb4aab82dfaf2a86c` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Punarnavā maṇḍūra | Ca.6.16.96 | lines 97117-97119 | 1 |
| 12 | `PCL-1c7aa40242cbd689b8a3` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Śilājatu vaṭaka | Ca.6.16.91 | — | 1 |
| 13 | `PCL-336df49f0ed3bdb18836` | Medication chosen according to the predominant dosha, in Pandu → USES_FORMULATION → Yogarāja | Ca.6.16.86 | — | 1 |

#### Herb use

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-4b00b22c0cee829c5353` | Purification (saṃśodhana) with sharp emetic and purgative drugs after oleation, in Pandu → USES_HERB → Harītakī | Ca.6.16.58 | lines 96559-96565 | 1 |
| 2 | `PCL-44bcf32caafda3d75277` | Purification (saṃśodhana) with sharp emetic and purgative drugs after oleation, in Pandu → USES_HERB → Trivṛt | Ca.6.16.57 | lines 96555-96557 | 1 |

#### Symptom indication

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-47e0c494e4615063cee9` | absence of sweating → INDICATES → Pandu | Ah.3.13.008a, Ca.6.16.12 | — | 2 |
| 2 | `PCL-48462dfe3f9d42e70a7f` | loss of appetite → INDICATES → Pandu | Ah.3.13.006a, Ca.6.16.13 | lines 96178-96179 | 2 |
| 3 | `PCL-b5b632986b47da5a5dbb` | body ache → INDICATES → Pandu | Ca.6.16.14 | lines 96162-96162 | 1 |
| 4 | `PCL-965764142fd090c78beb` | breathlessness → INDICATES → Pandu | Ah.3.13.007a, Ca.6.16.14 | lines 96162-96162 | 2 |
| 5 | `PCL-4655eb207ad698a37534` | dizziness → INDICATES → Pandu | Ah.3.13.007a, Ca.6.16.13 | — | 2 |
| 6 | `PCL-690a61d57be04d358cad` | dryness of the skin → INDICATES → Pandu | Ah.3.13.008a, Ca.6.16.12 | — | 2 |
| 7 | `PCL-4a4a2bc3390cb4991a77` | fatigue → INDICATES → Pandu | Ah.3.13.007a, Ca.6.16.13 | lines 96149-96151 | 2 |
| 8 | `PCL-f332dc7dac6b02e86acb` | fever → INDICATES → Pandu | Ah.3.13.007a, Ca.6.16.14 | — | 2 |
| 9 | `PCL-ea1fbd62b419b826307a` | pallor → INDICATES → Pandu | Ah.3.13.003a, Ca.6.16.11, Su.6.44.4 | — | 3 |
| 10 | `PCL-42507175c87cf1713980` | palpitations → INDICATES → Pandu | Ah.3.13.008a, Ca.6.16.12 | lines 96149-96151 | 2 |
| 11 | `PCL-9579545446f059528482` | periorbital swelling → INDICATES → Pandu | Ah.3.13.006a, Ca.6.16.15 | lines 96181-96183 | 2 |
| 12 | `PCL-37c722b5b5b1bdafeab5` | tinnitus → INDICATES → Pandu | Ah.3.13.007a, Ca.6.16.13 | lines 96153-96160 | 2 |
| 13 | `PCL-f963f62af1a5593374cf` | general weakness → INDICATES → Pandu | Ca.6.16.13 | lines 96153-96160 | 1 |

#### Treatment principle

| # | Claim ID | Subject → predicate → object | Primary citations | Translation | Sources |
|---|---|---|---|---|---|
| 1 | `PCL-e18bd5226d3b6644fbd5` | Pandu → SUGGESTS_PRINCIPLE → Wholesome diet (pathya) after purification, in Pandu | Ca.6.16.41 | — | 1 |
| 2 | `PCL-d754ab6e702d5e2681a4` | Pandu → SUGGESTS_PRINCIPLE → Purification (saṃśodhana) with sharp emetic and purgative drugs after oleation, in Pandu | Ca.6.16.40, Su.6.44.14 | lines 96384-96386 | 2 |
| 3 | `PCL-eaf85b89e6201e2a524a` | Pandu → SUGGESTS_PRINCIPLE → Oleation with medicated ghee (snehana) in Pandu | Ca.6.16.43 | lines 96401-96403 | 1 |
| 4 | `PCL-66ae5b2f52df024d9889` | Pandu → SUGGESTS_PRINCIPLE → Medication chosen according to the predominant dosha, in Pandu | Ca.6.16.123, Ca.6.16.42 | lines 96398-96399 | 1 |
