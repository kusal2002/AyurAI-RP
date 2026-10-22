import * as React from "react"
import { FileSearch, TriangleAlert, X } from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { ScoreCaveat, SourceLine, SourceLink } from "@/components/shared/c2"
import {
  EmptyState,
  FilterChips,
  IdChip,
  KeyValueList,
  PageHeader,
  Panel,
  SearchInput,
} from "@/components/shared/page"
import { StatusBadge, relationshipSpecs, verificationSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Component2Output } from "@/lib/api/types"
import { conceptNames, indexClaims, indexEvidence, matchedRogaTypes, type EvidenceIndexEntry } from "@/lib/c2-derive"
import { evidenceTypeLabels, formatScore, humanizeCode, predicateLabels } from "@/lib/labels"
import { cn } from "@/lib/utils"

type RelationFilter = "all" | "supports" | "contradicts"

/** Matched Pandu types (e.g. Pittaja Pandu) that a record's claims start or end at. */
function rogaTypesOf(entry: EvidenceIndexEntry, output: Component2Output, typeIds: Set<string>): string[] {
  const claims = indexClaims(output)
  const found = new Set<string>()
  for (const usage of entry.usages) {
    const claim = claims.get(usage.claimId)?.claim
    if (!claim) continue
    if (typeIds.has(claim.subject_id)) found.add(claim.subject_id)
    if (typeIds.has(claim.object_id)) found.add(claim.object_id)
  }
  return Array.from(found).sort()
}
type ProvenanceFilter = "all" | "complete" | "incomplete"

