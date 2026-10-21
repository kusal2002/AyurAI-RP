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

/** Component 1 API responses are preserved as raw JSON because the research
 * report schema is owned by Component 1 and must not be reconstructed here. */
export type Component1Json = Record<string, unknown>

export type Component1HealthResponse = Component1Json
export type Component1Session = Component1Json & {
  session_id?: string
  created_utc?: string | null
  questionnaire_available?: boolean
  image_count?: number
  ppg_available?: boolean
  record_saved?: boolean
  risk_level?: string | null
  workflow_state?: C1WorkflowState
  analysis_outdated?: boolean
}
/** GET /api/c1/sessions wraps the list in an object. */
export type Component1SessionsResponse = { sessions?: Component1Session[] }

/** Component 1 clinical intake (fictional demo sessions only). */
export type C1Question = {
  id: string
  prompt: string
  type: string
  options: string[] | null
  section: string
}

export type C1QuestionSet = {
  version: string
  approval_status?: string
  common: C1Question[]
  pregnancy_safety: C1Question
  safety_ids: string[]
  ppg_comfort: C1Question[]
}

export type C1Profile = { age_months: number; sex: string; pregnancy_status: string }

export type C1Answers = Record<string, string | number>

export type C1QuestionnaireBody = {
  profile: C1Profile
  consent: boolean
  consent_ppg: boolean
  consent_images: boolean
  guardian_permission: boolean
  answers: C1Answers
  medications: string
  herbals: string
  allergies: string
  no_medications: boolean
  no_allergies: boolean
}

export type C1CaptureStatus = {
  image_acquisition_allowed?: boolean
  ppg_acquisition_allowed?: boolean
  ppg_pending_finger_comfort_check?: boolean
  ppg_comfort_blocking_ids?: string[]
  ppg_optical_obstruction_reported?: boolean
  urgent_clinician_review?: boolean
}

export type C1CaptureCounts = Record<"conjunctiva" | "nails" | "tongue", number>

export type C1SerialPorts = {
  configured_port: string
  configured_baud: number
  ports: { device: string; description: string }[]
  /** Windows lists the port. Says nothing about whether valid samples arrive. */
  port_listed: boolean
  /** False when the server does not record from a USB sensor (C1_SERIAL_ENABLED=false); absent on older APIs. */
  serial_enabled?: boolean
}

/** Which PPG capture paths the Component 1 server offers. */
export type C1PpgCaptureOptions = {
  server_serial_enabled: boolean
  /** Browser Web Serial capture + upload (C1_PPG_UPLOAD_ENABLED). */
  browser_upload_enabled: boolean
  baud: number
  min_seconds: number
  max_seconds: number
}

/** One browser-captured recording, in the CSV format of capture_live_ppg.py. */
export type C1PpgUploadBody = {
  upload_id: string
  seconds: number
  samples_csv: string
  metrics_csv: string
}

export type C1RecordingResult = {
  session_id: string
  recording_id: number
  recording_file: string
  sample_count: number
  quality_status: string
  quality_passed: boolean
  quality_reasons: string[]
  observed_receive_rate_hz: number | null
  metrics_count: number
  finger_present_fraction: number | null
  median_experimental_hr_bpm: number | null
  median_experimental_spo2_percent: number | null
  median_temperature_c: number | null
  hb_model_applied: boolean
}

export type C1PpgJobState =
  | "idle"
  | "opening"
  | "port_open"
  | "receiving"
  | "processing"
  | "saved"
  | "failed"
  | "cancelled"
  | "probe_ok"

export type C1PpgJob = {
  job_id?: string
  kind?: "recording" | "probe"
  state: C1PpgJobState
  session_id?: string
  seconds?: number
  port?: string
  samples?: number
  metrics?: number
  elapsed_s?: number
  finger_present?: boolean | null
  last_hr_bpm?: number | null
  last_spo2_percent?: number | null
  error_kind?: string
  error?: string
  result?: C1RecordingResult | { valid_rows: number; rows_per_second: number; metrics: number; saved: false }
}

export type C1PpgJobStatus = C1SerialPorts & { job: C1PpgJob }

