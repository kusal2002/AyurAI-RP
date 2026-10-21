/**
 * TypeScript mirrors of the backend Pydantic schemas.
 *
 * Component 2: component2/app/models/{c1_input,c2_output,c3_handoff,feedback}.py
 * Component 3: component3/app/models/{c2_input,patient_context,safety_output}.py
 *
 * Keep these in sync with the backend; the frontend does not add fields the
 * services do not return.
 */

// ---------------------------------------------------------------------------
// Shared / Component 1 intake (as accepted by Component 2)
// ---------------------------------------------------------------------------

export type RiskTier = "low" | "moderate" | "high"

/** POST /api/v1/c1/screening-result (Component 2 service) - validation/echo only. */
export type C1Input = {
  case_id: string
  risk_tier: RiskTier
  /** Nullable upstream metadata (backend C1Input). */
  calibrated_confidence: number | null
  symptom_summary: string[]
  derived_context: Record<string, unknown>
}

export type C1IntakeResponse = {
  status: string
  message: string
  data: C1Input
}

// ---------------------------------------------------------------------------
// Component 2 reasoning
// ---------------------------------------------------------------------------

export type Component2ReasoningRequest = {
  request_id?: string
  risk_tier: RiskTier
  /** Nullable upstream metadata (backend Component2ReasoningRequest). */
  calibrated_confidence: number | null
  symptom_ids: string[]
}

export type SufficiencyStatus =
  | "sufficient_for_review"
  | "insufficient_evidence"
  | "conflicting_evidence"
  | "unverified_claims"
  | "out_of_scope"

export type CandidateCategory = "Herb" | "Formulation" | "Diet" | "Lifestyle"

export type CandidateDisposition =
  | "forward_for_safety_assessment"
  | "withheld_pending_review"

export type VerificationStatus =
  | "unverified"
  | "literature_supported"
  | "practitioner_verified"
  | "disputed"

export type EvidenceRelationship = "SUPPORTS" | "CONTRADICTS"

/**
 * Knowledge scope (c2-output/0.3.0). "approved" (default) reads human-approved
 * claims only; "approved_and_provisional" is research mode, which also reads
 * unverified AI-assisted draft claims. Provisional items are always labelled
 * and can never make a candidate sufficient.
 */
export type KnowledgeScope = "approved" | "approved_and_provisional"
export type KnowledgeStatus = "approved" | "provisional"

/** Request-level decision (FR9); always a decision for practitioner review. */
export type C2Decision = "recommend_for_review" | "caution" | "abstain"

export type RiskRule = "upstream_high_risk" | "upstream_confidence_missing" | "upstream_low_confidence"

/** Upstream risk gating. Never changes ranking, sufficiency or dispositions. */
export type RiskContext = {
  risk_tier: RiskTier
  calibrated_confidence: number | null
  rules_triggered: RiskRule[]
  escalation: string[]
  policy_id: string
}

export type UpstreamScreeningMetadata = {
  risk_tier: RiskTier
  /** Null when Component 1 supplied no calibrated confidence. */
  calibrated_confidence: number | null
}

export type EvidenceReference = {
  evidence_id: string
  relationship: EvidenceRelationship
  title: string | null
  source_name: string | null
  evidence_type: string | null
  section: string | null
  page: string | null
  citation: string | null
  source_url: string | null
  /** Set for evidence promoted from the source corpus (Stage E). */
  source_id?: string | null
  /** Source-text chunk the quoted sentence came from. */
  source_chunk_id?: string | null
  practitioner_verified: boolean
  provenance_complete: boolean
  missing_provenance: string[]
  /** Added in 0.3.0: approved or provisional (research scope only). */
  knowledge_status?: KnowledgeStatus | null
  /** claim_support | translation_support | modern_reference (provisional evidence). */
  evidence_role?: string | null
}

export type ClaimStep = {
  claim_id: string
  subject_id: string
  subject_type: string | null
  predicate: string
  object_id: string
  object_type: string | null
  statement: string | null
  /** Backend sends a string; usually one of VerificationStatus. */
  verification_status: string
  stored_confidence: number | null
  supporting_evidence: EvidenceReference[]
  contradicting_evidence: EvidenceReference[]
  evidence_lookup_failed: boolean
  retrieval_similarity: number | null
  /** Added in 0.3.0. Absent from older outputs: treat as approved. */
  knowledge_status?: KnowledgeStatus
  claim_category?: string | null
  uncertainty_notes?: string[]
  /** Modern reference statements that qualify (not support) a provisional claim. */
  qualifying_evidence?: EvidenceReference[]
}

