import type * as React from "react"
import { RefreshCw, ShieldOff } from "lucide-react"

import { EmptyState, KeyValueList, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, serviceStateSpecs } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useWorkspace } from "@/context/workspace"
import { useC2Readiness, useServiceHealth, type ServiceState } from "@/lib/api/health"
import type { ReadinessResponse } from "@/lib/api/types"
import { env } from "@/lib/env"

const endpoints = [
  { service: "Component 2", method: "GET", path: "/health", use: "Service health" },
  { service: "Component 2", method: "GET", path: "/health/neo4j", use: "Database connectivity only (read-only query)" },
  { service: "Component 2", method: "GET", path: "/health/readiness", use: "Connectivity, schema, content, ingestion, retrieval, model" },
  { service: "Component 2", method: "GET", path: "/health/graph-validation", use: "Read-only graph integrity validation" },
  { service: "Component 2", method: "POST", path: "/api/v1/c1/screening-result", use: "Component 1 intake validation (echo only)" },
  { service: "Component 2", method: "POST", path: "/api/v1/c2/reasoning", use: "Ayurvedic reasoning output" },
  { service: "Component 2", method: "POST", path: "/api/v1/c2/feedback", use: "Practitioner feedback" },
  { service: "Component 3", method: "GET", path: "/health", use: "Service health" },
  { service: "Component 3", method: "POST", path: "/api/v1/c2/safety-evaluation", use: "Safety assessment" },
  { service: "Component 3", method: "GET", path: "/api/v1/safety/{herbs,drugs,known-interactions,cyp-pathways}", use: "Reference data" },
]

type StatusRow = { label: string; state: ServiceState; detail: string }

function plural(count: number | null | undefined, noun: string): string {
  const value = count ?? 0
  return `${value} ${noun}${value === 1 ? "" : "s"}`
}

function encryptionNote(encrypted: boolean | null | undefined): string {
  if (encrypted === true) return " · TLS"
  if (encrypted === false) return " · not encrypted"
  return ""
}

function modelNote(loaded: boolean, cached: boolean | null): string {
  if (loaded) return "loaded"
  if (cached) return "cached locally, not loaded yet"
  if (cached === false) return "not in the local cache"
  return "cache state unknown"
}

/** One row per concern: a reachable database is not evidence of usable knowledge. */
function readinessRows(data: ReadinessResponse): StatusRow[] {
  const c = data.components
  const db = c.database_connectivity
  const schema = c.graph_schema
  const content = c.knowledge_graph_content
  const corpus = c.local_corpus_ingestion
  const retrieval = c.retrieval_service
  const model = c.embedding_model
  const counts = content.node_counts ?? {}

  let schemaDetail = schema.detail ?? "Unknown"
  if (schema.status === "core_constraints_present") {
    schemaDetail = `Core constraints present · source-provenance schema ${schema.stage_e_applied ? "applied" : "not applied yet"}`
  } else if (schema.status === "missing_constraints") {
    schemaDetail = `Missing: ${(schema.missing_core_constraints ?? []).join(", ")}`
  }

  let retrievalDetail = "Not initialised: the index is built on the first reasoning request"
  if (retrieval.status === "ready") {
    retrievalDetail = `Evidence index built: ${plural(retrieval.indexed_evidence, "evidence record")}, ${plural(retrieval.indexed_chunks, "chunk")}`
  } else if (retrieval.status === "unavailable") {
    retrievalDetail = retrieval.last_error ?? "Unavailable"
  }

  return [
    {
      label: "Database connectivity",
      state: db.status === "healthy" ? "online" : "offline",
      detail: `${db.detail ?? db.status}${encryptionNote(db.encrypted)}`,
    },
    {
      label: "Graph schema",
      state: schema.status === "core_constraints_present" ? "online" : "offline",
      detail: schemaDetail,
    },
    {
      label: "Knowledge graph content",
      state:
        content.status === "populated"
          ? "online"
          : content.status === "empty" || content.status === "provisional_only"
            ? "degraded"
            : "offline",
      detail:
        content.status === "unknown"
          ? (content.detail ?? "Unknown")
          : `${plural(counts.Claim, "approved claim")}, ${plural(counts.Evidence, "evidence record")}, ${plural(counts.ProvisionalClaim, "provisional (unverified) claim")}, ${plural(counts.Source, "source")}. ${content.note ?? ""}`,
    },
    {
      label: "Knowledge ingestion (local corpus)",
      state: corpus.status === "present" && corpus.approved_candidates ? "online" : "degraded",
      detail:
        corpus.status === "present"
          ? `${plural(corpus.sources, "source")}, ${corpus.processed ?? 0} extracted, ${corpus.needs_ocr_or_review ?? 0} need OCR · ${plural(corpus.candidate_claims, "candidate claim")}, ${corpus.approved_candidates ?? 0} approved`
          : (corpus.detail ?? corpus.status),
    },
    {
      label: "Retrieval service",
      state: retrieval.status === "ready" ? "online" : retrieval.status === "unavailable" ? "offline" : "degraded",
      detail: retrievalDetail,
    },
    {
      label: "Embedding model",
      state: model.loaded ? "online" : model.cached_locally ? "degraded" : "offline",
      detail: `${model.model_id} · ${modelNote(model.loaded, model.cached_locally)}`,
    },
    {
      label: "Component integration",
      state: "online",
      detail: Object.values(c.component_integration).join(" · "),
    },
  ]
}