export type C1SavedRecording = {
  recording_id: number
  recording_file: string
  sample_count: number
  quality_status: string
  observed_receive_rate_hz: number | null
  saved_utc: string
}

export type C1WorkflowState =
  | "created"
  | "safety_referral"
  | "images_in_progress"
  | "ppg_in_progress"
  | "ready_for_analysis"
  | "completed"

/** One active webcam image; image_id is a file name, never a filesystem path. */
export type C1SavedImage = {
  image_id: string
  modality: keyof C1CaptureCounts
  captured_utc: string | null
  available: boolean
}

export type C1ImageChange = {
  images: C1SavedImage[]
  captures: C1CaptureCounts
}

export type C1IntakeState = {
  session_id: string
  created_utc: string | null
  workflow_state: C1WorkflowState
  questionnaire: null | {
    profile: { age_months?: number; sex_reported_for_demo?: string; sex?: string; pregnancy_status?: string }
    answers: Record<string, unknown>
    status: C1CaptureStatus
    completion_status: string
  }
  captures: C1CaptureCounts
  images?: C1SavedImage[]
  ppg_recordings: C1SavedRecording[]
  record_saved: boolean
}

export type C1ReferralBody = {
  profile: C1Profile
  consent: boolean
  consent_ppg: boolean
  consent_images: boolean
  guardian_permission: boolean
  answers: C1Answers
}

/** Read-only view of GET /api/c1/sessions/{id}/report. All fields optional: render defensively. */
export type C1EvidenceItem = {
  modality: string
  source: string
  task: string
  outputs: number
  mean_output: number | null
  evidence: number | null
  technical_pass_ratio: number | null
  performance_weight: number
  reliability_weight: number
  weight_basis: string
  note?: string
}

export type C1FusionBlock = {
  fusion_version?: string
  experimental_risk_tier?: string
  hb_threshold_g_dl?: number | null
  hb_threshold_basis?: string
  questionnaire_evidence?: {
    answered_items: number
    present_symptoms: string[]
    absent_symptoms: string[]
    symptom_fraction: number | null
    usable: boolean
  } | null
  evidence_items?: C1EvidenceItem[]
  conventional_fusion?: { method: string; votes: number; anaemia_vote_fraction: number | null; tier: string }
  reliability_aware_fusion?: {
    weighted_evidence_score: number | null
    reliability_score: number
    conflict_ratio: number
    usable_physiological_modalities: string[]
    excluded_sources: string[]
    insufficient_reasons: string[]
    tier: string
  }
  rationale?: string[]
  safety_flags?: string[]
  doctor_review_recommendations?: string[]
}

export type C1Region = {
  captures?: number
  technical_passes?: number
  technical_pass_ratio?: number
  cross_model_disagreement?: boolean
  model_votes?: unknown[]
  experimental_hb_estimates_g_dl?: unknown[]
}

