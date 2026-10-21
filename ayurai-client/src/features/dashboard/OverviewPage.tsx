import { Link } from "react-router"
import {
  Activity,
  ArrowUpRight,
  CircleSlash,
  Leaf,
  Plus,
  ShieldCheck,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { EmptyState, Notice, PageHeader, Panel } from "@/components/shared/page"
import {
  StatusBadge,
  decisionSpec,
  safetySpec,
  serviceStateSpecs,
} from "@/components/shared/status"
import { WorkflowStrip } from "@/components/shared/workflow"
import { Button } from "@/components/ui/button"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { useServiceHealth } from "@/lib/api/health"
import { formatDateTime } from "@/lib/labels"

function MetricCard({
  title,
  value,
  note,
  icon: Icon,
  iconStyle,
}: {
  title: string
  value: string
  note: string
  icon: LucideIcon
  iconStyle: string
}) {
  return (
    <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/30">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <div className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${iconStyle}`}>
          <Icon aria-hidden size={19} strokeWidth={1.8} />
        </div>
      </div>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-xs text-slate-400">{note}</p>
    </article>
  )
}

export function caseStage(record: CaseRecord): string {
  if (record.c2.status === "idle") return "Awaiting Component 2 reasoning"
  if (record.c2.status === "loading") return "Reasoning in progress"
  if (record.c2.status === "error") return "Reasoning unavailable"
  if (record.c3.status === "success") return "Awaiting practitioner review"
  if (record.c2.data.abstention.abstain) return "Abstained · practitioner review"
  return "Awaiting safety assessment"
}

export function CaseStatusBadge({ record }: { record: CaseRecord }) {
  if (record.c2.status !== "success") {
    return <span className="text-xs text-slate-500">{caseStage(record)}</span>
  }
  if (record.c3.status === "success") return <StatusBadge spec={safetySpec(record.c3.data.overall_safety_tier)} />
  return <StatusBadge spec={decisionSpec(record.c2.data.decision)} />
}

export function OverviewPage() {
  const { cases, selectCase } = useWorkspace()
  const { checks } = useServiceHealth(true)

  const reasoned = cases.filter((record) => record.c2.status === "success")
  const abstained = reasoned.filter(
    (record) => record.c2.status === "success" && record.c2.data.abstention.abstain,
  )
  const safetyRuns = cases.filter((record) => record.c3.status === "success")

  return (
    <>
      <PageHeader
        eyebrow="Clinical workspace"
        title="Overview"
        description="Follow cases from screening through Ayurvedic reasoning and safety assessment to practitioner review. Practitioner decisions stay at the centre of care."
        actions={
          <Button className="bg-emerald-700 hover:bg-emerald-800" render={<Link to="/screening/new" />} nativeButton={false}>
            <Plus /> New screening
          </Button>
        }
      />

      <Panel title="How the components work together" className="mb-6">
        <WorkflowStrip />
      </Panel>

      <Notice tone="info" title="Session figures only" className="mb-5">
          No analytics or case-persistence service exists yet, so these counts cover only the cases
          created in this browser session.
      </Notice>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-4">
        <MetricCard
          title="Cases this session"
          value={String(cases.length)}
          note="Not persisted"
          icon={Activity}
          iconStyle="bg-emerald-50 text-emerald-700"
        />
        <MetricCard
          title="Reasoning outputs"
          value={String(reasoned.length)}
          note="Component 2 responses received"
          icon={Leaf}
          iconStyle="bg-amber-50 text-amber-700"
        />
        <MetricCard
          title="Safety assessments"
          value={String(safetyRuns.length)}
          note="Component 3 responses received"
          icon={ShieldCheck}
          iconStyle="bg-sky-50 text-sky-700"
        />
        <MetricCard
          title="Abstentions"
          value={String(abstained.length)}
          note="Component 2 declined to recommend"
          icon={CircleSlash}
          iconStyle="bg-violet-50 text-violet-700"
        />
      </section>

      <section className="mt-6 grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1.6fr)_minmax(330px,1fr)]">
        <Panel
          title="Screening activity"
          description="Requires an analytics service"
        >
          <EmptyState
            title="No activity data source"
            description="There is no screening analytics endpoint in the current backend, so no activity chart is shown."
          />
        </Panel>

        <Panel
          title="Service status"
          description="Live health endpoints"
          actions={
            <Link to="/admin" className="text-xs font-semibold text-emerald-700 hover:text-emerald-900">
              Details
            </Link>
          }
        >
          <ul className="space-y-2">
            {checks.map((check) => (
              <li key={check.key} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2">
                <span className="text-sm text-slate-700">{check.label}</span>
                <StatusBadge spec={serviceStateSpecs[check.state]} />
              </li>
            ))}
            <li className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2">
              <span className="text-sm text-slate-700">Component 1 screening model</span>
              <StatusBadge spec={serviceStateSpecs.missing} />
            </li>
          </ul>
        </Panel>
      </section>

      <Panel
        className="mt-6"
        title="Recent cases"
        description="Cases created in this session"
        bodyClassName="p-0"
      >
        {cases.length === 0 ? (
          <EmptyState
            title="No cases yet"
            description="Create a screening to start a case. Cases are kept in this browser tab and cleared when it is closed."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-3">Case</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Current stage</th>
                  <th className="px-5 py-3 text-right">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cases.slice(0, 6).map((record) => (
                  <tr key={record.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3 text-sm font-semibold text-slate-800">{record.caseRef}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(record.createdAt)}</td>
                    <td className="px-4 py-3"><CaseStatusBadge record={record} /></td>
                    <td className="px-4 py-3 text-xs text-slate-600">{caseStage(record)}</td>
                    <td className="px-5 py-3 text-right">
                      <Link
                        to="/analysis"
                        onClick={() => selectCase(record.id)}
                        aria-label={`Open analysis for ${record.caseRef}`}
                        className="inline-flex rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                      >
                        <ArrowUpRight size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