function C2SystemStatus({ live }: { live: boolean }) {
  const { state, refresh } = useC2Readiness(live)
  let body: React.ReactNode
  if (!live) {
    body = <EmptyState title="Status checks run in live mode" description="Switch to live mode to read GET /health/readiness." />
  } else if (state.status === "error") {
    body = (
      <Notice tone="critical" title="Readiness report unavailable">
        {state.message}
      </Notice>
    )
  } else if (state.status !== "success") {
    body = <p className="text-sm text-slate-500">Checking…</p>
  } else {
    const { data } = state
    body = (
      <>
        <div className="mb-3 flex flex-wrap gap-2">
          <StatusBadge
            spec={{
              ...serviceStateSpecs[data.ready_for_reasoning ? "online" : "offline"],
              label: data.ready_for_reasoning ? "Ready for reasoning requests" : "Not ready for reasoning",
            }}
          />
          <StatusBadge
            spec={{
              ...serviceStateSpecs[data.knowledge_available ? "online" : "degraded"],
              label: data.knowledge_available ? "Approved knowledge stored" : "No approved knowledge: requests abstain",
            }}
          />
        </div>
        <ul className="space-y-2">
          {readinessRows(data).map((row) => (
            <li key={row.label} className="rounded-lg border border-slate-200 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-800">{row.label}</span>
                <StatusBadge spec={serviceStateSpecs[row.state]} />
              </div>
              <p className="mt-0.5 text-xs break-words text-slate-500">{row.detail}</p>
            </li>
          ))}
        </ul>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-500">
          {data.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-400">Reported at {new Date(data.generated_at).toLocaleString()}</p>
      </>
    )
  }

  return (
    <Panel
      title="Component 2 system status"
      description="Each concern is checked separately. A connected database does not mean the corpus is complete or that recommendations are valid."
      className="mt-6"
      actions={
        live ? (
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw /> Re-check
          </Button>
        ) : undefined
      }
    >
      {body}
    </Panel>
  )
}

export function AdminPage() {
  const { mode } = useWorkspace()
  const live = mode === "live"
  const { checks, refresh } = useServiceHealth(live)

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Administration"
        description="Service configuration and connectivity for this client."
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel
          title="Service health"
          actions={
            live ? (
              <Button variant="outline" size="sm" onClick={refresh}>
                <RefreshCw /> Re-check
              </Button>
            ) : undefined
          }
        >
          {live ? (
            <ul className="space-y-2">
              {checks.map((check) => (
                <li key={check.key} className="rounded-lg border border-slate-200 px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-slate-800">{check.label}</span>
                    <StatusBadge spec={serviceStateSpecs[check.state]} />
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {check.endpoint}
                    {check.message ? ` · ${check.message}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="Health checks run in live mode" description="Switch to live mode to check the configured services." />
          )}
        </Panel>

        <Panel title="Client configuration">
          <KeyValueList
            items={[
              { label: "Data mode", value: live ? "Live" : "Demo" },
              { label: "Component 2 base URL", value: <code className="text-xs">{env.c2BaseUrl}</code> },
              { label: "Component 3 base URL", value: <code className="text-xs">{env.c3BaseUrl}</code> },
              { label: "Default request timeout", value: `${env.timeoutMs / 1000} s` },
              { label: "Reasoning / feedback timeout", value: `${env.reasoningTimeoutMs / 1000} s` },
            ]}
          />
          <p className="mt-3 text-xs text-slate-500">
            Configure with <code>VITE_*</code> variables (see <code>.env.example</code>). The dev server proxies{" "}
            <code>/c2-api</code> and <code>/c3-api</code> to the service ports.
          </p>
        </Panel>
      </div>

      <C2SystemStatus live={live} />

      <Panel title="Integrated endpoints" className="mt-6" bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                <th className="px-5 py-3">Service</th>
                <th className="px-4 py-3">Method</th>
                <th className="px-4 py-3">Path</th>
                <th className="px-5 py-3">Used for</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {endpoints.map((endpoint) => (
                <tr key={`${endpoint.service}-${endpoint.method}-${endpoint.path}`}>
                  <td className="px-5 py-2.5 text-slate-700">{endpoint.service}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{endpoint.method}</td>
                  <td className="px-4 py-2.5 font-mono text-xs break-all">{endpoint.path}</td>
                  <td className="px-5 py-2.5 text-slate-600">{endpoint.use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Users and roles" className="mt-6">
        <Notice tone="neutral" icon={ShieldOff} title="Not available">
          No authentication or authorization service exists in the current backend, so user and role management is not
          implemented. Server-side authorization must be added before any real-data use.
        </Notice>
      </Panel>
    </>
  )
}
