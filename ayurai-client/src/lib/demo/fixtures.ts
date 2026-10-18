/**
 * DEMO FIXTURES - FICTIONAL DATA ONLY.
 *
 * These records exist to demonstrate layouts and interactions when no
 * backend is connected. They do not describe real patients, real sources,
 * real knowledge-graph content or real model output. Every identifier is
 * prefixed with DEMO and every source is marked as fictional.
 *
 * The shapes follow the backend contracts in src/lib/api/types.ts so the
 * same screens render demo and live data.
 */

import type {
  ClaimStep,
  Component2Output,
  EvidenceReference,
  SafetyAssessmentReport,
} from "@/lib/api/types"

function demoEvidence(
  id: string,
  relationship: EvidenceReference["relationship"],
  overrides: Partial<EvidenceReference> = {},
): EvidenceReference {
  return {
    evidence_id: id,
    relationship,
    title: `Fictional demo evidence record ${id.replace("DEMO-EV-", "")}`,
    source_name: "AyurAI demo fixture (not a real source)",
    evidence_type: "classical",
    section: "Demo section",
    page: null,
    citation: null,
    source_url: null,
    practitioner_verified: false,
    provenance_complete: true,
    missing_provenance: [],
    ...overrides,
  }
}

function claim(step: Partial<ClaimStep> & Pick<ClaimStep, "claim_id" | "subject_id" | "predicate" | "object_id">): ClaimStep {
  return {
    subject_type: null,
    object_type: null,
    statement: null,
    verification_status: "literature_supported",
    stored_confidence: null,
    supporting_evidence: [],
    contradicting_evidence: [],
    evidence_lookup_failed: false,
    retrieval_similarity: null,
    ...step,
  }
}

const c1 = claim({
  claim_id: "DEMO-CL-1",
  subject_id: "DEMO-SYM-1",
  subject_type: "Symptom",
  predicate: "INDICATES",
  object_id: "DEMO-ROGA-1",
  object_type: "Roga",
  statement: "[Demo] Demo symptom A is associated with the demo Roga concept.",
  supporting_evidence: [demoEvidence("DEMO-EV-1", "SUPPORTS")],
  retrieval_similarity: 0.71,
})

const c2 = claim({
  claim_id: "DEMO-CL-2",
  subject_id: "DEMO-ROGA-1",
  subject_type: "Roga",
  predicate: "ASSOCIATED_WITH_DOSHA",
  object_id: "DEMO-DOSHA-1",
  object_type: "Dosha",
  statement: "[Demo] The demo Roga concept is associated with the demo Dosha concept.",
  supporting_evidence: [demoEvidence("DEMO-EV-2", "SUPPORTS")],
  retrieval_similarity: 0.64,
})

const c3 = claim({
  claim_id: "DEMO-CL-3",
  subject_id: "DEMO-ROGA-1",
  subject_type: "Roga",
  predicate: "AFFECTS_DHATU",
  object_id: "DEMO-DHATU-1",
  object_type: "Dhatu",
  statement: "[Demo] The demo Roga concept affects the demo Dhatu concept.",
  supporting_evidence: [demoEvidence("DEMO-EV-2", "SUPPORTS")],
  retrieval_similarity: 0.58,
})

const c4 = claim({
  claim_id: "DEMO-CL-4",
  subject_id: "DEMO-DOSHA-1",
  subject_type: "Dosha",
  predicate: "SUGGESTS_PRINCIPLE",
  object_id: "DEMO-TP-1",
  object_type: "TherapeuticPrinciple",
  statement: "[Demo] The demo Dosha concept suggests the demo therapeutic principle.",
  supporting_evidence: [demoEvidence("DEMO-EV-3", "SUPPORTS")],
  retrieval_similarity: 0.62,
})

