import { Link } from "react-router"
import { ArrowRight, ClipboardCheck, Leaf, ShieldCheck, Stethoscope } from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { EmptyState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { CaseStatusBadge, caseStage } from "@/features/dashboard/OverviewPage"
import { formatDateTime } from "@/lib/labels"
import { cn } from "@/lib/utils"

function StageDot({ icon: Icon, label, state }: { icon: LucideIcon; label: string; state: "done" | "active" | "todo" | "failed" }) {
  const stateLabel = { done: "complete", active: "in progress", todo: "not started", failed: "unavailable" }[state]
  return (
    <span className="flex items-center gap-1.5 text-xs" title={`${label}: ${stateLabel}`}>
      <span
        className={cn(
          "flex size-6 items-center justify-center rounded-full ring-1",
          state === "done" && "bg-emerald-50 text-emerald-700 ring-emerald-200",
          state === "active" && "bg-sky-50 text-sky-700 ring-sky-200",
          state === "todo" && "bg-slate-50 text-slate-400 ring-slate-200",
          state === "failed" && "bg-rose-50 text-rose-700 ring-rose-200",
        )}
      >
        <Icon aria-hidden className="size-3.5" />
      </span>
      <span className="sr-only">
        {label}: {stateLabel}
      </span>
    </span>
  )
}

function stageStates(record: CaseRecord) {
  const asyncState = (status: string) =>
    status === "success" ? "done" : status === "loading" ? "active" : status === "error" ? "failed" : "todo"
  return {
    c1: record.c1 ? ("done" as const) : ("todo" as const),
    c2: asyncState(record.c2.status) as "done" | "active" | "todo" | "failed",
    c3: asyncState(record.c3.status) as "done" | "active" | "todo" | "failed",
    review: record.feedback.length > 0 ? ("active" as const) : ("todo" as const),
  }
}

export function PatientCasesPage() {
  const { cases, activeCase, selectCase } = useWorkspace()

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Patient cases"
        description="Each case links one screening summary to its Component 2 reasoning, Component 3 safety assessment and practitioner review."
      />
      <Notice tone="info" className="mb-5" title="No patient records service">
        Cases are identified only by a pseudonymous reference and exist in this browser session. No
        patient demographics are stored, and nothing is retrieved from a patient database.
      </Notice>

      {cases.length === 0 ? (
        <Panel>
          <EmptyState
            title="No cases in this session"
            description="Create a screening to open a case."
            action={
              <Button className="bg-emerald-700 hover:bg-emerald-800" render={<Link to="/screening/new" />} nativeButton={false}>
                <Stethoscope /> New screening
              </Button>
            }
          />
        </Panel>
      ) : (
        <ul className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {cases.map((record) => {
            const states = stageStates(record)
            const active = activeCase?.id === record.id
            return (
              <li
                key={record.id}
                className={cn(
                  "rounded-2xl border bg-white p-5 shadow-sm shadow-slate-200/30",
                  active ? "border-emerald-300 ring-1 ring-emerald-100" : "border-slate-200/80",
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-slate-900">{record.caseRef}</p>
                    <p className="text-xs text-slate-500">Created {formatDateTime(record.createdAt)}</p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2" aria-label="Workflow progress">
                  <StageDot icon={Stethoscope} label="Screening summary" state={states.c1} />
                  <ArrowRight aria-hidden className="size-3 text-slate-300" />
                  <StageDot icon={Leaf} label="Ayurvedic reasoning" state={states.c2} />
                  <ArrowRight aria-hidden className="size-3 text-slate-300" />
                  <StageDot icon={ShieldCheck} label="Safety assessment" state={states.c3} />
                  <ArrowRight aria-hidden className="size-3 text-slate-300" />
                  <StageDot icon={ClipboardCheck} label="Practitioner review" state={states.review} />
                  <span className="ml-2 text-xs text-slate-600">{caseStage(record)}</span>
                </div>
                <div className="mt-3">
                  <CaseStatusBadge record={record} />
                </div>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                  {[
                    { to: "/analysis", label: "Analysis" },
                    { to: "/candidates", label: "Candidates" },
                    { to: "/safety", label: "Safety" },
                    { to: "/review", label: "Review" },
                  ].map((link) => (
                    <Button
                      key={link.to}
                      variant="outline"
                      size="sm"
                      render={<Link to={link.to} onClick={() => selectCase(record.id)} />}
                      nativeButton={false}
                    >
                      {link.label}
                    </Button>
                  ))}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}
