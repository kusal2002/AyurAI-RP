import type {
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
  return claims
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