const c8 = claim({
  claim_id: "DEMO-CL-8",
  subject_id: "DEMO-DHATU-1",
  subject_type: "Dhatu",
  predicate: "SUGGESTS_PRINCIPLE",
  object_id: "DEMO-TP-1",
  object_type: "TherapeuticPrinciple",
  statement: "[Demo] The demo Dhatu concept suggests the demo therapeutic principle.",
  verification_status: "unverified",
  supporting_evidence: [demoEvidence("DEMO-EV-3", "SUPPORTS")],
  retrieval_similarity: 0.49,
})

const c5 = claim({
  claim_id: "DEMO-CL-5",
  subject_id: "DEMO-TP-1",
  subject_type: "TherapeuticPrinciple",
  predicate: "USES_HERB",
  object_id: "DEMO-HERB-A",
  object_type: "Herb",
  statement: "[Demo] The demo therapeutic principle uses Demo Herb A.",
  supporting_evidence: [
    demoEvidence("DEMO-EV-4", "SUPPORTS", { evidence_type: "modern_research" }),
  ],
  retrieval_similarity: 0.66,
})

const c6 = claim({
  claim_id: "DEMO-CL-6",
  subject_id: "DEMO-TP-1",
  subject_type: "TherapeuticPrinciple",
  predicate: "USES_FORMULATION",
  object_id: "DEMO-FORM-B",
  object_type: "Formulation",
  statement: "[Demo] The demo therapeutic principle uses Demo Formulation B.",
  supporting_evidence: [demoEvidence("DEMO-EV-5", "SUPPORTS")],
  contradicting_evidence: [
    demoEvidence("DEMO-EV-6", "CONTRADICTS", {
      evidence_type: "modern_research",
      section: null,
      provenance_complete: false,
      missing_provenance: ["citation_or_locator"],
    }),
  ],
  retrieval_similarity: 0.55,
})

const c7 = claim({
  claim_id: "DEMO-CL-7",
  subject_id: "DEMO-TP-1",
  subject_type: "TherapeuticPrinciple",
  predicate: "RECOMMENDS_DIET",
  object_id: "DEMO-DIET-C",
  object_type: "Diet",
  statement: "[Demo] The demo therapeutic principle recommends Demo Diet C.",
  verification_status: "unverified",
  supporting_evidence: [],
  retrieval_similarity: null,
})

const path = (claims: ClaimStep[]) => ({
  concept_ids: [claims[0].subject_id, ...claims.map((step) => step.object_id)],
  claims,
})

