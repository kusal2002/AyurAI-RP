import * as React from "react"
import { Link } from "react-router"
import { Plus } from "lucide-react"

import { EmptyState, IdChip, Notice, PageHeader, Panel, SearchInput } from "@/components/shared/page"
import { StatusBadge, serviceStateSpecs } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useWorkspace, type ModalityKey } from "@/context/workspace"
import { formatDateTime, formatScore } from "@/lib/labels"

const modalityLabels: Record<ModalityKey, string> = {
  conjunctiva: "Eye",
  tongue: "Tongue",
  nail: "Nail",
  ppg: "PPG",
}

export function ScreeningRecordsPage() {
  const { cases, selectCase } = useWorkspace()
  const [query, setQuery] = React.useState("")

  const filtered = cases.filter((record) => {
    const text = query.trim().toLowerCase()
    if (!text) return true
    return [record.caseRef, record.c1?.risk_tier ?? "", ...(record.c1?.symptom_ids ?? [])].some((value) =>
      value.toLowerCase().includes(text),
    )
  })

  return (
    <>
      <PageHeader
        eyebrow="Component 1 · Screening"
        title="Screening records"
        description="Screening inputs and the Component 1 summaries recorded for each case in this session."
        actions={
          <Button className="bg-emerald-700 hover:bg-emerald-800" render={<Link to="/screening/new" />} nativeButton={false}>
            <Plus /> New screening
          </Button>
        }
      />
      <Notice tone="info" className="mb-5" title="Session-only records">
        There is no screening persistence or Component 1 model service in the repository. Records live
        in this browser tab's memory and are cleared on reload. Risk tiers shown here were entered
        manually or imported from Component 1 payloads.
      </Notice>

      <Panel
        title={`${filtered.length} record${filtered.length === 1 ? "" : "s"}`}
        actions={<SearchInput value={query} onChange={setQuery} placeholder="Search case or symptom ID…" label="Search screening records" className="sm:w-64" />}
        bodyClassName="p-0"
      >
        {filtered.length === 0 ? (
          <EmptyState
            title={cases.length === 0 ? "No screening records" : "No records match your search"}
            description={cases.length === 0 ? "Start a new screening to create one." : undefined}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-3">Case</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Inputs (local)</th>
                  <th className="px-4 py-3">Risk tier</th>
                  <th className="px-4 py-3">C1 confidence</th>
                  <th className="px-4 py-3">Symptom IDs</th>
                  <th className="px-5 py-3">Origin</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((record) => {
                  const modalities = Object.keys(record.screening?.modalities ?? {}) as ModalityKey[]
                  return (
                    <tr key={record.id} className="align-top hover:bg-slate-50/70">
                      <td className="px-5 py-3">
                        <Link
                          to="/analysis"
                          onClick={() => selectCase(record.id)}
                          className="font-semibold text-slate-800 hover:text-emerald-800"
                        >
                          {record.caseRef}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(record.createdAt)}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {modalities.length === 0 ? "None" : modalities.map((key) => modalityLabels[key]).join(", ")}
                      </td>
                      <td className="px-4 py-3 capitalize">{record.c1?.risk_tier ?? "—"}</td>
                      <td className="px-4 py-3">{formatScore(record.c1?.calibrated_confidence)}</td>
                      <td className="px-4 py-3">
                        <div className="flex max-w-[220px] flex-wrap gap-1">
                          {(record.c1?.symptom_ids ?? []).map((id) => (
                            <IdChip key={id}>{id}</IdChip>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-3 text-xs text-slate-600">
                        {record.c1?.origin === "c1_payload" ? "Imported C1 payload" : "Manual entry"}
                        {record.c1?.intake.status === "success" && (
                          <div className="mt-1">
                            <StatusBadge spec={{ ...serviceStateSpecs.online, label: "Intake validated" }} />
                          </div>
                        )}
                        {record.c1?.intake.status === "error" && (
                          <div className="mt-1">
                            <StatusBadge spec={{ ...serviceStateSpecs.offline, label: "Intake check failed" }} title={record.c1.intake.error.message} />
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
