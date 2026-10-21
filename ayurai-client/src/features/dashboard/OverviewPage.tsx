import { Link } from "react-router"
import {
  Activity,
  ArrowUpRight,
  CircleSlash,
  ClipboardCheck,
  Clock3,
  FlaskConical,
  Leaf,
  Plus,
  ShieldCheck,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis } from "recharts"

import { SourceBadge } from "@/components/shared/case"
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
import { demoMetrics, demoScreeningTrend } from "@/lib/demo/fixtures"
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
  const { mode, cases, selectCase } = useWorkspace()
  const { checks } = useServiceHealth(mode === "live")
  const isDemo = mode === "demo"

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

      {isDemo ? (
        <Notice tone="demo" title="Illustrative figures" className="mb-5">
          The metrics and chart below are fictional examples for layout demonstration. No patient
          records or live assessments are displayed.
        </Notice>
      ) : (
        <Notice tone="info" title="Session figures only" className="mb-5">
          No analytics or case-persistence service exists yet, so these counts cover only the cases
          created in this browser session.
        </Notice>
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-4">
        <MetricCard
          title={isDemo ? "Screening sessions" : "Cases this session"}
          value={String(isDemo ? demoMetrics.screeningSessions : cases.length)}
          note={isDemo ? "Fictional example" : "Not persisted"}
          icon={Activity}
          iconStyle="bg-emerald-50 text-emerald-700"
        />
        <MetricCard
          title={isDemo ? "Awaiting review" : "Reasoning outputs"}
          value={String(isDemo ? demoMetrics.awaitingReview : reasoned.length)}
          note={isDemo ? "Fictional example" : "Component 2 responses received"}
          icon={isDemo ? ClipboardCheck : Leaf}
          iconStyle="bg-amber-50 text-amber-700"
        />
        <MetricCard
          title={isDemo ? "Safety checks" : "Safety assessments"}
          value={String(isDemo ? demoMetrics.safetyChecks : safetyRuns.length)}
          note={isDemo ? "Fictional example" : "Component 3 responses received"}
          icon={ShieldCheck}
          iconStyle="bg-sky-50 text-sky-700"
        />
        <MetricCard
          title={isDemo ? "Data quality" : "Abstentions"}
          value={isDemo ? `${demoMetrics.dataQualityPercent}%` : String(abstained.length)}
          note={isDemo ? "Fictional example" : "Component 2 declined to recommend"}
          icon={isDemo ? FlaskConical : CircleSlash}
          iconStyle="bg-violet-50 text-violet-700"
        />
      </section>

      <section className="mt-6 grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1.6fr)_minmax(330px,1fr)]">
        <Panel
          title="Screening activity"
          description={isDemo ? "Illustrative screening and review counts" : "Requires an analytics service"}
        >
          {isDemo ? (
            <>
              <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500">
                <span className="inline-flex items-center gap-2">
                  <span className="size-2 rounded-full bg-emerald-600" /> Screenings
                </span>
                <span className="inline-flex items-center gap-2">
                  <span className="size-2 rounded-full bg-teal-300" /> Reviews completed
                </span>
              </div>
              <div className="mt-4 h-[240px] w-full" role="img" aria-label="Fictional weekly screening and review counts">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={demoScreeningTrend} margin={{ top: 12, right: 4, left: -22, bottom: 0 }}>
                    <defs>
                      <linearGradient id="screeningFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#059669" stopOpacity={0.17} />
                        <stop offset="95%" stopColor="#059669" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#edf1ef" strokeDasharray="4 5" vertical={false} />
                    <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#94a3b8", fontSize: 12 }} tickMargin={12} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} />
                    <Area type="monotone" dataKey="screenings" name="Screenings" stroke="#047857" strokeWidth={2.5} fill="url(#screeningFill)" />
                    <Area type="monotone" dataKey="reviewed" name="Reviews completed" stroke="#5eead4" strokeWidth={2} fill="transparent" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
                <Clock3 aria-hidden size={14} /> Fictional 7-day period · not live service data
              </p>
            </>
          ) : (
            <EmptyState
              title="No activity data source"
              description="There is no screening analytics endpoint in the current backend, so no activity chart is shown."
            />
          )}
        </Panel>

        <Panel
          title={isDemo ? "Services" : "Service status"}
          description={isDemo ? "Health checks run in live mode only" : "Live health endpoints"}
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
                <StatusBadge spec={isDemo ? serviceStateSpecs.demo : serviceStateSpecs[check.state]} />
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
        description={isDemo ? "Fictional demo cases" : "Cases created in this session"}
        bodyClassName="p-0"
      >
        {cases.length === 0 ? (
          <EmptyState
            title="No cases yet"
            description="Create a screening to start a case. Cases are held in memory and cleared on reload."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-3">Case</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Data</th>
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
                    <td className="px-4 py-3"><SourceBadge record={record} /></td>
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
