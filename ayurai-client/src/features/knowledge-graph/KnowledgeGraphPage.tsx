import * as React from "react"
import { Network, X } from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { ClaimCard } from "@/components/shared/c2"
import { EmptyState, IdChip, KeyValueList, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, sufficiencySpec, verificationSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Component2Output } from "@/lib/api/types"
import { conceptNames } from "@/lib/c2-derive"
import { conceptTypeLabels, predicateLabels } from "@/lib/labels"
import { buildGraph, columnTitles, type GraphEdge, type GraphNode, type ReasoningGraph } from "./buildGraph"

const NODE_W = 172
const NODE_H = 48
const COL_GAP = 64
const ROW_GAP = 16
const PAD_X = 16
const PAD_TOP = 40

const typeColors: Record<string, { fill: string; stroke: string; text: string }> = {
  Symptom: { fill: "#f8fafc", stroke: "#94a3b8", text: "#334155" },
  Roga: { fill: "#ecfdf5", stroke: "#059669", text: "#065f46" },
  Dosha: { fill: "#f0fdfa", stroke: "#0d9488", text: "#115e59" },
  Dhatu: { fill: "#f0fdfa", stroke: "#0d9488", text: "#115e59" },
  TherapeuticPrinciple: { fill: "#f0f9ff", stroke: "#0284c7", text: "#075985" },
  Candidate: { fill: "#fffbeb", stroke: "#d97706", text: "#92400e" },
  Unknown: { fill: "#ffffff", stroke: "#cbd5e1", text: "#475569" },
}

const edgeStyles: Record<string, { stroke: string; dash?: string; label: string }> = {
  practitioner_verified: { stroke: "#047857", label: "Practitioner verified" },
  literature_supported: { stroke: "#0284c7", label: "Literature supported" },
  unverified: { stroke: "#d97706", dash: "6 4", label: "Unverified (dashed)" },
  disputed: { stroke: "#e11d48", dash: "2 4", label: "Disputed (dotted)" },
}

function nodeColors(node: GraphNode) {
  if (node.isCandidate) return typeColors.Candidate
  return typeColors[node.type ?? ""] ?? typeColors.Unknown
}