export type CandidatePath = {
  concept_ids: string[]
  claims: ClaimStep[]
}

export type RankingBreakdown = {
  score: number
  components: Record<string, number>
  policy_id: string
  label: "experimental_ranking_score_not_clinical_confidence"
}

export type SufficiencyAssessment = {
  status: SufficiencyStatus
  review_required: boolean
  uncertainty_flags: string[]
  evidence_gaps: string[]
  policy_id: string
}

export type ExplanationStatement = {
  kind: string
  text: string
  claim_ids: string[]
  evidence_ids: string[]
}

export type Candidate = {
  candidate_id: string
  category: CandidateCategory
  name: string | null
  rank: number
  ranking: RankingBreakdown
  disposition: CandidateDisposition
  paths: CandidatePath[]
  claim_ids: string[]
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  verification_statuses: string[]
  conflict_flags: string[]
  sufficiency: SufficiencyAssessment
  rationale: ExplanationStatement[]
}

export type SymptomMapping = {
  symptom_id: string
  found: boolean
  name: string | null
  indicates_claim_ids: string[]
  message: string | null
}

export type InterpretedConcept = {
  concept_id: string
  concept_type: string
  name: string | null
  via_claim_ids: string[]
  verification_statuses: string[]
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
}

export type RejectedPath = {
  concept_ids: string[]
  claim_ids: string[]
  reason: string
}

export type RetrievedEvidenceItem = {
  chunk_id: string
  evidence_id: string
  similarity: number
  below_threshold: boolean
  linked_to_traversed_claim: boolean
  title: string | null
  source_name: string | null
  evidence_type: string | null
  section: string | null
  page: string | null
  citation: string | null
  source_url: string | null
  source_id?: string | null
  source_chunk_id?: string | null
  knowledge_status?: KnowledgeStatus | null
  evidence_role?: string | null
}

export type RetrievalInfo = {
  mode: "neural_embedding" | "unavailable" | "not_run"
  model_id: string | null
  query_count: number
  top_k: number | null
  min_similarity: number | null
  indexed_chunks: number
  error: string | null
}

export type Abstention = {
  abstain: boolean
  reasons: string[]
  explanation: string | null
}

export type Component2Output = {
  schema_version: string
  request_id: string
  generated_at: string
  /** Added in c2-output/0.3.0; absent means approved. */
  knowledge_scope?: KnowledgeScope
  upstream: UpstreamScreeningMetadata
  input_symptom_ids: string[]
  symptom_mappings: SymptomMapping[]
  interpretation: InterpretedConcept[]
  candidates: Candidate[]
  rejected_paths: RejectedPath[]
  retrieval: RetrievalInfo
  retrieved_evidence: RetrievedEvidenceItem[]
  sufficiency_status: SufficiencyStatus
  /** Added in c2-output/0.2.0. */
  decision: C2Decision
  decision_reasons: string[]
  risk_context: RiskContext
  uncertainty_flags: string[]
  evidence_gaps: string[]
  review_required: boolean
  abstention: Abstention
  explanation: ExplanationStatement[]
  traversal_truncated: boolean
  limitations: string[]
  score_semantics: Record<string, string>
  medical_conclusion: null
}

// ---------------------------------------------------------------------------
// Component 2 practitioner feedback
// ---------------------------------------------------------------------------

export type ReviewOutcome = "agree" | "disagree" | "needs_more_evidence" | "uncertain"

export type IssueCategory =
  | "none"
  | "missing_evidence"
  | "contradicting_evidence"
  | "incorrect_relationship"
  | "incorrect_concept_mapping"
  | "provenance_problem"
  | "source_misinterpreted"
  | "out_of_scope"
  | "other"

export type ReviewerRole = "ayurvedic_practitioner" | "researcher" | "supervisor"

export type PractitionerFeedbackRequest = {
  feedback_id?: string
  request_id: string
  claim_ids: string[]
  candidate_ids: string[]
  evidence_ids: string[]
  review_outcome: ReviewOutcome
  issue_category: IssueCategory
  rationale: string
  refinement_terms: string[]
  suggested_concept_ids: string[]
  reviewer_role: ReviewerRole
  reviewer_ref: string
}

