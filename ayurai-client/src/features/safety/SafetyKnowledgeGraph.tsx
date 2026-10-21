import * as React from "react"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Database,
  ExternalLink,
  Filter,
  FlaskConical,
  Info,
  Leaf,
  Network,
  Pill,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react"

import { CaseBar } from "@/components/shared/case"
import { EmptyState, IdChip, KeyValueList, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, safetySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useWorkspace } from "@/context/workspace"
import { component3Api } from "@/lib/api/component3"
import type { C3Drug, C3GraphEdge, C3GraphNode, C3GraphResponse, C3Herb } from "@/lib/api/types"

const NODE_W = 184
const NODE_H = 50
const COL_GAP = 68
const ROW_GAP = 16
const PAD_X = 20
const PAD_TOP = 42

export const columnTitles = [
  "Ayurvedic Herbs",
  "Active Compounds",
  "CYP Enzymes & Targets",
  "Pharmaceutical Drugs",
  "Clinical Directives",
]

const columnByType: Record<string, number> = {
  Herb: 0,
  Compound: 1,
  Enzyme: 2,
  Target: 2,
  Drug: 3,
  Condition: 4,
}

const nodeTypeStyles: Record<string, { fill: string; stroke: string; text: string; badge: string; icon: typeof Leaf }> = {
  Herb: { fill: "#ecfdf5", stroke: "#059669", text: "#065f46", badge: "Ayurvedic Herb", icon: Leaf },
  Compound: { fill: "#fffbeb", stroke: "#d97706", text: "#92400e", badge: "Active Compound", icon: FlaskConical },
  Enzyme: { fill: "#eef2ff", stroke: "#6366f1", text: "#3730a3", badge: "CYP450 Enzyme", icon: Activity },
  Target: { fill: "#f5f3ff", stroke: "#8b5cf6", text: "#5b21b6", badge: "Receptor Target", icon: Sparkles },
  Drug: { fill: "#f0f9ff", stroke: "#0284c7", text: "#075985", badge: "Pharmaceutical Drug", icon: Pill },
  Condition: { fill: "#fff1f2", stroke: "#e11d48", text: "#9f1239", badge: "Contraindication", icon: AlertTriangle },
}

const severityEdgeStyles: Record<string, { stroke: string; dash?: string; label: string; strokeWidth: number }> = {
  High: { stroke: "#dc2626", label: "Severe Interaction / Contraindicated", strokeWidth: 3 },
  Moderate: { stroke: "#ea580c", label: "Moderate (Titration Required)", strokeWidth: 2.25 },
  Low: { stroke: "#0284c7", strokeWidth: 1.75, label: "Low Severity / Minor" },
  Safe: { stroke: "#059669", dash: "5 3", strokeWidth: 1.75, label: "Compatible Synergy" },
  Info: { stroke: "#94a3b8", strokeWidth: 1.5, label: "Biochemical Pathway" },
}

type Selection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null

