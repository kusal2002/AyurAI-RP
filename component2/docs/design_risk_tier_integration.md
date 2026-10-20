# Design Proposal: Using the Component 1 Risk Tier in Component 2

**Status (2026-10-20): Option B implemented.** R-D1, R-D2 and R-D3 were
approved as recommended. Option C remains design only. R-D4, R-D5 and R-D6
are still open. See §9 for what was built and where it differs from this
proposal.

## 1. The problem

Component 2 currently treats the C1 risk tier and calibrated confidence
as **metadata only**. They are passed through to `output.upstream` and do
not affect traversal, ranking, sufficiency or abstention.
`test_screening_confidence_is_not_used_for_candidates` asserts this.

In the 60 NHANES reference-derived cases (`docs/c1_integration_testing.md`),
a low-tier person with fatigue received exactly the same six candidates,
scores and dispositions as a person with moderate or severe anaemia.

The proposal requires more than that:

| Ref | Requirement | Current state |
|---|---|---|
| SO4 | Ranking considers "symptom/risk compatibility" | Not implemented |
| FR2 | Normalize risk and symptom information for concept mapping | Symptoms only |
| FR8 | The score includes symptom/risk compatibility and uncertainty; it must be transparent and reproducible | Five evidence components; no risk term |
| FR9 | Three states: **Recommend / Caution / Abstain** | Only Recommend-for-review or Abstain. **No Caution state exists.** |
| FR10 | Abstain or escalate when "critical input information is missing" | Missing C1 confidence is not considered |
| SO5 | Calibrate sufficiency and uncertainty: abstention precision/recall, selective accuracy | Not measured |

## 2. Constraints any design must respect

These come from decisions already made in this project.

1. **Do not fabricate compatibility.** The graph holds no knowledge that
   relates a candidate to an anaemia severity. A tier-based ranking
   adjustment with no evidence behind it would be an invented clinical
   rule presented as reasoning.
2. **A risk tier is not a classical stage.** The C1 tier comes from modern
   haemoglobin severity, for example WHO cutoffs.
   - The lexicon rule already says *Pandu ≠ anaemia*: the two are related,
     not equivalent.
   - So "high tier = advanced Pandu" is itself an unverified claim. If it
     is used at all, it needs practitioner sign-off and a citation.
3. **C1 confidence is not C2 confidence.** The output never reuses
   screening confidence as confidence in an Ayurvedic concept. Using it to
   *gate* (caution or escalate) is compatible with that rule. Using it to
   *score* candidates is not.
4. **Safety belongs to Component 3.** Contraindications at high severity
   are C3's job. C2 may escalate. It must not decide that a candidate is
   unsafe.
5. **Reproducible, configurable policies.** Every threshold lives in a
   versioned policy object with a `policy_id`, like `RankingPolicy` and
   `SufficiencyPolicy`, and is marked provisional.

## 3. Options

| | Option | What it does | Faithful to SO4/FR8/FR9 | Needs new knowledge | Risk of fabricated reasoning | Effort |
|---|---|---|---|---|---|---|
| **A** | Keep as metadata | No change. Document the limitation. | No | No | None | None |
| **B** | Tier-gated caution and escalation (decision layer) | Adds the FR9 **Caution** state. High tier, missing confidence or low confidence trigger caution and practitioner/conventional-care escalation. **Ranking order and candidate sufficiency are unchanged.** | FR9 and FR10 fully; SO4 partly (risk shapes the decision, not the order) | No: the policy is a safety rule, not Ayurvedic knowledge | Low: the rules are explicit and labelled policy, not claims | Small |
| **C** | Evidence-based severity compatibility (ranking) | Ontology v1.2 relates principles to a severity context through **reviewed, cited claims**. Ranking gains a `risk_compatibility` component that is non-zero only when such a claim exists. | SO4 and FR8 fully, if the data exists | **Yes**: reviewed passages that state severity-specific management, plus a practitioner-approved tier → severity crosswalk | Low if the evidence rules are enforced; zero effect until curated | Medium code; large curation |
| **D** | Confidence-based selective prediction | Uses C1 confidence to withhold uncertain cases, for selective accuracy (SO5) | SO5 partly | No | Medium, if the confidence is miscalibrated (C1 has no calibrated model yet) | Small. Best folded into B. |
| **E** | Heuristic tier weighting | For example, multiply scores for "stronger" candidates in high tiers | Looks like SO4 | Has none, and invents it | **High**: an uncited clinical rule | Small |

**Rejected: E.** It encodes a severity–treatment relationship with no
source, which every other part of this system refuses to do.