function position(node: GraphNode) {
  return {
    x: PAD_X + node.column * (NODE_W + COL_GAP),
    y: PAD_TOP + node.row * (NODE_H + ROW_GAP),
  }
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

type Selection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null

function GraphCanvas({
  graph,
  selection,
  onSelect,
}: {
  graph: ReasoningGraph
  selection: Selection
  onSelect: (selection: Selection) => void
}) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]))
  const width = PAD_X * 2 + graph.columns * NODE_W + (graph.columns - 1) * COL_GAP
  const height = PAD_TOP + Math.max(1, graph.maxRows) * (NODE_H + ROW_GAP) + 8

  const related = React.useMemo(() => {
    if (!selection) return null
    if (selection.kind === "edge") {
      const edge = graph.edges.find((item) => item.id === selection.id)
      return edge ? { nodes: new Set([edge.source, edge.target]), edges: new Set([edge.id]) } : null
    }
    const edges = graph.edges.filter((edge) => edge.source === selection.id || edge.target === selection.id)
    return {
      nodes: new Set([selection.id, ...edges.flatMap((edge) => [edge.source, edge.target])]),
      edges: new Set(edges.map((edge) => edge.id)),
    }
  }, [graph, selection])

  const handleKey = (event: React.KeyboardEvent, next: Selection) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      onSelect(next)
    }
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        role="group"
        aria-label="Reasoning relationship graph"
        className="block"
      >
        <defs>
          <marker id="kg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>

        {columnTitles.map((title, column) => (
          <text
            key={title}
            x={PAD_X + column * (NODE_W + COL_GAP) + NODE_W / 2}
            y={20}
            textAnchor="middle"
            className="fill-slate-400 text-[11px] font-semibold tracking-wide uppercase"
          >
            {title}
          </text>
        ))}

        {graph.edges.map((edge) => {
          const source = nodeById.get(edge.source)
          const target = nodeById.get(edge.target)
          if (!source || !target) return null
          const a = position(source)
          const b = position(target)
          const forward = target.column > source.column
          const x1 = forward ? a.x + NODE_W : a.x + NODE_W / 2
          const y1 = forward ? a.y + NODE_H / 2 : a.y + NODE_H
          const x2 = forward ? b.x : b.x + NODE_W / 2
          const y2 = forward ? b.y + NODE_H / 2 : b.y
          const midX = (x1 + x2) / 2
          const d = forward
            ? `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
            : `M ${x1} ${y1} C ${x1 + 40} ${y1 + 30}, ${x2 + 40} ${y2 - 30}, ${x2} ${y2}`
          const style = edgeStyles[edge.claim.verification_status] ?? { stroke: "#94a3b8", label: edge.claim.verification_status }
          const contradicted = edge.claim.contradicting_evidence.length > 0
          const dimmed = related && !related.edges.has(edge.id)
          const selected = selection?.kind === "edge" && selection.id === edge.id
          const label = `Claim ${edge.claim.claim_id}: ${edge.source} ${predicateLabels[edge.claim.predicate] ?? edge.claim.predicate} ${edge.target}, ${style.label}${contradicted ? ", has contradicting evidence" : ""}`
          return (
            <g
              key={edge.id}
              role="button"
              tabIndex={0}
              aria-label={label}
              aria-pressed={selected}
              onClick={() => onSelect({ kind: "edge", id: edge.id })}
              onKeyDown={(event) => handleKey(event, { kind: "edge", id: edge.id })}
              className="cursor-pointer outline-none [&:focus-visible>path:last-of-type]:stroke-[5]"
              opacity={dimmed ? 0.18 : 1}
            >
              <title>{label}</title>
              <path d={d} fill="none" stroke="transparent" strokeWidth={14} />
              <path
                d={d}
                fill="none"
                stroke={style.stroke}
                strokeWidth={selected ? 3.5 : 2}
                strokeDasharray={style.dash}
                markerEnd="url(#kg-arrow)"
              />
              {contradicted && (
                <g transform={`translate(${midX - 8}, ${(y1 + y2) / 2 - 8})`}>
                  <circle cx={8} cy={8} r={8} fill="#fff1f2" stroke="#e11d48" />
                  <text x={8} y={12} textAnchor="middle" className="fill-rose-700 text-[11px] font-bold">
                    !
                  </text>
                </g>
              )}
            </g>
          )
        })}

        {graph.nodes.map((node) => {
          const { x, y } = position(node)
          const colors = nodeColors(node)
          const selected = selection?.kind === "node" && selection.id === node.id
          const dimmed = related && !related.nodes.has(node.id)
          const typeLabel = node.type ? conceptTypeLabels[node.type] ?? node.type : ""
          return (
            <g
              key={node.id}
              transform={`translate(${x}, ${y})`}
              role="button"
              tabIndex={0}
              aria-label={typeLabel ? `${node.name ?? node.id}, ${typeLabel}` : node.name ?? node.id}
              aria-pressed={selected}
              onClick={() => onSelect({ kind: "node", id: node.id })}
              onKeyDown={(event) => handleKey(event, { kind: "node", id: node.id })}
              className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[3]"
              opacity={dimmed ? 0.3 : 1}
            >
              <title>{typeLabel ? `${node.name ?? node.id} (${typeLabel})` : node.name ?? node.id}</title>
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill={colors.fill}
                stroke={selected ? "#065f46" : colors.stroke}
                strokeWidth={selected ? 2.5 : 1.25}
              />
              <text x={10} y={20} className="text-[12px] font-semibold" fill={colors.text}>
                {truncate(node.name ?? node.id, 24)}
              </text>
              <text x={10} y={36} className="text-[10px]" fill="#64748b">
                {truncate(typeLabel, 28)}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-600">
      {Object.entries(edgeStyles).map(([key, style]) => (
        <span key={key} className="inline-flex items-center gap-1.5">
          <svg width="26" height="8" aria-hidden>
            <line x1="0" y1="4" x2="26" y2="4" stroke={style.stroke} strokeWidth="2" strokeDasharray={style.dash} />
          </svg>
          {style.label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5">
        <span className="flex size-4 items-center justify-center rounded-full border border-rose-600 bg-rose-50 text-[10px] font-bold text-rose-700">!</span>
        Claim has contradicting evidence
      </span>
    </div>
  )
}

function Inspector({
  output,
  graph,
  selection,
  onClear,
}: {
  output: Component2Output
  graph: ReasoningGraph
  selection: Selection
  onClear: () => void
}) {
  const names = React.useMemo(() => conceptNames(output), [output])
  if (!selection) {
    return <EmptyState icon={Network} title="Select a node or relationship" description="Inspect its properties, the claim behind each relationship and the linked evidence." />
  }

  if (selection.kind === "edge") {
    const edge = graph.edges.find((item) => item.id === selection.id)
    if (!edge) return null
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Relationship (claim)</h3>
          <Button variant="ghost" size="icon-sm" aria-label="Clear selection" onClick={onClear}><X /></Button>
        </div>
        <ClaimCard claim={edge.claim} names={names} />
        <p className="text-xs text-slate-500">
          Used by: {edge.candidateIds.map((id) => names.get(id) ?? id).join(", ")}
        </p>
      </div>
    )
  }

  const node = graph.nodes.find((item) => item.id === selection.id)
  if (!node) return null
  const outgoing = graph.edges.filter((edge) => edge.source === node.id)
  const incoming = graph.edges.filter((edge) => edge.target === node.id)
  const interpretation = output.interpretation.find((concept) => concept.concept_id === node.id)
  const candidate = output.candidates.find((item) => item.candidate_id === node.id)
  const symptom = output.symptom_mappings.find((mapping) => mapping.symptom_id === node.id)

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-slate-900">{node.name ?? node.id}</h3>
          <IdChip>{node.id}</IdChip>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="Clear selection" onClick={onClear}><X /></Button>
      </div>
      <KeyValueList
        items={[
          { label: "Type", value: node.type ? conceptTypeLabels[node.type] ?? node.type : "Not supplied" },
          ...(symptom ? [{ label: "INDICATES claims", value: symptom.indicates_claim_ids.length }] : []),
          ...(interpretation
            ? [
                { label: "Reached via claims", value: interpretation.via_claim_ids.join(", ") },
                { label: "Supporting evidence", value: interpretation.supporting_evidence_ids.length },
                { label: "Contradicting evidence", value: interpretation.contradicting_evidence_ids.length },
              ]
            : []),
          ...(candidate
            ? [
                { label: "Rank", value: candidate.rank },
                { label: "Sufficiency", value: <StatusBadge spec={sufficiencySpec(candidate.sufficiency.status)} /> },
              ]
            : []),
        ]}
      />
      {interpretation && (
        <div className="flex flex-wrap gap-1">
          {Array.from(new Set(interpretation.verification_statuses)).map((status) => (
            <StatusBadge key={status} spec={verificationSpec(status)} />
          ))}
        </div>
      )}
      {[
        { title: "Incoming relationships", list: incoming },
        { title: "Outgoing relationships", list: outgoing },
      ].map(({ title, list }) => (
        <div key={title}>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            {title} ({list.length})
          </h4>
          {list.length === 0 ? (
            <p className="text-xs text-slate-500">None in this response.</p>
          ) : (
            <div className="space-y-2">
              {list.map((edge: GraphEdge) => (
                <ClaimCard key={edge.id} claim={edge.claim} names={names} />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function RelationshipList({ graph, output }: { graph: ReasoningGraph; output: Component2Output }) {
  const names = React.useMemo(() => conceptNames(output), [output])
  if (graph.edges.length === 0) {
    return <EmptyState title="No relationships in this response" description="No claims were returned on candidate paths." />
  }
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {graph.edges.map((edge) => (
        <ClaimCard key={edge.id} claim={edge.claim} names={names} />
      ))}
    </div>
  )
}

function GraphView({ output }: { output: Component2Output }) {
  const graph = React.useMemo(() => buildGraph(output), [output])
  const [selection, setSelection] = React.useState<Selection>(null)

  if (graph.nodes.length === 0) {
    return (
      <Panel>
        <EmptyState icon={Network} title="Nothing to display" description="The reasoning output contains no mapped symptoms, concepts or candidates." />
      </Panel>
    )
  }

  return (
    <div className="space-y-4">
      <Notice tone="neutral">
        Every relationship drawn is a claim returned by Component 2 on a candidate path. No relationship is
        inferred by the interface. Concepts reached only through claims outside candidate paths are shown
        without edges because the response does not include those claim details.
      </Notice>
      <Tabs defaultValue="graph">
        <TabsList>
          <TabsTrigger value="graph">Graph view</TabsTrigger>
          <TabsTrigger value="list">Relationship list ({graph.edges.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="graph" className="mt-4">
          <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_400px]">
            <Panel title="Reasoning relationships" description="Select a node or an arrow. Use Tab and Enter to navigate by keyboard." bodyClassName="space-y-3 p-4">
              <Legend />
              <GraphCanvas graph={graph} selection={selection} onSelect={setSelection} />
              {graph.isolatedNodeIds.length > 0 && (
                <p className="text-xs text-slate-500">
                  {graph.isolatedNodeIds.length} node(s) have no relationship details in this response.
                </p>
              )}
            </Panel>
            <Panel title="Inspector" className="2xl:sticky 2xl:top-24 2xl:self-start">
              <Inspector output={output} graph={graph} selection={selection} onClear={() => setSelection(null)} />
            </Panel>
          </div>
        </TabsContent>
        <TabsContent value="list" className="mt-4">
          <RelationshipList graph={graph} output={output} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export function KnowledgeGraphPage() {
  return (
    <>
      <PageHeader
        eyebrow="Component 2 · Knowledge graph"
        title="Knowledge graph"
        description="Relationships between symptoms, Ayurvedic concepts, therapeutic principles and candidates that the reasoning traversed, with the evidence behind each claim."
      />
      <CaseBar />
      <WithReasoning>{(output) => <GraphView output={output} />}</WithReasoning>
    </>
  )
}