function EvidenceDetail({
  entry,
  output,
  onClose,
}: {
  entry: EvidenceIndexEntry
  output: Component2Output
  onClose: () => void
}) {
  const claims = indexClaims(output)
  const names = conceptNames(output)
  const ref = entry.reference
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <IdChip>{entry.evidenceId}</IdChip>
          {ref.title && <h3 className="mt-1 text-base font-semibold text-slate-900">{ref.title}</h3>}
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="Close evidence detail" onClick={onClose}>
          <X />
        </Button>
      </div>
      <KeyValueList
        items={[
          { label: "Source", value: ref.source_name ?? "Not supplied" },
          { label: "Source type", value: ref.evidence_type ? evidenceTypeLabels[ref.evidence_type] ?? ref.evidence_type : "Not supplied" },
          { label: "Section", value: ref.section ?? "Not supplied" },
          { label: "Page", value: ref.page ?? "Not supplied" },
          { label: "Citation", value: ref.citation ?? "Not supplied" },
          { label: "Source link", value: <SourceLink url={ref.source_url} /> },
          ...(ref.source_id
            ? [{ label: "Source ID", value: <code className="text-xs break-all">{ref.source_id}</code> }]
            : []),
          ...(ref.source_chunk_id
            ? [{ label: "Source passage", value: <code className="text-xs break-all">{ref.source_chunk_id}</code> }]
            : []),
          { label: "Practitioner verified", value: ref.practitioner_verified ? "Yes" : "No" },
          {
            label: "Provenance",
            value: ref.provenance_complete ? "Complete" : (
              <span className="text-amber-800">
                Incomplete{ref.missing_provenance.length ? `: missing ${ref.missing_provenance.map(humanizeCode).join(", ")}` : ""}
              </span>
            ),
          },
        ]}
      />
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
        The Component 2 response includes evidence metadata only. The passage text is stored in the
        knowledge base but no API endpoint returns it yet, so no excerpt is shown.
      </p>

      <div>
        <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Linked claims</h4>
        <ul className="space-y-2">
          {entry.usages.map((usage) => {
            const claim = claims.get(usage.claimId)?.claim
            return (
              <li key={`${usage.relationship}-${usage.claimId}`} className="rounded-lg border border-slate-200 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge spec={relationshipSpecs[usage.relationship]} />
                  <IdChip>{usage.claimId}</IdChip>
                  {claim && <StatusBadge spec={verificationSpec(claim.verification_status)} />}
                </div>
                {claim && (
                  <p className="mt-2 text-sm text-slate-700">
                    {names.get(claim.subject_id) ?? claim.subject_id}{" "}
                    <span className="text-emerald-700">{predicateLabels[claim.predicate] ?? claim.predicate}</span>{" "}
                    {names.get(claim.object_id) ?? claim.object_id}
                  </p>
                )}
                {claim?.retrieval_similarity !== null && claim?.retrieval_similarity !== undefined && (
                  <p className="mt-1 text-xs text-slate-500">
                    Claim–evidence retrieval similarity: {formatScore(claim.retrieval_similarity)}
                  </p>
                )}
                <p className="mt-1 text-xs text-slate-500">
                  Candidates using this claim:{" "}
                  {usage.candidateIds.map((id) => names.get(id) ?? id).join(", ") ||
                    "none (traversed for interpretation only; never creates or ranks a candidate)"}
                </p>
              </li>
            )
          })}
        </ul>
      </div>

      {entry.interpretationConceptIds.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Interpretation concepts</h4>
          <div className="flex flex-wrap gap-1.5">
            {entry.interpretationConceptIds.map((id) => (
              <span key={id} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                {names.get(id) ?? id}
              </span>
            ))}
          </div>
        </div>
      )}

      {entry.retrievalHits.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Open-retrieval hits</h4>
          <ul className="space-y-1 text-xs text-slate-600">
            {entry.retrievalHits.map((hit) => (
              <li key={hit.chunk_id}>
                <IdChip>{hit.chunk_id}</IdChip> similarity {formatScore(hit.similarity)}
                {hit.below_threshold && " (below threshold)"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function EvidenceExplorer({ output }: { output: Component2Output }) {
  const index = React.useMemo(() => indexEvidence(output), [output])
  const names = React.useMemo(() => conceptNames(output), [output])
  const rogaTypes = React.useMemo(() => matchedRogaTypes(output), [output])
  const typesByEvidence = React.useMemo(() => {
    const typeIds = new Set(rogaTypes.keys())
    return new Map(Array.from(index.values()).map((entry) => [entry.evidenceId, rogaTypesOf(entry, output, typeIds)]))
  }, [index, output, rogaTypes])
  const [rogaType, setRogaType] = React.useState("all")
  const [relation, setRelation] = React.useState<RelationFilter>("all")
  const [provenance, setProvenance] = React.useState<ProvenanceFilter>("all")
  const [type, setType] = React.useState("all")
  const [query, setQuery] = React.useState("")
  const [selected, setSelected] = React.useState<string | null>(null)

  const entries = Array.from(index.values())
  const types = Array.from(new Set(entries.map((entry) => entry.reference.evidence_type ?? "unknown")))

  const filtered = entries.filter((entry) => {
    const supports = entry.usages.some((usage) => usage.relationship === "SUPPORTS")
    const contradicts = entry.usages.some((usage) => usage.relationship === "CONTRADICTS")
    if (relation === "supports" && !supports) return false
    if (relation === "contradicts" && !contradicts) return false
    if (provenance === "complete" && !entry.reference.provenance_complete) return false
    if (provenance === "incomplete" && entry.reference.provenance_complete) return false
    if (type !== "all" && (entry.reference.evidence_type ?? "unknown") !== type) return false
    const entryTypes = typesByEvidence.get(entry.evidenceId) ?? []
    if (rogaType === "any" && entryTypes.length === 0) return false
    if (rogaType !== "all" && rogaType !== "any" && !entryTypes.includes(rogaType)) return false
    const text = query.trim().toLowerCase()
    if (text) {
      const haystack = [entry.evidenceId, entry.reference.title, entry.reference.source_name, entry.reference.citation]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
      if (!haystack.includes(text)) return false
    }
    return true
  })

  const selectedEntry = selected ? index.get(selected) : undefined

  return (
    <Tabs defaultValue="linked">
      <TabsList>
        <TabsTrigger value="linked">Claim-linked evidence ({entries.length})</TabsTrigger>
        <TabsTrigger value="retrieved">Semantic retrieval ({output.retrieved_evidence.length})</TabsTrigger>
      </TabsList>

      <TabsContent value="linked" className="mt-4">
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <Panel
            title="Evidence records"
            description="Evidence linked by SUPPORTS or CONTRADICTS relationships to claims on the reasoning paths"
            bodyClassName="p-0"
          >
            <div className="space-y-3 border-b border-slate-100 p-4">
              <SearchInput value={query} onChange={setQuery} placeholder="Search ID, title, source or citation…" label="Search evidence" />
              <div className="flex flex-wrap items-center gap-3">
                <FilterChips
                  label="Relationship"
                  value={relation}
                  onChange={setRelation}
                  options={[
                    { value: "all", label: "All" },
                    { value: "supports", label: "Supporting" },
                    { value: "contradicts", label: "Contradicting" },
                  ]}
                />
                <FilterChips
                  label="Provenance"
                  value={provenance}
                  onChange={setProvenance}
                  options={[
                    { value: "all", label: "Any provenance" },
                    { value: "complete", label: "Complete" },
                    { value: "incomplete", label: "Incomplete" },
                  ]}
                />
                <select
                  aria-label="Evidence type"
                  value={type}
                  onChange={(event) => setType(event.target.value)}
                  className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700"
                >
                  <option value="all">All source types</option>
                  {types.map((value) => (
                    <option key={value} value={value}>
                      {evidenceTypeLabels[value] ?? humanizeCode(value)}
                    </option>
                  ))}
                </select>
                {rogaTypes.size > 0 && (
                  <select
                    aria-label="Pandu type"
                    value={rogaType}
                    onChange={(event) => setRogaType(event.target.value)}
                    className="h-8 rounded-lg border border-violet-200 bg-white px-2 text-xs text-slate-700"
                  >
                    <option value="all">All evidence</option>
                    <option value="any">Any matched Pandu type</option>
                    {Array.from(rogaTypes.values()).map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name ?? names.get(item.id) ?? item.id}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>
            {filtered.length === 0 ? (
              <EmptyState
                icon={FileSearch}
                title={entries.length === 0 ? "No evidence linked" : "No evidence matches these filters"}
                description={entries.length === 0 ? "The reasoning output contains no claim-linked evidence." : undefined}
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {filtered.map((entry) => {
                  const supports = entry.usages.filter((usage) => usage.relationship === "SUPPORTS").length
                  const contradicts = entry.usages.filter((usage) => usage.relationship === "CONTRADICTS").length
                  return (
                    <li key={entry.evidenceId}>
                      <button
                        type="button"
                        onClick={() => setSelected(entry.evidenceId)}
                        aria-pressed={selected === entry.evidenceId}
                        className={cn(
                          "w-full px-4 py-3 text-left transition hover:bg-slate-50",
                          selected === entry.evidenceId && "bg-emerald-50/60",
                        )}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <IdChip>{entry.evidenceId}</IdChip>
                          {supports > 0 && <StatusBadge spec={{ ...relationshipSpecs.SUPPORTS, label: `Supports ${supports} claim(s)` }} />}
                          {contradicts > 0 && <StatusBadge spec={{ ...relationshipSpecs.CONTRADICTS, label: `Contradicts ${contradicts} claim(s)` }} />}
                          {(typesByEvidence.get(entry.evidenceId) ?? []).map((id) => (
                            <span key={id} className="rounded-md border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[11px] font-medium text-violet-800">
                              {names.get(id) ?? id}
                            </span>
                          ))}
                          {!entry.reference.provenance_complete && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-800">
                              <TriangleAlert aria-hidden className="size-3.5" /> Incomplete provenance
                            </span>
                          )}
                        </div>
                        {entry.reference.title && (
                          <p className="mt-1 text-sm font-medium text-slate-800">{entry.reference.title}</p>
                        )}
                        <SourceLine
                          parts={[
                            entry.reference.source_name,
                            entry.reference.evidence_type
                              ? evidenceTypeLabels[entry.reference.evidence_type] ?? entry.reference.evidence_type
                              : null,
                            entry.reference.practitioner_verified ? "practitioner verified" : null,
                          ]}
                        />
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </Panel>

          <Panel title="Evidence detail" className="xl:sticky xl:top-24 xl:self-start">
            {selectedEntry ? (
              <EvidenceDetail entry={selectedEntry} output={output} onClose={() => setSelected(null)} />
            ) : (
              <EmptyState title="Select an evidence record" description="Inspect its provenance, linked claims and the candidates that depend on it." />
            )}
          </Panel>
        </div>
      </TabsContent>

      <TabsContent value="retrieved" className="mt-4">
        <Panel
          title="Open semantic retrieval"
          description="Evidence chunks retrieved by embedding similarity to the mapped symptom and concept names. Retrieval never creates a candidate."
          bodyClassName="p-0"
        >
          <div className="px-5 pt-4">
            <ScoreCaveat>{output.score_semantics.retrieval_similarity ?? "Retrieval similarity is relevance only, not clinical confidence."}</ScoreCaveat>
            {output.retrieval.mode !== "neural_embedding" && (
              <p className="mt-2 text-sm text-amber-800">
                Retrieval mode: {output.retrieval.mode.replace(/_/g, " ")}
                {output.retrieval.error ? ` — ${output.retrieval.error}` : ""}
              </p>
            )}
          </div>
          {output.retrieved_evidence.length === 0 ? (
            <EmptyState title="No retrieval hits" description="The open retrieval query returned no evidence chunks." />
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                    <th className="px-5 py-3">Chunk</th>
                    <th className="px-4 py-3">Title / source</th>
                    <th className="px-4 py-3">Similarity</th>
                    <th className="px-4 py-3">Threshold</th>
                    <th className="px-5 py-3">Linked to a traversed claim</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {output.retrieved_evidence.map((hit) => (
                    <tr key={hit.chunk_id} className="align-top">
                      <td className="px-5 py-3"><IdChip>{hit.chunk_id}</IdChip></td>
                      <td className="px-4 py-3">
                        {hit.title && <p className="font-medium text-slate-800">{hit.title}</p>}
                        <SourceLine parts={[hit.source_name]} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{formatScore(hit.similarity)}</td>
                      <td className="px-4 py-3 text-xs">{hit.below_threshold ? "Below threshold" : "At or above"}</td>
                      <td className="px-5 py-3 text-xs">
                        {hit.linked_to_traversed_claim ? "Yes" : <span className="font-medium text-amber-800">No — needs review</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </TabsContent>
    </Tabs>
  )
}

export function EvidencePage() {
  return (
    <>
      <PageHeader
        eyebrow="Component 2 · Knowledge base"
        title="Evidence explorer"
        description="Trace why an interpretation or candidate was produced: which evidence records support or contradict each claim, and how complete their provenance is."
      />
      <CaseBar />
      <WithReasoning>{(output) => <EvidenceExplorer output={output} />}</WithReasoning>
    </>
  )
}