## 4. Recommendation

1. **Implement B now, with D's input-quality checks folded in.** It closes
   FR9 and FR10, makes risk visible in every decision, needs no new
   knowledge, and does not change rankings, so existing evaluation results
   stay comparable.
2. **Prepare C as the research track.**
   - Ontology v1.2 and a `risk_compatibility` ranking component with weight
     `w_risk`, default 0 until curated claims exist.
   - It is enabled and evaluated by ablation (SO4) only after practitioners
     approve severity claims and the crosswalk.
   - Until then it reports `risk_compatibility_unknown` rather than
     guessing.
3. **Keep A's guarantee for scores.** Under B, the ranking score is still
   independent of C1 confidence. The existing test stays and is renamed to
   say exactly that.

## 5. Option B specification

### 5.1 New policy object

`RiskContextPolicy` (`policy_id = "prototype-risk-context-v0.1-provisional"`).
All values are provisional and need supervisor sign-off:

| Rule | Trigger | Effect |
|---|---|---|
| R1 high tier | `risk_tier == high` | Decision at least **caution**. Flag `upstream_high_risk`. Escalation note: practitioner review **and** conventional clinical assessment are recommended. |
| R2 missing confidence | `calibrated_confidence is null` | Decision at least **caution**. Flag `upstream_confidence_missing` (FR10). |
| R3 low confidence | `calibrated_confidence < 0.5` (provisional) | Decision at least **caution**. Flag `upstream_low_confidence`. |
| R4 optional: high tier and missing confidence | both | Configurable: caution (default) or **abstain** with `critical_upstream_information_missing` |
| R5 low and moderate tier | — | No change. A low tier does **not** mean no condition. |

### 5.2 Decision mapping (FR9)

A new request-level field `decision` keeps the existing
`sufficiency_status` unchanged, so it is additive:

| C2 evidence status (unchanged) | Risk rules triggered | `decision` |
|---|---|---|
| `sufficient_for_review` | none | **recommend_for_review** |
| `sufficient_for_review` | any of R1–R3 | **caution** |
| `conflicting_evidence` or `unverified_claims` | any | **caution** (as today: candidates withheld) |
| `insufficient_evidence` or `out_of_scope` | any | **abstain** (unchanged) |
| any | R4 configured to abstain | **abstain** |

Candidate `disposition` (forward or withhold) is **not** changed by risk
rules. Under caution, forwarded candidates still go to C3, with the risk
flags attached, so the safety assessment and the practitioner see them.

### 5.3 Contract changes, all additive

- `Component2Output` gains `decision` and a `risk_context` object:
  `{tier, confidence, rules_triggered, escalation, policy_id}`.
  The schema becomes `c2-output/0.2.0`.
- The C3 handoff carries `risk_context`, so C3 can use it. This needs a
  check with the C3 owner.
- Frontend: decision badges for Recommend, Caution and Abstain, and an
  escalation notice.
- Audit record: `decision` and the risk policy ID. *Changed during
  implementation:* the triggered rule IDs are **not** logged, because they
  would reveal the risk tier and confidence, which the audit record
  deliberately excludes (implementation notes §15).

### 5.4 Tests

- Scores are identical for confidence 0.01 and 0.99 (existing invariant,
  kept).
- `decision` changes as specified for every row of §5.2. The tier and the
  confidence each switch caution on and off independently.
- Candidate dispositions are identical across tiers (no hidden ranking
  effect).
- The sandbox scenarios gain an expected `decision`. The NHANES run
  reports the decision distribution per tier.

## 6. Option C specification (research track)

### 6.1 Knowledge model (ontology v1.2; needs approval)

- **New concept.** `SeverityContext`, with IDs `SEV-MILD`, `SEV-MODERATE`
  and `SEV-SEVERE`, or classical stages if practitioners prefer.
- **New reasoning predicate.** `INDICATED_AT_SEVERITY`
  (TherapeuticPrinciple → SeverityContext). It is written only through
  reviewed claims, extracted or modelled with `model-claim`, and each claim
  cites a passage. Candidate sources to check are a verified official copy
  of the Ayurvedic Standard Treatment Guidelines (registry N-024), Caraka
  Ci. 16 and the Mādhavanidāna Pandu chapter.
- **Crosswalk.** Tier → SeverityContext is a separate, versioned,
  practitioner-approved mapping with a rationale. It is stored as data,
  never hard-coded, and never presented as Ayurvedic doctrine.
- **Out of scope for C2.** Severity *contraindications* stay with C3,
  under constraint 4.

### 6.2 Ranking component

