import * as React from "react"
import { Link } from "react-router"
import { FolderOpen, Leaf, Play, Stethoscope } from "lucide-react"

import { EmptyState, ErrorState, IdChip, LoadingState, Panel } from "@/components/shared/page"
import { StatusBadge, demoSpec, serviceStateSpecs } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import type { Component2Output } from "@/lib/api/types"
import { formatDateTime } from "@/lib/labels"

export function SourceBadge({ record }: { record: CaseRecord }) {
  return record.source === "demo" ? (
    <StatusBadge spec={demoSpec} />
  ) : (
    <StatusBadge spec={{ ...serviceStateSpecs.online, label: "Live service data" }} />
  )
}

/** Active-case selector shown at the top of case-level screens. */
export function CaseBar() {
  const { cases, activeCase, selectCase } = useWorkspace()
  if (cases.length === 0) return null

  return (
    <div className="mb-5 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <FolderOpen aria-hidden className="size-4 shrink-0 text-emerald-700" />
        <label className="flex min-w-0 items-center gap-2 text-xs text-slate-500">
          <span className="shrink-0">Active case</span>
          <select
            value={activeCase?.id ?? ""}
            onChange={(event) => selectCase(event.target.value)}
            className="h-8 min-w-0 rounded-lg border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-800 focus:border-emerald-500 focus:outline-none"
          >
            {cases.map((record) => (
              <option key={record.id} value={record.id}>
                {record.caseRef} · {formatDateTime(record.createdAt)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {activeCase && (
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge record={activeCase} />
          {activeCase.c2.status === "success" && (
            <span className="text-xs text-slate-500">
              C2 request <IdChip>{activeCase.c2.data.request_id}</IdChip>
            </span>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Renders children only when the active case has a Component 2 output.
 * Otherwise shows the appropriate empty / loading / error state.
 */
export function WithReasoning({
  children,
}: {
  children: (output: Component2Output, record: CaseRecord) => React.ReactNode
}) {
  const { activeCase, runReasoning } = useWorkspace()

  if (!activeCase) {
    return (
      <Panel>
        <EmptyState
          icon={Stethoscope}
          title="No case in this session"
          description="Start a screening and enter the approved Component 1 summary to run Component 2 reasoning. Cases exist only in this browser tab."
          action={
            <Button className="bg-emerald-700 hover:bg-emerald-800" render={<Link to="/screening/new" />} nativeButton={false}>
              <Stethoscope /> New screening
            </Button>
          }
        />
      </Panel>
    )
  }

  const state = activeCase.c2
  if (state.status === "idle") {
    return (
      <Panel>
        <EmptyState
          icon={Leaf}
          title="Component 2 reasoning has not been run for this case"
          description="Run reasoning to request the Ayurvedic interpretation, evidence and candidates from the Component 2 service."
          action={
            <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={() => runReasoning(activeCase.id)}>
              <Play /> Run Component 2 reasoning
            </Button>
          }
        />
      </Panel>
    )
  }
  if (state.status === "loading") {
    return (
      <Panel>
        <LoadingState label="Waiting for the Component 2 reasoning service… The first request can take longer while the embedding model loads." />
      </Panel>
    )
  }
  if (state.status === "error") {
    return (
      <Panel>
        <ErrorState
          title="Component 2 reasoning output is unavailable"
          error={state.error}
          onRetry={() => runReasoning(activeCase.id)}
        />
        <p className="mt-3 text-xs text-slate-500">
          No interpretation, evidence or candidates are shown because the service did not return
          them. Nothing is substituted.
        </p>
      </Panel>
    )
  }
  return <>{children(state.data, activeCase)}</>
}
