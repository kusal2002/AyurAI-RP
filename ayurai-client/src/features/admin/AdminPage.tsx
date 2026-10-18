import { RefreshCw, ShieldOff } from "lucide-react"

import { EmptyState, KeyValueList, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, serviceStateSpecs } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useWorkspace } from "@/context/workspace"
import { useServiceHealth } from "@/lib/api/health"
import { env } from "@/lib/env"

const endpoints = [
  { service: "Component 2", method: "GET", path: "/health", use: "Service health" },
  { service: "Component 2", method: "GET", path: "/health/neo4j", use: "Knowledge graph connectivity" },
  { service: "Component 2", method: "POST", path: "/api/v1/c1/screening-result", use: "Component 1 intake validation (echo only)" },
  { service: "Component 2", method: "POST", path: "/api/v1/c2/reasoning", use: "Ayurvedic reasoning output" },
  { service: "Component 2", method: "POST", path: "/api/v1/c2/feedback", use: "Practitioner feedback" },
  { service: "Component 3", method: "GET", path: "/health", use: "Service health" },
  { service: "Component 3", method: "POST", path: "/api/v1/c2/safety-evaluation", use: "Safety assessment" },
  { service: "Component 3", method: "GET", path: "/api/v1/safety/{herbs,drugs,known-interactions,cyp-pathways}", use: "Reference data" },
]

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