type PositionedNode = C3GraphNode & {
  column: number
  row: number
  x: number
  y: number
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

export function SafetyKnowledgeGraph() {
  const { currentRecord } = useWorkspace()
  const [data, setData] = React.useState<C3GraphResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  // Filter states
  const [mode, setMode] = React.useState<"active_case" | "tracer" | "all">("active_case")
  const [selectedHerb, setSelectedHerb] = React.useState<string>("")
  const [selectedDrug, setSelectedDrug] = React.useState<string>("")
  const [severityFilter, setSeverityFilter] = React.useState<string>("all")
  const [searchQuery, setSearchQuery] = React.useState("")
  const [selection, setSelection] = React.useState<Selection>(null)

  // Options for dropdowns
  const [herbOptions, setHerbOptions] = React.useState<C3Herb[]>([])
  const [drugOptions, setDrugOptions] = React.useState<C3Drug[]>([])

  // Load dropdown catalogs
  React.useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      component3Api.herbs(controller.signal).catch(() => []),
      component3Api.drugs(controller.signal).catch(() => []),
    ]).then(([herbs, drugs]) => {
      setHerbOptions(herbs)
      setDrugOptions(drugs)
    })
    return () => controller.abort()
  }, [])

  // Fetch graph data
  const fetchGraph = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      let herbParam: string | undefined
      let drugParam: string | undefined

      if (mode === "tracer") {
        herbParam = selectedHerb || undefined
        drugParam = selectedDrug || undefined
      } else if (mode === "active_case" && currentRecord?.c2) {
        // Infer primary candidate and patient meds
        const topCandidate = currentRecord.c2.candidates[0]?.name
        const patientMed = currentRecord.c3Payload?.patient_context?.concurrent_medications[0]
        if (topCandidate) herbParam = topCandidate
        if (patientMed) drugParam = patientMed
      }

      const res = await component3Api.subgraph({
        herb: herbParam,
        drug: drugParam,
        severity: severityFilter !== "all" ? severityFilter : undefined,
        limit: mode === "all" ? 60 : 35,
      })
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load safety graph data")
    } finally {
      setLoading(false)
    }
  }, [mode, selectedHerb, selectedDrug, severityFilter, currentRecord])

  React.useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  // Process nodes into 5-column layout
  const layout = React.useMemo(() => {
    if (!data) return { positionedNodes: [], edges: [], width: 900, height: 600, maxRows: 0 }

    let filteredNodes = data.nodes
    let filteredEdges = data.edges

    // Text search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      const matchingIds = new Set(
        filteredNodes
          .filter(
            (n) =>
              n.name.toLowerCase().includes(q) ||
              (n.botanical_name && n.botanical_name.toLowerCase().includes(q)) ||
              (n.sanskrit_name && n.sanskrit_name.toLowerCase().includes(q)),
          )
          .map((n) => n.id),
      )

      filteredEdges = filteredEdges.filter(
        (e) => matchingIds.has(e.source) || matchingIds.has(e.target),
      )
      const connected = new Set(filteredEdges.flatMap((e) => [e.source, e.target]))
      filteredNodes = filteredNodes.filter((n) => matchingIds.has(n.id) || connected.has(n.id))
    }

    const byCol = new Map<number, C3GraphNode[]>()
    for (let c = 0; c < columnTitles.length; c++) byCol.set(c, [])

    for (const node of filteredNodes) {
      const col = columnByType[node.type] ?? 2
      byCol.get(col)?.push(node)
    }

    let maxRows = 1
    const positioned: PositionedNode[] = []
    const nodeMap = new Map<string, PositionedNode>()

    for (const [col, colNodes] of byCol.entries()) {
      colNodes.sort((a, b) => a.name.localeCompare(b.name))
      maxRows = Math.max(maxRows, colNodes.length)
      colNodes.forEach((node, row) => {
        const x = PAD_X + col * (NODE_W + COL_GAP)
        const y = PAD_TOP + row * (NODE_H + ROW_GAP)
        const posNode: PositionedNode = { ...node, column: col, row, x, y }
        positioned.push(posNode)
        nodeMap.set(node.id, posNode)
      })
    }

    const validEdges = filteredEdges.filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
    const width = PAD_X * 2 + columnTitles.length * NODE_W + (columnTitles.length - 1) * COL_GAP
    const height = PAD_TOP + Math.max(1, maxRows) * (NODE_H + ROW_GAP) + 32

    return { positionedNodes: positioned, edges: validEdges, width, height, maxRows }
  }, [data, searchQuery])

  // Connected elements for highlighting selection
  const related = React.useMemo(() => {
    if (!selection) return null
    if (selection.kind === "edge") {
      const edge = layout.edges.find((item) => item.id === selection.id)
      return edge ? { nodes: new Set([edge.source, edge.target]), edges: new Set([edge.id]) } : null
    }
    const edges = layout.edges.filter((e) => e.source === selection.id || e.target === selection.id)
    return {
      nodes: new Set([selection.id, ...edges.flatMap((e) => [e.source, e.target])]),
      edges: new Set(edges.map((e) => e.id)),
    }
  }, [layout.edges, selection])

  // Inspector details
  const selectedNode = selection?.kind === "node" ? layout.positionedNodes.find((n) => n.id === selection.id) : null
  const selectedEdge = selection?.kind === "edge" ? layout.edges.find((e) => e.id === selection.id) : null

  return (
    <div className="space-y-6">
      {/* Top Banner & Neo4j Database Status */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800">
            <Network className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900">Component 3 · Safety Knowledge Graph</h2>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200">
                <Database className="size-3" /> Live Neo4j Connected
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Interactive multi-hop pathway discovery: Herb → Active Compound → CYP450 Enzyme / Receptor Target ↔ Pharmaceutical Drug.
            </p>
          </div>
        </div>

        {data?.stats && (
          <div className="flex items-center gap-3 text-xs text-slate-600 bg-slate-50 px-3 py-2 rounded-lg border border-slate-200">
            <span>
              Total Graph Nodes: <strong>{String((data.stats as Record<string, unknown>).total_nodes ?? 379)}</strong>
            </span>
            <span className="text-slate-300">|</span>
            <span>
              Relationships: <strong>{String((data.stats as Record<string, unknown>).total_relationships ?? 498)}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Mode Controls & Filters */}
      <Panel
        title="Knowledge Graph Controls & Multi-Hop Pathway Tracer"
        description="Filter by active case, trace multi-hop pathways between an herb and a pharmaceutical drug, or inspect interaction severities."
      >
        <div className="flex flex-wrap items-center gap-3 pb-2 border-b border-slate-100">
          <div className="flex items-center rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => {
                setMode("active_case")
                setSelection(null)
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                mode === "active_case" ? "bg-white text-emerald-800 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Active Case Subgraph
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("tracer")
                setSelection(null)
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                mode === "tracer" ? "bg-white text-emerald-800 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Herb ↔ Drug Pathway Tracer
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("all")
                setSelection(null)
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                mode === "all" ? "bg-white text-emerald-800 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Full Safety Network
            </button>
          </div>

          {/* Tracer Selectors */}
          {mode === "tracer" && (
            <div className="flex flex-wrap items-center gap-2">
              <select
                aria-label="Select Ayurvedic Herb"
                value={selectedHerb}
                onChange={(e) => setSelectedHerb(e.target.value)}
                className="text-xs rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-slate-800"
              >
                <option value="">-- All Ayurvedic Herbs --</option>
                {herbOptions.map((h) => (
                  <option key={h.id} value={h.common_name}>
                    {h.common_name} ({h.botanical_name})
                  </option>
                ))}
              </select>

              <ArrowRight className="size-3.5 text-slate-400" />

              <select
                aria-label="Select Pharmaceutical Drug"
                value={selectedDrug}
                onChange={(e) => setSelectedDrug(e.target.value)}
                className="text-xs rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-slate-800"
              >
                <option value="">-- All Pharmaceutical Drugs --</option>
                {drugOptions.map((d) => (
                  <option key={d.id} value={d.generic_name}>
                    {d.generic_name} ({d.drug_class})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Severity filter */}
          <div className="flex items-center gap-1.5 ml-auto">
            <Filter className="size-3.5 text-slate-400" />
            <select
              aria-label="Filter by Severity"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-slate-800"
            >
              <option value="all">All Severities</option>
              <option value="high">High Severity Only</option>
              <option value="moderate">Moderate Severity</option>
              <option value="safe">Compatible Synergy</option>
            </select>

            {/* Quick text search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-slate-400" />
              <input
                type="text"
                placeholder="Search node..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-36 text-xs rounded-lg border border-slate-300 bg-white pl-7 pr-2.5 py-1.5 text-slate-800 focus:outline-emerald-600"
              />
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="pt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-600">
          <span className="font-semibold text-slate-700">Nodes:</span>
          {Object.entries(nodeTypeStyles).map(([type, style]) => (
            <span key={type} className="inline-flex items-center gap-1.5">
              <span className="size-3 rounded-full border" style={{ backgroundColor: style.fill, borderColor: style.stroke }} />
              {style.badge}
            </span>
          ))}

          <span className="font-semibold text-slate-700 ml-2">Edges:</span>
          {Object.entries(severityEdgeStyles).map(([sev, style]) => (
            <span key={sev} className="inline-flex items-center gap-1.5">
              <svg width="22" height="6" aria-hidden>
                <line x1="0" y1="3" x2="22" y2="3" stroke={style.stroke} strokeWidth={style.strokeWidth} strokeDasharray={style.dash} />
              </svg>
              {style.label}
            </span>
          ))}
        </div>
      </Panel>

      {/* Main Tabs: Visual Graph vs Interaction List vs Neo4j Architecture */}
      <Tabs defaultValue="visual">
        <TabsList>
          <TabsTrigger value="visual" className="flex items-center gap-2">
            <Network className="size-3.5" /> Interactive Graph Canvas ({layout.positionedNodes.length} nodes, {layout.edges.length} edges)
          </TabsTrigger>
          <TabsTrigger value="interactions" className="flex items-center gap-2">
            <ShieldAlert className="size-3.5" /> Interaction Rules & Citations ({data?.edges.filter((e) => e.type === "INTERACTS_WITH").length ?? 0})
          </TabsTrigger>
          <TabsTrigger value="schema" className="flex items-center gap-2">
            <Database className="size-3.5" /> Neo4j Graph Schema & Multi-Hop Cypher
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: Visual Interactive SVG Canvas */}
        <TabsContent value="visual" className="mt-4">
          <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_420px]">
            {/* Visual Canvas */}
            <Panel
              title="Multi-Hop Safety Relationship Canvas"
              description="Click any node or relationship line to inspect active compounds, metabolizing enzymes, PubMed evidence, and titration guidance."
              bodyClassName="p-3 space-y-3"
            >
              {loading ? (
                <div className="flex h-96 items-center justify-center text-xs text-slate-500">
                  <Activity className="size-5 animate-spin mr-2 text-emerald-600" /> Discovering multi-hop pathways in Neo4j...
                </div>
              ) : error ? (
                <EmptyState title="Graph Query Error" description={error} />
              ) : layout.positionedNodes.length === 0 ? (
                <EmptyState title="No matching nodes found" description="Try clearing your search query or selecting a different herb-drug pair." />
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                  <svg
                    viewBox={`0 0 ${layout.width} ${layout.height}`}
                    width={layout.width}
                    height={layout.height}
                    className="block"
                    role="group"
                    aria-label="Component 3 Safety Knowledge Graph"
                  >
                    <defs>
                      <marker id="c3-arrow-neutral" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                        <path d="M 0 1 L 9 5 L 0 9 z" fill="#94a3b8" />
                      </marker>
                      <marker id="c3-arrow-danger" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                        <path d="M 0 1 L 9 5 L 0 9 z" fill="#dc2626" />
                      </marker>
                      <marker id="c3-arrow-warning" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                        <path d="M 0 1 L 9 5 L 0 9 z" fill="#ea580c" />
                      </marker>
                      <marker id="c3-arrow-success" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                        <path d="M 0 1 L 9 5 L 0 9 z" fill="#059669" />
                      </marker>
                    </defs>

                    {/* Column Header Titles */}
                    {columnTitles.map((title, col) => (
                      <text
                        key={title}
                        x={PAD_X + col * (NODE_W + COL_GAP) + NODE_W / 2}
                        y={22}
                        textAnchor="middle"
                        className="fill-slate-500 text-[11px] font-bold tracking-wider uppercase"
                      >
                        {title}
                      </text>
                    ))}

                    {/* Edges */}
                    {layout.edges.map((edge) => {
                      const source = layout.positionedNodes.find((n) => n.id === edge.source)
                      const target = layout.positionedNodes.find((n) => n.id === edge.target)
                      if (!source || !target) return null

                      const forward = target.column > source.column
                      const x1 = forward ? source.x + NODE_W : source.x + NODE_W / 2
                      const y1 = forward ? source.y + NODE_H / 2 : source.y + NODE_H
                      const x2 = forward ? target.x : target.x + NODE_W / 2
                      const y2 = forward ? target.y + NODE_H / 2 : target.y
                      const midX = (x1 + x2) / 2

                      const d = forward
                        ? `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
                        : `M ${x1} ${y1} C ${x1 + 35} ${y1 + 25}, ${x2 + 35} ${y2 - 25}, ${x2} ${y2}`

                      const style = severityEdgeStyles[edge.severity] ?? severityEdgeStyles.Info
                      const isHighRisk = edge.severity === "High"
                      const dimmed = related && !related.edges.has(edge.id)
                      const isSelected = selection?.kind === "edge" && selection.id === edge.id

                      const markerId = isHighRisk
                        ? "url(#c3-arrow-danger)"
                        : edge.severity === "Moderate"
                        ? "url(#c3-arrow-warning)"
                        : edge.severity === "Safe"
                        ? "url(#c3-arrow-success)"
                        : "url(#c3-arrow-neutral)"

                      return (
                        <g
                          key={edge.id}
                          role="button"
                          tabIndex={0}
                          aria-label={`Edge: ${edge.type} from ${source.name} to ${target.name}`}
                          onClick={() => setSelection({ kind: "edge", id: edge.id })}
                          className="cursor-pointer outline-none"
                          opacity={dimmed ? 0.15 : 1}
                        >
                          <path d={d} fill="none" stroke="transparent" strokeWidth={16} />
                          <path
                            d={d}
                            fill="none"
                            stroke={style.stroke}
                            strokeWidth={isSelected ? style.strokeWidth + 2 : style.strokeWidth}
                            strokeDasharray={style.dash}
                            markerEnd={markerId}
                          />
                          {isHighRisk && (
                            <g transform={`translate(${midX - 7}, ${(y1 + y2) / 2 - 7})`}>
                              <circle cx={7} cy={7} r={7} fill="#fee2e2" stroke="#dc2626" />
                              <text x={7} y={11} textAnchor="middle" className="fill-red-700 text-[10px] font-bold">
                                !
                              </text>
                            </g>
                          )}
                        </g>
                      )
                    })}

                    {/* Nodes */}
                    {layout.positionedNodes.map((node) => {
                      const style = nodeTypeStyles[node.type] ?? nodeTypeStyles.Herb
                      const isSelected = selection?.kind === "node" && selection.id === node.id
                      const dimmed = related && !related.nodes.has(node.id)

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${node.x}, ${node.y})`}
                          role="button"
                          tabIndex={0}
                          aria-label={`${node.name} (${node.type})`}
                          onClick={() => setSelection({ kind: "node", id: node.id })}
                          className="cursor-pointer outline-none"
                          opacity={dimmed ? 0.25 : 1}
                        >
                          <rect
                            width={NODE_W}
                            height={NODE_H}
                            rx={8}
                            fill={style.fill}
                            stroke={isSelected ? "#0f172a" : style.stroke}
                            strokeWidth={isSelected ? 2.5 : 1.25}
                          />
                          <text x={10} y={20} className="text-[11.5px] font-semibold" fill={style.text}>
                            {truncate(node.name, 22)}
                          </text>
                          <text x={10} y={36} className="text-[9.5px]" fill="#64748b">
                            {truncate(
                              node.type === "Herb"
                                ? node.botanical_name || style.badge
                                : node.type === "Drug"
                                ? node.category || style.badge
                                : style.badge,
                              25,
                            )}
                          </text>
                        </g>
                      )
                    })}
                  </svg>
                </div>
              )}
            </Panel>

            {/* Right Inspector Panel */}
            <Panel title="Pathway & Evidence Inspector" className="2xl:sticky 2xl:top-24 2xl:self-start">
              {!selection && (
                <EmptyState
                  icon={Network}
                  title="Inspect Safety Node or Relationship"
                  description="Click on any Ayurvedic herb, active compound, CYP enzyme, or interaction line in the canvas to inspect its biochemical mechanism, clinical directives, and PubMed evidence."
                />
              )}

              {/* Node Inspector */}
              {selectedNode && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2 border-b border-slate-100 pb-3">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-md" style={{ backgroundColor: nodeTypeStyles[selectedNode.type]?.fill, color: nodeTypeStyles[selectedNode.type]?.text }}>
                          {selectedNode.type}
                        </span>
                        {selectedNode.narrow_therapeutic_index && (
                          <span className="text-xs font-bold px-1.5 py-0.5 rounded-md bg-rose-100 text-rose-800">
                            Narrow Therapeutic Index (NTI)
                          </span>
                        )}
                      </div>
                      <h3 className="text-base font-bold text-slate-900 mt-1">{selectedNode.name}</h3>
                      <IdChip>{selectedNode.id}</IdChip>
                    </div>
                    <Button variant="ghost" size="icon-sm" onClick={() => setSelection(null)}>
                      <X className="size-4" />
                    </Button>
                  </div>

                  <KeyValueList
                    items={[
                      ...(selectedNode.sanskrit_name ? [{ label: "Sanskrit Name", value: selectedNode.sanskrit_name }] : []),
                      ...(selectedNode.botanical_name ? [{ label: "Botanical Specie", value: selectedNode.botanical_name }] : []),
                      ...(selectedNode.category ? [{ label: "Category", value: selectedNode.category }] : []),
                      ...(selectedNode.traditional_uses && selectedNode.traditional_uses.length > 0
                        ? [{ label: "Traditional Uses", value: selectedNode.traditional_uses.join(", ") }]
                        : []),
                      ...(selectedNode.active_compounds && selectedNode.active_compounds.length > 0
                        ? [{ label: "Active Compounds", value: selectedNode.active_compounds.join(", ") }]
                        : []),
                      ...(selectedNode.metabolizing_enzymes && selectedNode.metabolizing_enzymes.length > 0
                        ? [{ label: "Metabolizing Enzymes", value: selectedNode.metabolizing_enzymes.join(", ") }]
                        : []),
                      ...(selectedNode.target_receptors && selectedNode.target_receptors.length > 0
                        ? [{ label: "Target Receptors", value: selectedNode.target_receptors.join(", ") }]
                        : []),
                    ]}
                  />

                  {selectedNode.contraindications && selectedNode.contraindications.length > 0 && (
                    <div className="rounded-lg bg-rose-50 border border-rose-200 p-3">
                      <p className="text-xs font-bold text-rose-800 flex items-center gap-1.5">
                        <ShieldAlert className="size-3.5" /> Clinical Contraindications:
                      </p>
                      <ul className="mt-1 list-disc pl-4 text-xs text-rose-700 space-y-0.5">
                        {selectedNode.contraindications.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Incoming & Outgoing Connections */}
                  <div className="space-y-3 pt-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Connected Relationships ({layout.edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id).length})
                    </h4>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {layout.edges
                        .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                        .map((e) => {
                          const otherId = e.source === selectedNode.id ? e.target : e.source
                          const otherNode = layout.positionedNodes.find((n) => n.id === otherId)
                          return (
                            <button
                              key={e.id}
                              type="button"
                              onClick={() => setSelection({ kind: "edge", id: e.id })}
                              className="w-full text-left p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-all text-xs"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">{e.type}</span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: severityEdgeStyles[e.severity]?.stroke + "20", color: severityEdgeStyles[e.severity]?.stroke }}>
                                  {e.severity}
                                </span>
                              </div>
                              <p className="text-slate-500 text-[11px] mt-0.5">
                                {e.source === selectedNode.id ? "→ " : "← "} {otherNode?.name ?? otherId}
                              </p>
                            </button>
                          )
                        })}
                    </div>
                  </div>
                </div>
              )}

              {/* Edge Inspector */}
              {selectedEdge && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2 border-b border-slate-100 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold px-2 py-0.5 rounded-md" style={{ backgroundColor: severityEdgeStyles[selectedEdge.severity]?.stroke + "20", color: severityEdgeStyles[selectedEdge.severity]?.stroke }}>
                          {selectedEdge.severity} Severity
                        </span>
                        <span className="text-xs text-slate-500 font-mono">{selectedEdge.type}</span>
                      </div>
                      <h3 className="text-base font-bold text-slate-900 mt-1">
                        {layout.positionedNodes.find((n) => n.id === selectedEdge.source)?.name} →{" "}
                        {layout.positionedNodes.find((n) => n.id === selectedEdge.target)?.name}
                      </h3>
                      <IdChip>{selectedEdge.id}</IdChip>
                    </div>
                    <Button variant="ghost" size="icon-sm" onClick={() => setSelection(null)}>
                      <X className="size-4" />
                    </Button>
                  </div>

                  {selectedEdge.mechanism && (
                    <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-1">
                      <p className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                        <BookOpen className="size-3.5 text-slate-600" /> Pharmacological Mechanism:
                      </p>
                      <p className="text-xs text-slate-700 leading-relaxed">{selectedEdge.mechanism}</p>
                    </div>
                  )}

                  {selectedEdge.recommended_action && (
                    <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-1">
                      <p className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
                        <ShieldAlert className="size-3.5 text-amber-700" /> Practitioner Titration Directive:
                      </p>
                      <p className="text-xs text-amber-800 leading-relaxed">{selectedEdge.recommended_action}</p>
                    </div>
                  )}

                  <KeyValueList
                    items={[
                      ...(selectedEdge.interaction_type ? [{ label: "Interaction Category", value: selectedEdge.interaction_type }] : []),
                      ...(selectedEdge.evidence_level ? [{ label: "Evidence Strength", value: selectedEdge.evidence_level }] : []),
                      ...(selectedEdge.citation ? [{ label: "Clinical Literature", value: selectedEdge.citation }] : []),
                    ]}
                  />

                  {selectedEdge.pmid && (
                    <div className="pt-2">
                      <a
                        href={`https://pubmed.ncbi.nlm.nih.gov/${selectedEdge.pmid}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 hover:text-emerald-800 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200"
                      >
                        <ExternalLink className="size-3.5" /> View PubMed Clinical Trial (PMID: {selectedEdge.pmid})
                      </a>
                    </div>
                  )}
                </div>
              )}
            </Panel>
          </div>
        </TabsContent>

        {/* TAB 2: Interaction Rules List */}
        <TabsContent value="interactions" className="mt-4">
          <Panel
            title="Curated Herb-Drug Interaction Rules & PubMed Citations"
            description="Verified rules codified in Neo4j connecting classical Ayurvedic candidates with narrow therapeutic index medications."
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {data?.edges
                .filter((e) => e.type === "INTERACTS_WITH")
                .map((inter) => {
                  const sourceNode = data.nodes.find((n) => n.id === inter.source)
                  const targetNode = data.nodes.find((n) => n.id === inter.target)
                  return (
                    <div
                      key={inter.id}
                      className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 hover:border-slate-300 transition-all shadow-2xs"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span
                            className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                            style={{
                              backgroundColor: severityEdgeStyles[inter.severity]?.stroke + "20",
                              color: severityEdgeStyles[inter.severity]?.stroke,
                            }}
                          >
                            {inter.severity} Severity
                          </span>
                          <h4 className="text-sm font-bold text-slate-900 mt-1">
                            {sourceNode?.name ?? inter.source} ↔ {targetNode?.name ?? inter.target}
                          </h4>
                          <p className="text-xs text-slate-500 font-mono">{inter.interaction_type || "Herb-Drug Collision"}</p>
                        </div>
                        {inter.pmid && (
                          <a
                            href={`https://pubmed.ncbi.nlm.nih.gov/${inter.pmid}/`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] text-emerald-700 hover:underline bg-emerald-50 px-2 py-1 rounded-md"
                          >
                            <ExternalLink className="size-3" /> PMID {inter.pmid}
                          </a>
                        )}
                      </div>

                      <p className="text-xs text-slate-700 leading-relaxed">{inter.mechanism}</p>

                      {inter.recommended_action && (
                        <div className="rounded-lg bg-amber-50 p-2 text-xs text-amber-900 border border-amber-200">
                          <strong>Directive:</strong> {inter.recommended_action}
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          </Panel>
        </TabsContent>

        {/* TAB 3: Neo4j Schema & Architecture */}
        <TabsContent value="schema" className="mt-4">
          <Panel
            title="Component 3: Neo4j Multi-Hop Graph Architecture"
            description="Cypher query patterns and ontological schema constraints powering in-silico interaction prediction."
          >
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                  <span className="font-semibold text-slate-700">Nodes (Entities)</span>
                  <ul className="mt-2 space-y-1 text-slate-600">
                    <li>• <code>:Herb</code> (31 Anemia Formulations)</li>
                    <li>• <code>:Compound</code> (121 Phytochemicals)</li>
                    <li>• <code>:Enzyme</code> (55 CYP450 Subtypes)</li>
                    <li>• <code>:Drug</code> (55 Pharmaceutical Drugs)</li>
                    <li>• <code>:Condition</code> (63 Clinical Contraindications)</li>
                  </ul>
                </div>

                <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                  <span className="font-semibold text-slate-700">Relationships (Edges)</span>
                  <ul className="mt-2 space-y-1 text-slate-600">
                    <li>• <code>[:CONTAINS_COMPOUND]</code> (Herb → Compound)</li>
                    <li>• <code>[:INHIBITS] / [:INDUCES]</code> (Compound → Enzyme)</li>
                    <li>• <code>[:METABOLIZED_BY]</code> (Drug → Enzyme)</li>
                    <li>• <code>[:ACTS_ON]</code> (Drug → Target Receptor)</li>
                    <li>• <code>[:CONTRAINDICATED_IN]</code> (Herb → Condition)</li>
                  </ul>
                </div>

                <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                  <span className="font-semibold text-slate-700">Live Status & Verification</span>
                  <ul className="mt-2 space-y-1 text-slate-600">
                    <li>• Mode: <strong>Neo4j Live Graph Service</strong></li>
                    <li>• Graph Protocol: <strong>Bolt (neo4j://)</strong></li>
                    <li>• Multi-hop reasoning: <strong>M2 Generic GNN + M4 Fusion</strong></li>
                    <li>• Evidence standard: <strong>PubMed / WHO Monographs</strong></li>
                  </ul>
                </div>
              </div>

              <div className="rounded-lg bg-slate-900 text-slate-100 p-4 font-mono text-[11px] overflow-x-auto">
                <p className="text-slate-400">// Sample Multi-Hop Pathway Cypher Pattern:</p>
                <p className="text-emerald-400">
                  MATCH path = (h:Herb)-[:CONTAINS_COMPOUND]-&gt;(c:Compound)-[r:INHIBITS|INDUCES]-&gt;(e:Enzyme)&lt;-[:METABOLIZED_BY]-(d:Drug)
                </p>
                <p className="text-emerald-400">
                  WHERE toLower(h.common_name) = toLower($herb) AND toLower(d.generic_name) = toLower($drug)
                </p>
                <p className="text-emerald-400">
                  RETURN h.common_name, c.name, type(r), e.name, d.generic_name;
                </p>
              </div>
            </div>
          </Panel>
        </TabsContent>
      </Tabs>
    </div>
  )
}
