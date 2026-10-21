# Component 1 → Component 2 Integration Testing (2026-10-20)

No Component 1 model exists in this repository. No public dataset contains
Component 1 outputs, which are a risk tier, a calibrated confidence and
symptoms, produced from images, PPG and a questionnaire. The integration is
tested with two input sets that follow the provisional `C1ScreeningPayload`
contract (`app/models/c1_screening_payload.py`), against two backends.

## 1. Inputs

### Synthetic scenarios (committed)

`samples/c1_screening_scenarios.json`, also bundled for the client as
`ayurai-client/src/lib/samples/`. These are eight invented payloads, each
stating its expected outcome:

| Scenario | Exercises |
|---|---|
| `syn-01-high-classic` | 3 present symptoms, including the alias "shortness of breath" |
| `syn-02-moderate-fatigue` | An absent symptom that is ignored |
| `syn-03-low-no-symptoms` | No present symptom → `insufficient_input` |
| `syn-04-unknown-symptom` | "hair loss" reported `not_found`, never guessed |
| `syn-05-null-confidence` | Null C1 confidence, missing modalities, an unverified claim |
| `syn-06-unsupported-tier` | `very_high` → `blocked` |
| `syn-07-symptom-without-claims` | A known symptom with no claims → abstention |
| `syn-08-ambiguous-symptom` | "weakness" matches two symptoms → `ambiguous`, not guessed |

### Reference-derived real data (NHANES, local only)

`app/integration/c1_reference_samples.py` builds C1-shaped payloads from
NHANES 2017–March 2020 public-use files. They are registry rows N-027 to
N-030, CDC public domain under the NCHS Data User Agreement: statistical
use only, no re-identification and no linking.

**Population.** Non-pregnant adults aged 40–65 with measured haemoglobin.
3,735 people are eligible:

| Tier | Eligible |
|---|---|
| low | 3,366 |
| moderate | 254 |
| high | 115 |

**Risk tier.** It comes from **laboratory Hb**, using WHO 2024 Table 3. The
cutoffs were verified against the guideline text extracted from registry
row N-021. The mapping is provisional:

| WHO 2024 severity | Tier |
|---|---|
| none | low |
| mild | moderate |
| moderate or severe | high |

**Symptoms.**

- fatigue: DPQ040 ≥ "several days"
- breathlessness: CDQ010, shortness of breath on stairs
- Refused or don't-know answers go into `missing_data`. They are never
  guessed.

**Confidence.** Always null: no model produced these cases. Each payload's
status is `reference_derived_not_model_output`.

**Sample.** Stratified, 20 per tier, seed 2026, so 60 payloads. They are
written to the git-ignored
`corpus/extracted/c1_samples/nhanes_reference_samples.json`:

```bash
python -m app.integration.c1_reference_samples corpus/raw/c1_reference/nhanes_2017_2020 \
    --out corpus/extracted/c1_samples/nhanes_reference_samples.json
```

The SAS transport files are read by a small stdlib XPORT v5 reader, so no
pandas dependency is needed. It is tested with synthetic XPT files. On the
real files it reports the documented 15,560 DEMO records.

## 2. Backends

| Backend | Command | Graph |
|---|---|---|
| Live | `uvicorn app.main:app --port 8000` | AuraDB |

The service always reads the live AuraDB graph. The synthetic sandbox
server (`app.dev.sandbox`), its `X-AyurAI-Data-Mode` header and the
`data_mode` health field were removed on 2026-10-20. The synthetic graph
now lives only in the tests (`tests/fixtures/synthetic_graph_v1.json`,
loaded by `memory_graph_test_support.py`), where it still exercises every
candidate status offline. The sandbox results below are kept as a
historical record.

## 3. Results

| Input | Live AuraDB | Sandbox |
|---|---|---|
| 8 synthetic scenarios | (not run: no symptoms in the graph) | All 8 took the expected path: 3 sufficient, 1 conflicting (null confidence and unverified claim), 1 abstention (no claims), 2 `insufficient_input`, 1 `blocked` |
| 60 NHANES cases | **60 of 60 `insufficient_input: no_present_symptoms_resolved`**, correctly, because AuraDB has no Symptom nodes | 49 `sufficient_for_review`, 11 `insufficient_input` (no present symptom). Upstream tier and null confidence pass through unchanged, and `medical_conclusion` stays null. |

Covered by `test_c1_samples_and_scenarios.py`: the XPT reader, the WHO
boundaries, payload honesty, and, over the in-memory test graph, scenario
paths, candidate statuses, unknown and ambiguous symptoms and expected
decisions.

## 4. Findings that need a decision

1. **Risk tier did not influence C2 output.** *Resolved 2026-10-20 by
   Option B* (`design_risk_tier_integration.md` §9). The tier and
   confidence now gate a Recommend / Caution / Abstain decision. Ranking
   is still unaffected, by design. The original finding follows.
   - What happens: a low-tier person with fatigue gets the same candidates
     as a high-tier person.
   - Why: this is the implemented design. The tier is passed through as
     metadata only, and a unit test asserts it.
   - Conflict: proposal SO4 says ranking should consider "symptom/risk
     compatibility".
   - Not changed: altering ranking or sufficiency by tier is a
     methodological decision for you and your supervisor.
2. **The C1 → C3 contract gap.** Component 3 requires a numeric
   `anemia_confidence`. When C1 supplies none, the client now refuses to
   send the case to C3, with an explanation, instead of substituting a
   value.
3. **The symptom vocabulary is undefined.** C1 symptom names must match
   graph Symptom names or aliases exactly. Agree a shared vocabulary with
   the C1 owner, for example fatigue, pallor, breathlessness, dizziness and
   palpitations, and seed the graph's Symptom nodes from it after review.

## 5. Frontend

- **Import page.** *Import C1 output* (`/screening/import`) accepts any of:
  - a bundled scenario
  - an uploaded JSON file (one payload, an array, `{payloads: [...]}`, or
    the scenario file)
  - pasted JSON

  Payloads are sent in order to `POST /api/v1/c1/reasoning`. A table shows
  the tier, confidence, present symptoms, mapping (resolved, unresolved or
  ambiguous) and C2 outcome. Each row opens as a normal case.
- **Analysis page.** It shows the C1 name → graph symptom mapping. A case
  where C2 did not run shows the mapping and the reason instead of
  substituting anything.
- **Running it.** `npm run dev` proxies `/c2-api` to the live service on
  port 8000 (or `C2_PROXY_TARGET`). The separate offline demo mode is
  unchanged.
- **Null confidence.** It is displayed as "—" and blocked from C3 with an
  explanation.
