import type {
  C3CandidatePackage,
  Candidate,
  Component2Output,
  RiskTier,
} from "@/lib/api/types"

/**
 * Projects a Component 2 output onto the Component 3 candidate-package
 * contract (component3/app/models/c2_input.py).
 *
 * The two services were built separately and their contracts differ. Every
 * transformation is listed in `notes` so the UI can show it; nothing
 * clinical is invented here (no dose, no botanical name, no new rationale).
 */

export type C3PackageBuild = {
  package: C3CandidatePackage
  excluded: { candidateId: string; reason: string }[]
  notes: string[]
}

const tierLabel: Record<RiskTier, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
}

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value))
}

export function buildC3Package(
  output: Component2Output,
  options: { caseId: string; candidateIds: string[] },
): C3PackageBuild {
  const selected = new Set(options.candidateIds)
  const excluded: C3PackageBuild["excluded"] = []
  const notes: string[] = []
  let clamped = false

  const candidates = output.candidates
    .filter((candidate) => selected.has(candidate.candidate_id))
    .filter((candidate: Candidate) => {
      if (!candidate.name) {
        // Component 3 matches its rules on the candidate name, so an unnamed
        // candidate would silently produce no findings.
        excluded.push({
          candidateId: candidate.candidate_id,
          reason: "No display name in the Component 2 output; Component 3 matches rules by name.",
        })
        return false
      }
      return true
    })
    .map((candidate) => {
      const score = clamp01(candidate.ranking.score)
      if (score !== candidate.ranking.score) clamped = true
      return {
        id: candidate.candidate_id,
        name: candidate.name as string,
        category: candidate.category,
        reasoning_score: score,
        rationale:
          candidate.rationale.map((statement) => statement.text).join(" ") ||
          "No rationale statements supplied by Component 2.",
        evidence_ids: Array.from(
          new Set([
            ...candidate.supporting_evidence_ids,
            ...candidate.contradicting_evidence_ids,
          ]),
        ),
      }
    })

  const interpretation =
    output.interpretation
      .map((concept) => `${concept.name ?? concept.concept_id} (${concept.concept_type})`)
      .join("; ") || "No Ayurvedic interpretation produced by Component 2"

  notes.push(
    "reasoning_score carries the Component 2 experimental ranking score; it is not clinical confidence.",
  )
  if (clamped) {
    notes.push(
      "One or more ranking scores were outside 0–1 and were clamped because Component 3 only accepts 0–1.",
    )
  }
  notes.push("rationale joins the Component 2 rationale statements into one text field.")
  notes.push("No dose or botanical name is sent: Component 2 does not provide them.")

  return {
    package: {
      case_id: options.caseId,
      anemia_risk_tier: tierLabel[output.upstream.risk_tier],
      // Null only reaches here if the caller skipped the guard in runSafety.
      anemia_confidence: output.upstream.calibrated_confidence ?? Number.NaN,
      ayurvedic_interpretation: interpretation,
      symptom_summary: output.symptom_mappings
        .filter((mapping) => mapping.found)
        .map((mapping) => mapping.name ?? mapping.symptom_id),
      candidates,
      metadata: {
        source: "component2",
        c2_request_id: output.request_id,
        c2_schema_version: output.schema_version,
        c2_sufficiency_status: output.sufficiency_status,
        c2_abstained: output.abstention.abstain,
      },
    },
    excluded,
    notes,
  }
}
