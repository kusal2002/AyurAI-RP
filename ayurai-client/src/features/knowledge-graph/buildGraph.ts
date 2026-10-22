import type { ClaimStep, Component2Output } from "@/lib/api/types"
import { conceptNames, indexClaims, matchedRogaTypes } from "@/lib/c2-derive"

/**
 * Builds a graph strictly from relationships present in the Component 2
 * output: each edge is a claim the reasoning traversed, either on a candidate
 * path or (c2-output/0.5.0+) in `interpretation_claims`. No edges are
 * inferred. Older outputs omit off-path claims, so some concepts may appear
 * as nodes without edges.
 */

export type GraphNode = {
  id: string
  type: string | null
  name: string | null
  column: number
  row: number
  isCandidate: boolean
  isInterpretation: boolean
  isSymptom: boolean
  /** Parent Roga ID when this node is a Roga type (e.g. Pittaja Pandu). */
  subtypeOf: string | null
}

export type GraphEdge = {
  id: string
  claim: ClaimStep
  source: string
  target: string
  candidateIds: string[]
  /** False for a traversed claim that leads to no candidate. */
  onCandidatePath: boolean
}

export type ReasoningGraph = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  columns: number
  maxRows: number
  isolatedNodeIds: string[]
}

const columnByType: Record<string, number> = {
  Symptom: 0,
  Roga: 1,
  Dosha: 2,
  Dhatu: 2,
  TherapeuticPrinciple: 3,
  Herb: 4,
  Formulation: 4,
  Diet: 4,
  Lifestyle: 4,
}

export const columnTitles = ["Symptoms", "Roga", "Dosha / Dhatu", "Therapeutic principles", "Candidates"]

export function buildGraph(output: Component2Output): ReasoningGraph {
  const names = conceptNames(output)
  const claims = indexClaims(output)
  const types = new Map<string, string | null>()
  const nodeIds = new Set<string>()

  const rogaTypes = matchedRogaTypes(output)
  const candidateIds = new Set(output.candidates.map((candidate) => candidate.candidate_id))
  const interpretationIds = new Set(output.interpretation.map((concept) => concept.concept_id))
  const symptomIds = new Set(
    output.symptom_mappings.filter((mapping) => mapping.found).map((mapping) => mapping.symptom_id),
  )

  for (const id of symptomIds) {
    nodeIds.add(id)
    types.set(id, "Symptom")
  }
  for (const concept of output.interpretation) {
    nodeIds.add(concept.concept_id)
    types.set(concept.concept_id, concept.concept_type)
  }
  for (const candidate of output.candidates) {
    nodeIds.add(candidate.candidate_id)
    types.set(candidate.candidate_id, candidate.category)
  }

  const edges: GraphEdge[] = []
  for (const { claim, candidateIds: usedBy } of claims.values()) {
    nodeIds.add(claim.subject_id)
    nodeIds.add(claim.object_id)
    if (!types.get(claim.subject_id)) types.set(claim.subject_id, claim.subject_type)
    if (!types.get(claim.object_id)) types.set(claim.object_id, claim.object_type)
    edges.push({
      id: claim.claim_id,
      claim,
      source: claim.subject_id,
      target: claim.object_id,
      candidateIds: usedBy,
      onCandidatePath: usedBy.length > 0,
    })
  }

  const columnOf = (id: string) => {
    const type = types.get(id)
    return type && type in columnByType ? columnByType[type] : 2
  }

  const byColumn = new Map<number, string[]>()
  for (const id of nodeIds) {
    const column = columnOf(id)
    byColumn.set(column, [...(byColumn.get(column) ?? []), id])
  }

  const nodes: GraphNode[] = []
  let maxRows = 0
  for (const [column, ids] of byColumn) {
    ids.sort((a, b) => {
      const typeCompare = (types.get(a) ?? "").localeCompare(types.get(b) ?? "")
      return typeCompare || (names.get(a) ?? a).localeCompare(names.get(b) ?? b)
    })
    maxRows = Math.max(maxRows, ids.length)
    ids.forEach((id, row) =>
      nodes.push({
        id,
        type: types.get(id) ?? null,
        name: names.get(id) ?? null,
        column,
        row,
        isCandidate: candidateIds.has(id),
        isInterpretation: interpretationIds.has(id),
        isSymptom: symptomIds.has(id),
        subtypeOf: rogaTypes.get(id)?.parentId || null,
      }),
    )
  }

  const connected = new Set(edges.flatMap((edge) => [edge.source, edge.target]))
  return {
    nodes,
    edges,
    columns: columnTitles.length,
    maxRows,
    isolatedNodeIds: nodes.filter((node) => !connected.has(node.id)).map((node) => node.id),
  }
}
