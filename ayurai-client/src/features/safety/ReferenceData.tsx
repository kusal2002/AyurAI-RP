import * as React from "react"

import { EmptyState, ErrorState, LoadingState, Panel, SearchInput } from "@/components/shared/page"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { ErrorInfo } from "@/context/workspace"
import { isAbortError, isApiError } from "@/lib/api/client"
import { component3Api } from "@/lib/api/component3"
import type { C3CypPathway, C3Drug, C3Herb, C3KnownInteraction } from "@/lib/api/types"

type Loadable<T> = { status: "loading" } | { status: "error"; error: ErrorInfo } | { status: "success"; data: T }

function useReference<T>(load: (signal: AbortSignal) => Promise<T>, enabled: boolean) {
  const [state, setState] = React.useState<Loadable<T>>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  React.useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => setState({ status: "success", data }))
      .catch((error: unknown) => {
        if (isAbortError(error)) return
        setState({
          status: "error",
          error: isApiError(error)
            ? { kind: error.kind, message: error.message, details: error.details }
            : { kind: "unknown", message: "Unexpected error", details: [] },
        })
      })
    return () => controller.abort()
  }, [load, enabled, attempt])
  return {
    state,
    retry: () => {
      setState({ status: "loading" })
      setAttempt((value) => value + 1)
    },
  }
}

function Table({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  if (rows.length === 0) return <EmptyState title="No matching records" />
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
            {headers.map((header) => (
              <th key={header} className="px-4 py-3">{header}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((cells, index) => (
            <tr key={index} className="align-top">
              {cells.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-4 py-2.5 text-xs text-slate-700">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReferenceTab<T>({
  load,
  enabled,
  label,
  filter,
  render,
}: {
  load: (signal: AbortSignal) => Promise<T[]>
  enabled: boolean
  label: string
  filter: (item: T, query: string) => boolean
  render: (items: T[]) => React.ReactNode
}) {
  const { state, retry } = useReference(load, enabled)
  const [query, setQuery] = React.useState("")
  if (state.status === "loading") return <div className="p-5"><LoadingState label={`Loading ${label} from Component 3…`} /></div>
  if (state.status === "error") return <div className="p-5"><ErrorState error={state.error} onRetry={retry} /></div>
  const text = query.trim().toLowerCase()
  const items = text ? state.data.filter((item) => filter(item, text)) : state.data
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <p className="text-xs text-slate-500">
          {items.length} of {state.data.length} records served by Component 3
        </p>
        <SearchInput value={query} onChange={setQuery} placeholder={`Search ${label}…`} label={`Search ${label}`} className="sm:w-64" />
      </div>
      {render(items)}
    </div>
  )
}

const includes = (values: (string | null | undefined)[], query: string) =>
  values.some((value) => value?.toLowerCase().includes(query))

export function ReferenceData() {
  return (
    <Panel
      title="Component 3 reference data"
      description="Curated datasets used by the Component 3 rule engine. Presence of an herb in this list does not mean it is safe."
      bodyClassName="p-0"
    >
      <Tabs defaultValue="interactions" className="pt-3">
        <div className="overflow-x-auto px-4">
          <TabsList>
            <TabsTrigger value="interactions">Known interactions</TabsTrigger>
            <TabsTrigger value="herbs">Herbs</TabsTrigger>
            <TabsTrigger value="drugs">Drugs</TabsTrigger>
            <TabsTrigger value="cyp">CYP pathways</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="interactions">
          <ReferenceTab<C3KnownInteraction>
            load={component3Api.knownInteractions}
            enabled
            label="interactions"
            filter={(item, query) => includes([item.herb, item.drug, item.mechanism, item.interaction_type], query)}
            render={(items) => (
              <Table
                headers={["Herb", "Drug", "Severity", "Type", "Mechanism", "Evidence", "Reference"]}
                rows={items.map((item) => [
                  item.herb,
                  item.drug,
                  item.severity,
                  item.interaction_type,
                  item.mechanism,
                  item.evidence_level,
                  [item.pmid ? `PMID ${item.pmid}` : null, item.citation].filter(Boolean).join(" · ") || "—",
                ])}
              />
            )}
          />
        </TabsContent>
        <TabsContent value="herbs">
          <ReferenceTab<C3Herb>
            load={component3Api.herbs}
            enabled
            label="herbs"
            filter={(item, query) => includes([item.common_name, item.botanical_name, item.sanskrit_name], query)}
            render={(items) => (
              <Table
                headers={["Herb", "Botanical name", "Active compounds", "Listed contraindications"]}
                rows={items.map((item) => [
                  item.common_name,
                  <i key="b">{item.botanical_name}</i>,
                  item.active_compounds.join(", "),
                  item.contraindications.join("; ") || "—",
                ])}
              />
            )}
          />
        </TabsContent>
        <TabsContent value="drugs">
          <ReferenceTab<C3Drug>
            load={component3Api.drugs}
            enabled
            label="drugs"
            filter={(item, query) => includes([item.generic_name, item.drug_class, ...item.brand_names], query)}
            render={(items) => (
              <Table
                headers={["Generic name", "Class", "Metabolism", "Narrow therapeutic index"]}
                rows={items.map((item) => [
                  item.generic_name,
                  item.drug_class,
                  item.metabolizing_enzymes.join(", "),
                  item.narrow_therapeutic_index ? "Yes" : "No",
                ])}
              />
            )}
          />
        </TabsContent>
        <TabsContent value="cyp">
          <ReferenceTab<C3CypPathway>
            load={component3Api.cypPathways}
            enabled
            label="CYP pathways"
            filter={(item, query) => includes([item.enzyme, ...item.substrates, ...item.inhibitors, ...item.inducers], query)}
            render={(items) => (
              <Table
                headers={["Enzyme", "Description", "Substrates", "Inhibitors", "Inducers"]}
                rows={items.map((item) => [
                  <strong key="e">{item.enzyme}</strong>,
                  item.description,
                  item.substrates.join(", "),
                  item.inhibitors.join(", ") || "—",
                  item.inducers.join(", ") || "—",
                ])}
              />
            )}
          />
        </TabsContent>
      </Tabs>
    </Panel>
  )
}
