import type {
  Candidate,
  CandidateCategory,
  ClaimStep,
  Component2Output,
  EvidenceReference,
  RetrievedEvidenceItem,
} from "@/lib/api/types"

/**
 * Read-only indexes over a Component 2 output. These only regroup fields the
 * service returned; they never infer new relationships or scores.
 */

export type ClaimIndexEntry = {
  claim: ClaimStep
  candidateIds: string[]
}

export type EvidenceUsage = {
  claimId: string
  relationship: EvidenceReference["relationship"]
  candidateIds: string[]
}

export type EvidenceIndexEntry = {
  evidenceId: string
  /** Metadata from the first reference seen; references share evidence metadata. */
  reference: EvidenceReference
  usages: EvidenceUsage[]
  interpretationConceptIds: string[]
  retrievalHits: RetrievedEvidenceItem[]
}

export function indexClaims(output: Component2Output): Map<string, ClaimIndexEntry> {
  const claims = new Map<string, ClaimIndexEntry>()
  for (const candidate of output.candidates) {
    for (const path of candidate.paths) {
      for (const claim of path.claims) {
        const entry = claims.get(claim.claim_id)
        if (entry) {
          if (!entry.candidateIds.includes(candidate.candidate_id)) {
            entry.candidateIds.push(candidate.candidate_id)
          }
        } else {
          claims.set(claim.claim_id, { claim, candidateIds: [candidate.candidate_id] })
        }
      }
    }
  }
  // Claims the reasoning traversed that lead to no candidate (used by no candidate).
  for (const claim of output.interpretation_claims ?? []) {
    if (!claims.has(claim.claim_id)) claims.set(claim.claim_id, { claim, candidateIds: [] })
  }
  return claims
}

/** Roga types (e.g. Pittaja Pandu) reached from the patient's symptoms, keyed by ID. */
export function matchedRogaTypes(output: Component2Output) {
  const types = new Map<string, { id: string; name: string | null; parentId: string; candidateIds: string[] }>()
  for (const concept of output.interpretation) {
    if (concept.concept_type === "Roga" && concept.subtype_of) {
      types.set(concept.concept_id, { id: concept.concept_id, name: concept.name, parentId: concept.subtype_of, candidateIds: [] })
    }
  }
  for (const candidate of output.candidates) {
    for (const id of candidate.matched_subtypes ?? []) {
      const type = types.get(id)
      if (type) type.candidateIds.push(candidate.candidate_id)
      else types.set(id, { id, name: null, parentId: "", candidateIds: [candidate.candidate_id] })
    }
  }
  return types
}

export function indexEvidence(output: Component2Output): Map<string, EvidenceIndexEntry> {
  const evidence = new Map<string, EvidenceIndexEntry>()
  const claims = indexClaims(output)

  for (const { claim, candidateIds } of claims.values()) {
    for (const reference of [...claim.supporting_evidence, ...claim.contradicting_evidence]) {
      let entry = evidence.get(reference.evidence_id)
      if (!entry) {
        entry = {
          evidenceId: reference.evidence_id,
          reference,
          usages: [],
          interpretationConceptIds: [],
          retrievalHits: [],
        }
        evidence.set(reference.evidence_id, entry)
      }
      entry.usages.push({ claimId: claim.claim_id, relationship: reference.relationship, candidateIds })
    }
  }

  for (const concept of output.interpretation) {
    for (const id of [...concept.supporting_evidence_ids, ...concept.contradicting_evidence_ids]) {
      evidence.get(id)?.interpretationConceptIds.push(concept.concept_id)
    }
  }

  for (const hit of output.retrieved_evidence) {
    evidence.get(hit.evidence_id)?.retrievalHits.push(hit)
  }

  return evidence
}

/** Display names supplied by the service (symptoms, interpretation, candidates). */
export function conceptNames(output: Component2Output): Map<string, string> {
  const names = new Map<string, string>()
  for (const mapping of output.symptom_mappings) {
    if (mapping.name) names.set(mapping.symptom_id, mapping.name)
  }
  for (const concept of output.interpretation) {
    if (concept.name) names.set(concept.concept_id, concept.name)
  }
  for (const candidate of output.candidates) {
    if (candidate.name) names.set(candidate.candidate_id, candidate.name)
  }
  return names
}

export function evidenceCounts(output: Component2Output) {
  const index = indexEvidence(output)
  let supporting = 0
  let contradicting = 0
  for (const entry of index.values()) {
    if (entry.usages.some((usage) => usage.relationship === "SUPPORTS")) supporting += 1
    if (entry.usages.some((usage) => usage.relationship === "CONTRADICTS")) contradicting += 1
  }
  return { total: index.size, supporting, contradicting }
}

export const CANDIDATE_CATEGORIES: CandidateCategory[] = ["Herb", "Formulation", "Diet", "Lifestyle"]

/**
 * The best candidate in each category (Herb, Formulation, Diet, Lifestyle).
 * Candidates arrive already ordered by the service (rank 1 first), so the
 * first one seen per category is that category's top-ranked candidate.
 * Categories with no candidate are left out.
 */
export function topCandidatePerCategory(output: Component2Output): Candidate[] {
  const best = new Map<CandidateCategory, Candidate>()
  for (const candidate of [...output.candidates].sort((a, b) => a.rank - b.rank)) {
    if (!best.has(candidate.category)) best.set(candidate.category, candidate)
  }
  return CANDIDATE_CATEGORIES.flatMap((category) => {
    const candidate = best.get(category)
    return candidate ? [candidate] : []
  })
}