export const demoComponent2Output: Component2Output = {
  schema_version: "c2-output/0.1.0",
  request_id: "c2req-DEMO-0001",
  generated_at: "2026-01-01T09:00:00Z",
  upstream: { risk_tier: "moderate", calibrated_confidence: 0.72 },
  input_symptom_ids: ["DEMO-SYM-1", "DEMO-SYM-UNKNOWN"],
  symptom_mappings: [
    {
      symptom_id: "DEMO-SYM-1",
      found: true,
      name: "Demo symptom A",
      indicates_claim_ids: ["DEMO-CL-1"],
      message: null,
    },
    {
      symptom_id: "DEMO-SYM-UNKNOWN",
      found: false,
      name: null,
      indicates_claim_ids: [],
      message: "Symptom not found in the knowledge graph.",
    },
  ],
  interpretation: [
    {
      concept_id: "DEMO-ROGA-1",
      concept_type: "Roga",
      name: "Demo Roga concept (Pandu scope)",
      via_claim_ids: ["DEMO-CL-1"],
      verification_statuses: ["literature_supported"],
      supporting_evidence_ids: ["DEMO-EV-1"],
      contradicting_evidence_ids: [],
    },
    {
      concept_id: "DEMO-DOSHA-1",
      concept_type: "Dosha",
      name: "Demo Dosha concept",
      via_claim_ids: ["DEMO-CL-2"],
      verification_statuses: ["literature_supported"],
      supporting_evidence_ids: ["DEMO-EV-2"],
      contradicting_evidence_ids: [],
    },
    {
      concept_id: "DEMO-DHATU-1",
      concept_type: "Dhatu",
      name: "Demo Dhatu concept",
      via_claim_ids: ["DEMO-CL-3"],
      verification_statuses: ["literature_supported"],
      supporting_evidence_ids: ["DEMO-EV-2"],
      contradicting_evidence_ids: [],
    },
    {
      concept_id: "DEMO-TP-1",
      concept_type: "TherapeuticPrinciple",
      name: "Demo therapeutic principle",
      via_claim_ids: ["DEMO-CL-4"],
      verification_statuses: ["literature_supported"],
      supporting_evidence_ids: ["DEMO-EV-3"],
      contradicting_evidence_ids: [],
    },
  ],
  candidates: [
    {
      candidate_id: "DEMO-HERB-A",
      category: "Herb",
      name: "Demo Herb A",
      rank: 1,
      ranking: {
        score: 0.71,
        components: { status: 0.28, support: 0.1, contradiction: 0, provenance: 0, retrieval: 0.12 },
        policy_id: "prototype-ranking-v0.1-provisional",
        label: "experimental_ranking_score_not_clinical_confidence",
      },
      disposition: "forward_for_safety_assessment",
      paths: [path([c1, c2, c4, c5]), path([c1, c3, c8, c5])],
      claim_ids: ["DEMO-CL-1", "DEMO-CL-2", "DEMO-CL-4", "DEMO-CL-5", "DEMO-CL-3", "DEMO-CL-8"],
      supporting_evidence_ids: ["DEMO-EV-1", "DEMO-EV-2", "DEMO-EV-3", "DEMO-EV-4"],
      contradicting_evidence_ids: [],
      verification_statuses: ["literature_supported", "unverified"],
      conflict_flags: [],
      sufficiency: {
        status: "sufficient_for_review",
        review_required: true,
        uncertainty_flags: ["multiple_paths", "some_paths_not_sufficient"],
        evidence_gaps: [],
        policy_id: "prototype-sufficiency-v0.1-provisional",
      },
      rationale: [
        {
          kind: "candidate_path",
          text: "[Demo] Reached through Demo symptom A → Demo Roga concept → Demo Dosha concept → Demo therapeutic principle → Demo Herb A.",
          claim_ids: ["DEMO-CL-1", "DEMO-CL-2", "DEMO-CL-4", "DEMO-CL-5"],
          evidence_ids: [],
        },
        {
          kind: "supporting_evidence",
          text: "[Demo] Each claim on this path has at least one fictional supporting record.",
          claim_ids: [],
          evidence_ids: ["DEMO-EV-1", "DEMO-EV-2", "DEMO-EV-3", "DEMO-EV-4"],
        },
      ],
    },
    {
      candidate_id: "DEMO-FORM-B",
      category: "Formulation",
      name: "Demo Formulation B",
      rank: 2,
      ranking: {
        score: 0.38,
        components: { status: 0.28, support: 0.1, contradiction: -0.1, provenance: 0, retrieval: 0.11 },
        policy_id: "prototype-ranking-v0.1-provisional",
        label: "experimental_ranking_score_not_clinical_confidence",
      },
      disposition: "withheld_pending_review",
      paths: [path([c1, c2, c4, c6])],
      claim_ids: ["DEMO-CL-1", "DEMO-CL-2", "DEMO-CL-4", "DEMO-CL-6"],
      supporting_evidence_ids: ["DEMO-EV-1", "DEMO-EV-2", "DEMO-EV-3", "DEMO-EV-5"],
      contradicting_evidence_ids: ["DEMO-EV-6"],
      verification_statuses: ["literature_supported"],
      conflict_flags: ["supporting_and_contradicting_evidence"],
      sufficiency: {
        status: "conflicting_evidence",
        review_required: true,
        uncertainty_flags: ["supporting_and_contradicting_evidence"],
        evidence_gaps: ["incomplete_provenance:DEMO-EV-6"],
        policy_id: "prototype-sufficiency-v0.1-provisional",
      },
      rationale: [
        {
          kind: "contradicting_evidence",
          text: "[Demo] A fictional record contradicts the final claim on this path; conflicting evidence is never outvoted.",
          claim_ids: ["DEMO-CL-6"],
          evidence_ids: ["DEMO-EV-6"],
        },
      ],
    },
    {
      candidate_id: "DEMO-DIET-C",
      category: "Diet",
      name: "Demo Diet C",
      rank: 3,
      ranking: {
        score: 0.08,
        components: { status: 0.08, support: 0, contradiction: 0, provenance: 0, retrieval: 0 },
        policy_id: "prototype-ranking-v0.1-provisional",
        label: "experimental_ranking_score_not_clinical_confidence",
      },
      disposition: "withheld_pending_review",
      paths: [path([c1, c2, c4, c7])],
      claim_ids: ["DEMO-CL-1", "DEMO-CL-2", "DEMO-CL-4", "DEMO-CL-7"],
      supporting_evidence_ids: ["DEMO-EV-1", "DEMO-EV-2", "DEMO-EV-3"],
      contradicting_evidence_ids: [],
      verification_statuses: ["literature_supported", "unverified"],
      conflict_flags: [],
      sufficiency: {
        status: "insufficient_evidence",
        review_required: true,
        uncertainty_flags: ["claim_without_supporting_evidence"],
        evidence_gaps: ["no_supporting_evidence:DEMO-CL-7"],
        policy_id: "prototype-sufficiency-v0.1-provisional",
      },
      rationale: [
        {
          kind: "evidence_gaps",
          text: "[Demo] The final claim has no supporting evidence and is unverified.",
          claim_ids: ["DEMO-CL-7"],
          evidence_ids: [],
        },
      ],
    },
  ],
  rejected_paths: [
    {
      concept_ids: ["DEMO-SYM-1", "DEMO-HERB-Z"],
      claim_ids: ["DEMO-CL-9"],
      reason: "[Demo] Symptom → Herb is not an allowed ontology relationship.",
    },
  ],
  retrieval: {
    mode: "neural_embedding",
    model_id: "sentence-transformers/all-MiniLM-L6-v2",
    query_count: 1,
    top_k: 5,
    min_similarity: 0.3,
    indexed_chunks: 12,
    error: null,
  },
  retrieved_evidence: [
    {
      chunk_id: "DEMO-EV-1#chunk-0",
      evidence_id: "DEMO-EV-1",
      similarity: 0.61,
      below_threshold: false,
      linked_to_traversed_claim: true,
      title: "Fictional demo evidence record 1",
      source_name: "AyurAI demo fixture (not a real source)",
      evidence_type: "classical",
      section: "Demo section",
      page: null,
      citation: null,
      source_url: null,
    },
    {
      chunk_id: "DEMO-EV-9#chunk-0",
      evidence_id: "DEMO-EV-9",
      similarity: 0.27,
      below_threshold: true,
      linked_to_traversed_claim: false,
      title: "Fictional demo evidence record 9",
      source_name: "AyurAI demo fixture (not a real source)",
      evidence_type: "modern_research",
      section: null,
      page: null,
      citation: null,
      source_url: null,
    },
  ],
  sufficiency_status: "sufficient_for_review",
  uncertainty_flags: ["retrieved_evidence_not_linked_to_claims", "ontology_invalid_paths_rejected"],
  evidence_gaps: ["no_supporting_evidence:DEMO-CL-7", "incomplete_provenance:DEMO-EV-6"],
  review_required: true,
  abstention: { abstain: false, reasons: [], explanation: null },
  explanation: [
    {
      kind: "symptom_mapping",
      text: "[Demo] 1 of 2 supplied symptom IDs matched a stored symptom concept.",
      claim_ids: ["DEMO-CL-1"],
      evidence_ids: [],
    },
    {
      kind: "interpretation",
      text: "[Demo] Graph traversal reached the demo Roga, Dosha, Dhatu and therapeutic-principle concepts. These are graph associations, not a diagnosis.",
      claim_ids: ["DEMO-CL-1", "DEMO-CL-2", "DEMO-CL-3", "DEMO-CL-4"],
      evidence_ids: ["DEMO-EV-1", "DEMO-EV-2", "DEMO-EV-3"],
    },
    {
      kind: "candidate_decision",
      text: "[Demo] 1 candidate is forwarded for safety assessment; 2 are withheld pending practitioner review.",
      claim_ids: [],
      evidence_ids: [],
    },
  ],
  traversal_truncated: false,
  limitations: [
    "Research decision-support output only; not a diagnosis or a prescription.",
    "Graph associations are not causal or efficacy claims.",
    "Candidates are not assessed for patient safety; Component 3 must perform safety assessment.",
    "Ranking and sufficiency rules are provisional prototypes pending supervisor and practitioner review.",
    "Results depend entirely on the curated knowledge graph and evidence corpus currently stored.",
  ],
  score_semantics: {
    "upstream.calibrated_confidence":
      "Component 1 screening confidence. Upstream metadata only; not used as confidence in any Ayurvedic concept or candidate.",
    retrieval_similarity:
      "Cosine similarity between embeddings of a query and an evidence chunk. Retrieval relevance only; not clinical confidence.",
    "ranking.score":
      "Experimental engineering ranking score from a provisional policy. Not clinically validated; does not predict safety or efficacy.",
    stored_confidence:
      "Confidence stored on the Claim node, if any. Null until an explicit, evaluated scoring method exists. Never generated here.",
  },
  medical_conclusion: null,
}

