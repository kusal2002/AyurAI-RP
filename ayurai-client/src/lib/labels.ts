/**
 * Human-readable labels for backend codes. The raw code is always shown
 * alongside these labels where precision matters.
 */

const flagLabels: Record<string, string> = {
  semantic_retrieval_unavailable: "Semantic retrieval was unavailable",
  semantic_retrieval_not_assessed: "Semantic retrieval was not assessed",
  retrieval_below_threshold: "Evidence similarity below the retrieval threshold",
  retrieved_evidence_not_linked_to_claims: "Retrieved evidence is not linked to traversed claims",
  ontology_invalid_paths_rejected: "Some graph paths were rejected by ontology validation",
  traversal_truncated: "Graph traversal was truncated at its limits",
  unmapped_symptom_ids: "Some supplied symptom IDs were not found",
  claim_without_supporting_evidence: "A claim has no supporting evidence",
  contradicting_evidence_only: "Only contradicting evidence for a claim",
  supporting_and_contradicting_evidence: "Both supporting and contradicting evidence",
  disputed_claim: "A claim is marked disputed",
  incomplete_provenance: "Evidence provenance is incomplete",
  unverified_only: "Only unverified claims",
  multiple_paths: "Multiple reasoning paths reach this candidate",
  paths_disagree: "Reasoning paths disagree",
  some_paths_not_sufficient: "Some paths do not meet the sufficiency policy",
  no_supplied_symptom_mapped_to_stored_concept: "No supplied symptom matched a stored concept",
  no_valid_candidate_path_found: "No valid candidate path was found",
  no_candidate_sufficient_for_review: "No candidate met the sufficiency policy",
  safety_assessment_not_available: "No Component 3 safety assessment is available",
}

const prefixLabels: Record<string, string> = {
  no_supporting_evidence: "No supporting evidence for claim",
  incomplete_provenance: "Incomplete provenance for",
  evidence_lookup_failed: "Evidence lookup failed for claim",
  missing_concept: "Missing concept",
  ambiguous_concept_type: "Ambiguous concept type",
  dominant_candidate_status: "Dominant candidate status",
  unmapped: "Symptom ID not found",
  escalation: "Component 3 escalation for",
}

export function humanizeCode(code: string): string {
  const spaced = code.replace(/_/g, " ")
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** Describe a flag such as `no_supporting_evidence:CL-1`. */
export function describeFlag(flag: string): { label: string; target?: string } {
  if (flagLabels[flag]) return { label: flagLabels[flag] }
  const separator = flag.indexOf(":")
  if (separator > 0) {
    const prefix = flag.slice(0, separator)
    const target = flag.slice(separator + 1)
    return { label: prefixLabels[prefix] ?? humanizeCode(prefix), target }
  }
  return { label: humanizeCode(flag) }
}

export const conceptTypeLabels: Record<string, string> = {
  Symptom: "Symptom",
  Roga: "Roga (disease concept)",
  Dosha: "Dosha",
  Dhatu: "Dhatu",
  TherapeuticPrinciple: "Therapeutic principle",
  Herb: "Herb",
  Formulation: "Formulation",
  Diet: "Diet",
  Lifestyle: "Lifestyle",
}

export const predicateLabels: Record<string, string> = {
  INDICATES: "indicates",
  ASSOCIATED_WITH_DOSHA: "associated with Dosha",
  AFFECTS_DHATU: "affects Dhatu",
  SUGGESTS_PRINCIPLE: "suggests principle",
  USES_HERB: "uses herb",
  USES_FORMULATION: "uses formulation",
  RECOMMENDS_DIET: "recommends diet",
  RECOMMENDS_LIFESTYLE: "recommends lifestyle",
}

export const evidenceTypeLabels: Record<string, string> = {
  classical: "Classical text",
  modern_research: "Modern research",
  clinical_guideline: "Clinical guideline",
  practitioner: "Practitioner knowledge",
}

export const rankingComponentLabels: Record<string, string> = {
  status: "Verification status",
  support: "Independent support",
  contradiction: "Contradiction penalty",
  provenance: "Provenance penalty",
  retrieval: "Claim–evidence retrieval",
}

export function formatDateTime(value: string | number | Date): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function formatScore(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return value.toFixed(digits)
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}
