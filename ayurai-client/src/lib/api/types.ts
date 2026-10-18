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
  calibrated_confidence: number
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
  calibrated_confidence: number
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

export type UpstreamScreeningMetadata = {
  risk_tier: RiskTier
  calibrated_confidence: number
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
  practitioner_verified: boolean
  provenance_complete: boolean
  missing_provenance: string[]
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
  upstream: UpstreamScreeningMetadata
  input_symptom_ids: string[]
  symptom_mappings: SymptomMapping[]
  interpretation: InterpretedConcept[]
  candidates: Candidate[]
  rejected_paths: RejectedPath[]
  retrieval: RetrievalInfo
  retrieved_evidence: RetrievedEvidenceItem[]
  sufficiency_status: SufficiencyStatus
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

export type HealthResponse = { status: string; service?: string; version?: string }
export type Neo4jHealthResponse = { status: string; database: string; connected: boolean }

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
