import { CheckCircle2, RefreshCw, ShieldAlert, XCircle } from "lucide-react"
import {
  CartesianGrid,
  ErrorBar,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { EmptyState, ErrorState, LoadingState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, type StatusSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { useWorkspace } from "@/context/workspace"
import type { BaselineRow, SummaryRow } from "@/lib/api/component4"
import { C4SignInRequired, RealDataNotice, baselineLabels, strategyStyle, useFederationData } from "./shared"

const withinTarget: StatusSpec = { label: "Within target", tone: "positive", icon: CheckCircle2 }
const overTarget: StatusSpec = { label: "Over target", tone: "critical", icon: XCircle }

type Metric = "accuracy" | "f1"

/** One chart row per ε, with mean ± std accuracy and macro-F1 for each strategy. */
function curveRows(summary: SummaryRow[]) {
  const byEpsilon = new Map<number, Record<string, number>>()
  for (const row of summary) {
    const eps = Number(row.target_epsilon)
    const entry = byEpsilon.get(eps) ?? { epsilon: eps }
    entry[`${row.strategy}_accuracy`] = Number(row.final_accuracy_mean)
    entry[`${row.strategy}_accuracy_std`] = Number(row.final_accuracy_std)
    if (row.final_macro_f1_mean !== undefined) {
      entry[`${row.strategy}_f1`] = Number(row.final_macro_f1_mean)
      entry[`${row.strategy}_f1_std`] = Number(row.final_macro_f1_std ?? 0)
    }
    byEpsilon.set(eps, entry)
  }
  return [...byEpsilon.values()].sort((a, b) => a.epsilon - b.epsilon)
}

/** Horizontal reference lines drawn on the curves (from results/baselines.csv). */
const referenceStyle: Partial<Record<BaselineRow["method"], { short: string; color: string }>> = {
  majority_class: { short: "always most common tier", color: "#94a3b8" },
  centralised_no_dp: { short: "centralised, no DP", color: "#0369a1" },
  fedprox_no_dp: { short: "FedProx, no DP", color: "#047857" },
}

function TradeoffChart({ rows, metric, baselines }: { rows: Record<string, number>[]; metric: Metric; baselines: BaselineRow[] | null }) {
  const label = metric === "accuracy" ? "Final accuracy" : "Final macro-F1"
  return (
    <div className="h-72 w-full" role="img" aria-label={`${label} versus privacy budget epsilon for FedAvg and FedProx`}>
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis
            dataKey="epsilon"
            type="number"
            scale="log"
            domain={["dataMin", "dataMax"]}
            ticks={rows.map((row) => row.epsilon)}
            tick={{ fontSize: 11 }}
            label={{ value: "ε (log scale)", position: "insideBottom", offset: -4, fontSize: 11 }}
          />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} width={44} />
          <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(3) : value)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {baselines?.map((b) => {
            const style = referenceStyle[b.method]
            if (!style) return null
            const y = Number(metric === "accuracy" ? b.accuracy_mean : b.macro_f1_mean)
            return (
              <ReferenceLine
                key={b.method}
                y={y}
                stroke={style.color}
                strokeDasharray="2 4"
                label={{ value: style.short, fontSize: 10, fill: style.color, position: "insideTopLeft" }}
              />
            )
          })}
          {(["fedprox", "fedavg"] as const).map((key) => (
            <Line
              key={key}
              dataKey={`${key}_${metric}`}
              name={strategyStyle[key].label}
              stroke={strategyStyle[key].color}
              strokeDasharray={strategyStyle[key].dash}
              strokeWidth={2}
              dot={{ r: 3 }}
            >
              <ErrorBar dataKey={`${key}_${metric}_std`} width={4} stroke={strategyStyle[key].color} />
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function PrivacyPage() {
  const { user } = useAuth()
  const { mode } = useWorkspace()
  const { state, reload } = useFederationData()

  const header = (
    <PageHeader
      eyebrow="Component 4 · Differential privacy"
      title="Privacy budget"
      description="Opacus clips every patient's gradient and adds Gaussian noise before a model update leaves a clinic. Smaller ε means stronger privacy and more noise. δ is fixed at 10⁻⁵."
      actions={user && mode === "live" ? <Button variant="outline" size="sm" onClick={reload}><RefreshCw /> Refresh</Button> : undefined}
    />
  )

  if (mode !== "live" || !user) return <>{header}<C4SignInRequired what="Privacy budget results" /></>
  if (state.status === "loading") return <>{header}<LoadingState label="Loading privacy results…" /></>
  if (state.status === "error") return <>{header}<ErrorState error={state.error} onRetry={reload} /></>

  const { config, summary, baselines } = state.data
  if (!summary || summary.length === 0) {
    return (
      <>
        {header}
        <EmptyState icon={ShieldAlert} title="No sweep summary yet" description="Run component4/federated/sweep.py to produce results/summary.csv." />
      </>
    )
  }

  const rows = curveRows(summary)
  const dataSource = summary[0].data_source
  const hasF1 = summary[0].final_macro_f1_mean !== undefined

  return (
    <>
      {header}
      {config.real_data && !dataSource.startsWith("PLACEHOLDER") ? (
        <RealDataNotice config={config} />
      ) : (
        <Notice tone="caution" className="mb-5" title="Placeholder training data">
          The results below were measured on placeholder features ({dataSource}) and are not clinical results. The ε
          accounting is real: it comes from Opacus&apos; privacy accountant.
        </Notice>
      )}

      <Panel
        className="mb-5"
        title="Privacy–utility trade-off"
        description={`Final-round results (mean ± standard deviation over ${summary[0].runs} runs) at each privacy budget. Dotted lines are the reference points without differential privacy.`}
      >
        <div className={hasF1 ? "grid grid-cols-1 gap-6 xl:grid-cols-2" : undefined}>
          <div>
            <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Accuracy</h3>
            <TradeoffChart rows={rows} metric="accuracy" baselines={baselines} />
          </div>
          {hasF1 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Macro-F1 (all tiers weighted equally)
              </h3>
              <TradeoffChart rows={rows} metric="f1" baselines={baselines} />
            </div>
          )}
        </div>
      </Panel>

      {baselines && baselines.length > 0 && (
        <Panel
          className="mb-5"
          title="Reference points (no differential privacy)"
          description="Compare the curves with these: the gap to centralised training is the cost of federation; the gap to federated-without-DP is the cost of privacy."
          bodyClassName="p-0"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-3">Method</th>
                  <th className="px-4 py-3">Accuracy</th>
                  <th className="px-4 py-3">Macro-F1</th>
                  <th className="px-5 py-3">Runs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {baselines.map((b) => (
                  <tr key={b.method}>
                    <td className="px-5 py-3 font-medium text-slate-800">{baselineLabels[b.method] ?? b.method}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {Number(b.accuracy_mean).toFixed(3)} ± {Number(b.accuracy_std).toFixed(3)}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{Number(b.macro_f1_mean).toFixed(3)}</td>
                    <td className="px-5 py-3 text-slate-500">{b.runs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <Panel
        title="Budget spent vs target"
        description="Evaluation metric from the proposal: the ε actually spent (Opacus accountant, worst clinic) must stay within the target."
        bodyClassName="p-0"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                <th className="px-5 py-3">Strategy</th>
                <th className="px-4 py-3">Target ε</th>
                <th className="px-4 py-3">ε spent (max)</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Final accuracy</th>
                {hasF1 && <th className="px-4 py-3">Final macro-F1</th>}
                <th className="px-5 py-3">Runs × rounds</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.map((row) => {
                const spent = Number(row.epsilon_spent_max)
                const target = Number(row.target_epsilon)
                return (
                  <tr key={`${row.strategy}-${row.target_epsilon}`}>
                    <td className="px-5 py-3 font-medium text-slate-800">{strategyStyle[row.strategy].label}</td>
                    <td className="px-4 py-3">{target}</td>
                    <td className="px-4 py-3 tabular-nums">{spent.toFixed(4)}</td>
                    <td className="px-4 py-3"><StatusBadge spec={spent <= target ? withinTarget : overTarget} /></td>
                    <td className="px-4 py-3 tabular-nums">
                      {Number(row.final_accuracy_mean).toFixed(3)} ± {Number(row.final_accuracy_std).toFixed(3)}
                    </td>
                    {hasF1 && (
                      <td className="px-4 py-3 tabular-nums">
                        {Number(row.final_macro_f1_mean).toFixed(3)} ± {Number(row.final_macro_f1_std ?? 0).toFixed(3)}
                      </td>
                    )}
                    <td className="px-5 py-3 text-slate-500">{row.runs} × {row.rounds}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  )
}