export const demoSafetyReport: SafetyAssessmentReport = {
  assessment_id: "SAF-DEMO0001",
  case_id: "DEMO-CASE-001",
  patient_id: "DEMO-PT-001",
  timestamp: "2026-01-01T09:05:00Z",
  overall_safety_tier: "Caution",
  highest_severity_finding: "Caution",
  evaluations: [
    {
      candidate_id: "DEMO-HERB-A",
      candidate_name: "Demo Herb A",
      safety_tier: "Caution",
      confidence: 0.95,
      summary_warning:
        "[Demo] A fictional interaction rule matched Demo Herb A and Demo Drug X.",
      interaction_findings: [
        {
          herb_or_constituent: "Demo Herb A",
          target_drug: "Demo Drug X",
          interaction_type: "Known Rule",
          severity: "Moderate",
          mechanism: "[Demo] Fictional pathway overlap used for interface testing.",
          evidence_strength: "Probable",
          prediction_confidence: 0.9,
          source_refs: [
            {
              source_id: "DEMO-SRC-1",
              source_title: "Fictional demo interaction source",
              citation_type: "Demo fixture",
              pmid_or_ref: null,
              grade: "Probable",
            },
          ],
        },
      ],
      contraindications_triggered: [],
      patient_risk_modifiers: ["[Demo] Fictional risk modifier: polypharmacy flag"],
      titration_plan: null,
      surveillance: {
        lab_monitoring: [],
        clinical_signs_to_watch: ["[Demo] Fictional sign to watch"],
      },
      escalate_to_practitioner: true,
    },
  ],
  practitioner_review_required: true,
  metadata: {
    anemia_risk_tier: "Moderate",
    total_candidates_evaluated: 1,
  },
}

/** Illustrative dashboard figures (fictional). */
export const demoScreeningTrend = [
  { day: "Mon", screenings: 18, reviewed: 12 },
  { day: "Tue", screenings: 24, reviewed: 17 },
  { day: "Wed", screenings: 20, reviewed: 16 },
  { day: "Thu", screenings: 31, reviewed: 23 },
  { day: "Fri", screenings: 27, reviewed: 20 },
  { day: "Sat", screenings: 35, reviewed: 26 },
  { day: "Sun", screenings: 29, reviewed: 24 },
]

export const demoMetrics = {
  screeningSessions: 128,
  awaitingReview: 18,
  safetyChecks: 42,
  dataQualityPercent: 94,
}