`risk_compatibility(path, tier)`:

| Situation | Value |
|---|---|
| The path's principle has an approved `INDICATED_AT_SEVERITY` claim for the crosswalked severity, and that claim passes the same sufficiency checks | `+1` |
| No severity claim exists for the principle | `0`, flag `risk_compatibility_unknown` |
| Claims exist only for other severities | `0`, flag `indicated_for_other_severity`. **No penalty**, because absence of evidence is not evidence of incompatibility. A penalty is an explicit policy option for the ablation only. |

The weight `w_risk` defaults to **0.0**. It is reported in the ranking
breakdown like the other components.

### 6.3 Evaluation (SO4 ablation)

- **Cases.** 50–100 practitioner-labelled cases, as the proposal
  specifies.
  - Tiers are stratified, and the NHANES derivation provides realistic
    tier and symptom mixes.
  - Gold rankings come from practitioners, blind to system output.
- **Compare:**
  - `w_risk = 0`, which is the B behaviour
  - `w_risk > 0`
  - optionally the penalty variant
- **Metrics:** NDCG@K and expert relevance per tier, plus abstention
  precision and recall.
- **Report** effects per tier, so a gain in one tier cannot hide a loss in
  another.

## 7. Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| R-D1 | Adopt B (Caution state plus risk gating) now? | **Yes** |
| R-D2 | Provisional thresholds: low-confidence cutoff 0.5; high tier triggers caution rather than abstain | Yes. Revisit after the SO5 calibration data. |
| R-D3 | R4: should high tier with missing confidence abstain? | No. Caution plus escalation keeps the information visible to the practitioner. |
| R-D4 | Start C (ontology v1.2 `SeverityContext` / `INDICATED_AT_SEVERITY`)? | Yes as design, with `w_risk = 0` until practitioners approve claims and the crosswalk |
| R-D5 | Share `risk_context` with C3 (contract change)? | Yes. Confirm with the C3 owner. |
| R-D6 | Confirm the provisional NHANES tier mapping with the C1 owner (none → low, mild → moderate, moderate/severe → high) | Needed before using those cases for evaluation |

## 8. What does not change

- Evidence sufficiency per candidate, conflict handling and provenance
  rules.
- The ranking score's independence from C1 confidence.
- `medical_conclusion: null`. Every decision remains a recommendation
  **for practitioner review**.

## 9. Implementation of Option B (2026-10-20)

| Piece | Where |
|---|---|
| Policy, rules and decision table | `app/reasoning/risk_context.py`: `RiskContextPolicy`, `evaluate_risk_context()`, `decide()` |
| Contract types | `app/models/c2_output.py`: `Decision`, `RiskRule`, `RiskContext`, and the new output fields `decision`, `decision_reasons`, `risk_context`. Schema `c2-output/0.2.0`; the change is additive. |
| Pipeline | `run_component2_reasoning(..., risk_policy=None)`. The decision is computed **after** ranking and sufficiency are final. Caution adds a `caution` explanation statement and sets `review_required`. |
| Audit | `decision` and `risk_policy_id` only (see §5.3) |
| C3 handoff | **Unchanged.** R-D5 is not approved. |
| Frontend | `decisionSpec()` badges (Recommend for review / Caution / Abstain) shown next to the evidence status, on the analysis, overview, review and import pages. A "Decision: caution" notice with the escalation text appears on the analysis and candidates pages. The demo fixture is updated to 0.2.0. |
| Tests | `test_risk_context.py` (25): every rule, every row of §5.2, R4 configurable, ranking and dispositions identical across 5 tier/confidence variants, audit privacy, unchanged C3 handoff. Scenario fixtures carry an `expected_decision`, checked in `test_c1_samples_and_sandbox.py`. |

### Results on the test inputs (sandbox graph)

| Input | Decision |
|---|---|
| `syn-01` high tier, sufficient evidence | **caution** (`risk:upstream_high_risk`) |
| `syn-02`, `syn-04` moderate tier, confidence ≥ 0.5, sufficient | **recommend_for_review** |
| `syn-05` high tier, null confidence, conflicting evidence | **caution** (evidence reason plus both risk reasons) |
| `syn-07` no claims | **abstain** |
| 60 NHANES reference-derived cases | 49 **caution**, 11 `insufficient_input` |

**Why every NHANES case is caution.** Those payloads have no C1
confidence by construction, because no model produced them. Rule R2
therefore applies to all of them. Tier-specific differences in the decision
will only be observable once Component 1 supplies real calibrated
confidences. This is a limitation of the reference-derived inputs, not of
the rules.