export type Component1Report = {
  schema_version?: string
  session_id?: string
  /** "screening" (normal) or "safety_referral" (urgent safety answer: referral-only, no risk tier). */
  outcome?: "screening" | "safety_referral"
  workflow_state?: C1WorkflowState
  generated_utc?: string
  patient?: { age_months?: number | null; sex?: string | null; pregnancy_status?: string | null; fictional_demo?: boolean }
  workflow?: { key: string; label: string; status: string }[]
  questionnaire?: {
    available?: boolean
    completion_status?: string | null
    responses?: { question_id: string; question: string; section: string; answer: unknown }[]
  }
  referral?: {
    urgent_response_ids: string[]
    unresolved_safety_ids: string[]
    /** Safety questions still unanswered when the clinician referred. */
    not_asked_safety_ids?: string[]
    referred_utc: string | null
    reason: string
  }
  modalities?: {
    images?: { image_count?: number; regions?: Record<string, C1Region> }
    ppg?: {
      available?: boolean
      sample_count?: number
      observed_receive_rate_hz?: number
      quality_status?: string | null
      quality_windows_passed?: number
      quality_windows_checked?: number
      median_experimental_hr_bpm?: number | null
      median_experimental_spo2_percent?: number | null
      hb_model_applied?: boolean
    }
  }
  screening_result?: {
    risk_level?: string | null
    decision_status?: string
    reliability_score?: number | null
  }
  fusion?: C1FusionBlock
  missing_inputs?: string[]
  /** Images were added, removed or replaced after the last fusion: results below are outdated. */
  analysis_outdated?: boolean
  storage?: {
    folder: string
    record_saved: boolean
    record_saved_utc: string | null
    files: string[]
    image_files: number
    saved_images?: C1CaptureCounts
    ppg_recordings: number
  }
  doctor_report?: {
    summary?: string
    observations?: string[]
    recommendations?: string[]
    reliability_flags?: string[]
    limitations?: string[]
    clinical_action?: string
  }
}

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
  /** Botanical name as stated by a cited translation; not verified. */
  botanical_name?: string | null
  rank: number
  ranking: RankingBreakdown
  disposition: CandidateDisposition
  paths: CandidatePath[]
  claim_ids: string[]
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  verification_statuses: string[]
  conflict_flags: string[]
  /**
   * Added in c2-output/0.4.0: Roga types (e.g. Pittaja Pandu) matched from the
   * patient's symptoms on this candidate's paths. Such candidates are listed
   * before general remedies; the ranking score is unchanged. Absent in older outputs.
   */
  matched_subtypes?: string[]
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
export type C1ScreeningPayloadProvisional = {
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

/** Component 1 output `c1.screening.v1` (component2/app/models/c1_screening_v1.py). */
export type C1ScreeningPayloadV1 = {
  schema_version: "c1.screening.v1"
  screening_id: string
  session_id: string
  synthetic_fixture?: boolean
  screening_result: {
    risk_level: string
    /** Calibrated confidence 0–100; null when none is available. */
    confidence_percent: number | null
    /** Not calibrated: never used as a confidence. */
    experimental_reliability_score?: number | null
    clinician_review_required?: boolean
    contributing_factors?: string[]
  }
  /** Symptoms reported present. */
  symptoms: string[]
  questionnaire_status?: { urgent_clinician_review?: boolean }
  missing_modalities?: string[]
  [key: string]: unknown
}

export type C1ScreeningPayload = C1ScreeningPayloadProvisional | C1ScreeningPayloadV1

/** The values Component 2 reads, from either Component 1 format. */
export function c1View(payload: C1ScreeningPayload) {
  if ("schema_version" in payload && payload.schema_version === "c1.screening.v1") {
    const percent = payload.screening_result.confidence_percent
    return {
      riskLevel: payload.screening_result.risk_level,
      confidence: percent === null || percent === undefined ? null : percent / 100,
      symptoms: payload.symptoms.map((name) => ({ name: name.replace(/_/g, " "), present: true })),
      urgentReview: payload.questionnaire_status?.urgent_clinician_review === true,
      synthetic: payload.synthetic_fixture === true,
    }
  }
  const legacy = payload as C1ScreeningPayloadProvisional
  return {
    riskLevel: legacy.screening_result.risk_level,
    confidence: legacy.screening_result.screening_confidence,
    symptoms: legacy.symptoms,
    urgentReview: false,
    synthetic: false,
  }
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
  anemia_confidence: number | null
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
  source_url?: string | null
  excerpt?: string | null
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
  clinical_action?: string | null
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

export type C3GraphNode = {
  id: string
  name: string
  type: "Herb" | "Compound" | "Enzyme" | "Target" | "Drug" | "Condition"
  category?: string
  sanskrit_name?: string
  botanical_name?: string
  contraindications?: string[]
  traditional_uses?: string[]
  active_compounds?: string[]
  narrow_therapeutic_index?: boolean
  metabolizing_enzymes?: string[]
  target_receptors?: string[]
}

export type C3GraphEdge = {
  id: string
  source: string
  target: string
  type: string
  label: string
  severity: "High" | "Moderate" | "Low" | "Safe" | "Info" | string
  interaction_type?: string
  mechanism?: string
  evidence_level?: string
  pmid?: string
  citation?: string
  recommended_action?: string
}

export type C3GraphResponse = {
  mode: "live_neo4j" | "offline_fallback"
  total_nodes: number
  total_edges: number
  nodes: C3GraphNode[]
  edges: C3GraphEdge[]
  stats?: Record<string, unknown>
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