export type FeedbackRetrieval = {
  mode: "neural_embedding" | "unavailable" | "not_run"
  model_id?: string | null
  results: Array<Record<string, unknown>>
  error: string | null
}

export type PractitionerFeedbackResponse = {
  status: "recorded"
  feedback_id: string
  linked_claim_ids: string[]
  unknown_claim_ids: string[]
  claims_modified: false
  refinement_query: {
    feedback_id: string
    query_text: string | null
    terms: string[]
    concept_ids: string[]
    unknown_concept_ids: string[]
  }
  refinement_retrieval: FeedbackRetrieval
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export type HealthResponse = {
  status: string
  service?: string
  version?: string
}

// ---------------------------------------------------------------------------
// Component 1 screening payload -> Component 2 (POST /api/v1/c1/reasoning)
// ---------------------------------------------------------------------------

/** Provisional Component 1 output contract (component2/app/models/c1_screening_payload.py). */
export type C1ScreeningPayload = {
  screening_id: string
  session_id: string
  screening_result: {
    condition: string
    risk_level: string
    screening_confidence: number | null
    evidence_strength: string
    status: string
    requires_clinician_review: boolean
  }
  hemoglobin: {
    estimated_g_dl: number | null
    measured_lab_g_dl: number | null
    source: string
    clinically_validated: boolean
  }
  modality_results: Record<string, unknown>
  symptoms: { name: string; present: boolean }[]
  clinical_findings: Record<string, unknown>[]
  contributing_factors: string[]
  missing_data: string[]
  recommendation: string
  model_version: string
  disclaimer: string
}

export type C1SymptomMapping = {
  status: "ready" | "blocked" | "insufficient_input"
  reason: string | null
  resolved_symptoms: { input_name: string; symptom_id: string; canonical_name: string }[]
  unresolved_symptoms: { input_name: string; status: string; candidate_ids?: string[] }[]
}

export type C1ReasoningResponse = {
  status: "completed" | "blocked" | "insufficient_input"
  screening_id: string
  mapping: C1SymptomMapping
  reasoning: Component2Output | null
}
export type Neo4jHealthResponse = {
  status: string
  database: string
  connected: boolean
  /** healthy | not_configured | misconfigured | auth_failed | unreachable | query_failed */
  reason?: string
  detail?: string
  encrypted?: boolean | null
}

/** GET /health/readiness: each concern is reported separately. */
export type ReadinessComponent = { status: string; detail?: string }

export type ReadinessResponse = {
  service: string
  generated_at: string
  ready_for_reasoning: boolean
  knowledge_available: boolean
  components: {
    database_connectivity: ReadinessComponent & { encrypted?: boolean | null }
    graph_schema: ReadinessComponent & { missing_core_constraints?: string[]; stage_e_applied?: boolean }
    knowledge_graph_content: ReadinessComponent & { node_counts?: Record<string, number>; note?: string }
    local_corpus_ingestion: ReadinessComponent & {
      sources?: number
      processed?: number
      needs_ocr_or_review?: number
      rejected?: number
      candidate_claims?: number
      approved_candidates?: number
      with_curated_metadata?: number
      note?: string
    }
    retrieval_service: ReadinessComponent & {
      indexed_evidence?: number | null
      indexed_chunks?: number | null
      last_error?: string | null
    }
    embedding_model: { model_id: string; loaded: boolean; cached_locally: boolean | null }
    component_integration: Record<string, string>
  }
  notes: string[]
}

// ---------------------------------------------------------------------------
// Component 3 safety
// ---------------------------------------------------------------------------

export type C3CandidateItem = {
  id: string
  name: string
  category: string
  botanical_name?: string | null
  /** Never filled by the frontend: no dosage is generated client-side. */
  dose?: string | null
  reasoning_score: number
  rationale: string
  evidence_ids: string[]
}

export type C3CandidatePackage = {
  case_id: string
  anemia_risk_tier: string
  anemia_confidence: number
  ayurvedic_interpretation: string
  symptom_summary: string[]
  candidates: C3CandidateItem[]
  metadata?: Record<string, unknown>
}

export type MedicationItem = {
  name: string
  drug_class?: string | null
  dosage?: string | null
  route?: string | null
}

export type OrganFunction = {
  egfr?: number | null
  ckd_stage?: string | null
  hepatic_impairment?: string | null
  serum_creatinine?: number | null
}

export type PatientContext = {
  patient_id: string
  age: number
  gender: string
  pregnancy_status: boolean
  pregnancy_trimester?: number | null
  lactation_status: boolean
  current_medications: MedicationItem[]
  comorbidities: string[]
  allergies: string[]
  organ_function: OrganFunction
  polypharmacy: boolean
}

export type C2SafetyEvaluationRequest = {
  candidate_package: C3CandidatePackage
  patient_context: PatientContext
}

export type SafetyClassification = "Low Risk" | "Caution" | "High Risk"
export type EvidenceGrade = "Established" | "Probable" | "Possible" | "Insufficient"

export type EvidenceProvenance = {
  source_id: string
  source_title: string
  citation_type: string
  pmid_or_ref: string | null
  grade: EvidenceGrade
}

export type InteractionFinding = {
  herb_or_constituent: string
  target_drug: string
  interaction_type: string
  severity: string
  mechanism: string
  evidence_strength: EvidenceGrade
  prediction_confidence: number
  source_refs: EvidenceProvenance[]
}

export type TitrationGuidance = {
  recommended_dose_adjustment: string | null
  separation_window: string | null
  duration_limit: string | null
}

export type SurveillanceGuidance = {
  lab_monitoring: string[]
  clinical_signs_to_watch: string[]
}

export type EvaluatedCandidateSafety = {
  candidate_id: string
  candidate_name: string
  safety_tier: SafetyClassification
  confidence: number
  summary_warning: string
  interaction_findings: InteractionFinding[]
  contraindications_triggered: string[]
  patient_risk_modifiers: string[]
  titration_plan: TitrationGuidance | null
  surveillance: SurveillanceGuidance | null
  escalate_to_practitioner: boolean
}

export type SafetyAssessmentReport = {
  assessment_id: string
  case_id: string
  patient_id: string
  timestamp: string
  overall_safety_tier: SafetyClassification
  highest_severity_finding: string | null
  evaluations: EvaluatedCandidateSafety[]
  practitioner_review_required: boolean
  metadata: Record<string, unknown>
}

// Component 3 reference data (GET /api/v1/safety/*) - JSON files served as-is.
export type C3Herb = {
  id: string
  common_name: string
  sanskrit_name?: string | null
  botanical_name: string
  active_compounds: string[]
  contraindications: string[]
  traditional_uses: string[]
}

export type C3Drug = {
  id: string
  generic_name: string
  brand_names: string[]
  drug_class: string
  metabolizing_enzymes: string[]
  target_receptors: string[]
  narrow_therapeutic_index: boolean
}

export type C3KnownInteraction = {
  id: string
  herb: string
  drug: string
  severity: string
  interaction_type: string
  mechanism: string
  evidence_level: string
  pmid?: string | null
  citation?: string | null
  recommended_action?: string | null
}

export type C3CypPathway = {
  enzyme: string
  description: string
  substrates: string[]
  inhibitors: string[]
  inducers: string[]
}

// ---------------------------------------------------------------------------
// Provisional research knowledge (GET /api/v1/c2/research/knowledge)
// ---------------------------------------------------------------------------

export type ResearchEvidence = {
  evidence_id: string
  text?: string | null
  citation?: string | null
  source_id?: string | null
  source_name?: string | null
  evidence_role?: string | null
  evidence_type?: string | null
  source_language?: string | null
  licence_note?: string | null
  category?: string | null
  topics?: string[] | null
}

export type ResearchClaim = {
  claim_id: string
  claim_key?: string | null
  claim_category?: string | null
  subject_id: string
  predicate: string
  object_id: string
  statement?: string | null
  verification_status: string
  review_status?: string | null
  uncertainty_notes?: string[] | null
  dataset_id?: string | null
}

export type ResearchClaimRow = {
  claim: ResearchClaim
  subject_name: string
  subject_type: string | null
  object_name: string
  object_type: string | null
  evidence: ResearchEvidence[]
  qualifying_evidence: ResearchEvidence[]
}

export type ResearchKnowledgeResponse = {
  knowledge_status: "provisional"
  notice: string
  claims: ResearchClaimRow[]
  reference_evidence: ResearchEvidence[]
}
