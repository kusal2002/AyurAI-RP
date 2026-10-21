import * as React from "react"
import { Network, RefreshCw } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { EmptyState, ErrorState, FilterChips, KeyValueList, LoadingState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { useWorkspace } from "@/context/workspace"
import type { FederationRun } from "@/lib/api/component4"
import { C4SignInRequired, RealDataNotice, meanByRound, strategyStyle, useFederationData } from "./shared"

/** Merge FedAvg and FedProx per-round means into one array for a chart. */
function chartRows(runs: FederationRun[], epsilon: number) {
  const fedavg = meanByRound(runs, "fedavg", epsilon)
  const fedprox = meanByRound(runs, "fedprox", epsilon)
  const rounds = new Map<number, Record<string, number | null>>()
  for (const [key, series] of [["fedavg", fedavg], ["fedprox", fedprox]] as const) {
    for (const row of series.rounds) {
      const entry = rounds.get(row.round) ?? { round: row.round }
      entry[`${key}_accuracy`] = row.accuracy
      entry[`${key}_f1`] = row.macro_f1
      entry[`${key}_loss`] = row.loss
      entry[`${key}_eps`] = row.epsilon_spent
      rounds.set(row.round, entry)
    }
  }
  return {
    rows: [...rounds.values()].sort((a, b) => (a.round ?? 0) - (b.round ?? 0)),
    runCounts: { fedavg: fedavg.runCount, fedprox: fedprox.runCount },
  }
}

function MetricChart({
  rows,
  metric,
  label,
  target,
}: {
  rows: Record<string, number | null>[]
  metric: "accuracy" | "f1" | "loss" | "eps"
  label: string
  target?: number
}) {
  return (
    <div className="h-64 w-full" role="img" aria-label={`${label} per round, FedAvg versus FedProx`}>
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="round" tick={{ fontSize: 11 }} label={{ value: "Round", position: "insideBottom", offset: -2, fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={44} />
          <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(4) : value)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {target !== undefined && (
            <ReferenceLine y={target} stroke="#be123c" strokeDasharray="3 3" label={{ value: `target ε = ${target}`, fontSize: 11, fill: "#be123c", position: "insideTopRight" }} />
          )}
          {(["fedprox", "fedavg"] as const).map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={`${key}_${metric}`}
              name={strategyStyle[key].label}
              stroke={strategyStyle[key].color}
              strokeDasharray={strategyStyle[key].dash}
              strokeWidth={2}
              dot={{ r: 2 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function ClinicDistribution({ clinics }: { clinics: { clinic_id: number; name: string; low: number; moderate: number; high: number }[] }) {
  const rows = clinics.map((clinic) => ({ ...clinic, label: `Clinic ${clinic.clinic_id}` }))
  return (
    <div className="h-56 w-full" role="img" aria-label="Risk-tier label counts per clinic (non-IID split)">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={64} />
          <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.name ?? ""} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="low" name="Low" stackId="tier" fill="#6ee7b7" />
          <Bar dataKey="moderate" name="Moderate" stackId="tier" fill="#fbbf24" />
          <Bar dataKey="high" name="High" stackId="tier" fill="#e11d48" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function FederationPage() {
  const { user } = useAuth()
  const { mode } = useWorkspace()
  const { state, reload } = useFederationData()
  const [epsilon, setEpsilon] = React.useState<string>("2")

  const header = (
    <PageHeader
      eyebrow="Component 4 · Federated learning"
      title="Federated training"
      description="Three simulated clinic nodes train one anemia risk model without sharing raw data. FedProx (proposed) is compared with FedAvg (baseline) under the same non-IID split and differential-privacy budget."
      actions={user && mode === "live" ? <Button variant="outline" size="sm" onClick={reload}><RefreshCw /> Refresh</Button> : undefined}
    />
  )

  if (mode !== "live" || !user) return <>{header}<C4SignInRequired what="Federated training results" /></>
  if (state.status === "loading") return <>{header}<LoadingState label="Loading federated training results…" /></>
  if (state.status === "error") return <>{header}<ErrorState error={state.error} onRetry={reload} /></>

  const { config, runs, summary } = state.data
  const selected = Number(epsilon)
  const { rows, runCounts } = chartRows(runs, selected)
  const dataSource = summary?.[0]?.data_source

  return (
    <>
      {header}
      {config.real_data ? (
        <RealDataNotice config={config} />
      ) : (
        <Notice tone="caution" className="mb-5" title="Placeholder training data">
          These runs use placeholder features{dataSource ? ` (${dataSource})` : ""}. The pipeline, privacy accounting
          and aggregation are real, but accuracy values are not meaningful until the Component 1 dataset is connected.
        </Notice>
      )}

      <div className="mb-5 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Panel title="Experiment configuration">
          <KeyValueList
            items={[
              { label: "Clinic nodes", value: config.num_clinics },
              { label: "Federated rounds", value: config.num_rounds },
              { label: "Local epochs per round", value: config.local_epochs },
              { label: "Learning rate", value: config.learning_rate },
              { label: "FedProx proximal term μ", value: config.proximal_mu },
              { label: "DP failure probability δ", value: config.delta.toExponential(0) },
              { label: "Gradient clipping bound C", value: config.max_grad_norm },
              { label: "Privacy budgets ε tested", value: config.epsilons.join(", ") },
            ]}
          />
        </Panel>
        <Panel title="Clinic nodes — non-IID label distribution" description="Each clinic keeps its own data; only DP-noised model updates leave the node.">
          <ClinicDistribution clinics={config.clinics} />
        </Panel>
      </div>

      <Panel
        title="FedProx vs FedAvg per round"
        description={`Mean over ${Math.max(runCounts.fedavg, runCounts.fedprox)} run(s) at the selected privacy budget.`}
        actions={
          <FilterChips
            label="Privacy budget"
            value={epsilon}
            onChange={setEpsilon}
            options={config.epsilons.map((eps) => ({ value: String(eps), label: `ε = ${eps}` }))}
          />
        }
      >
        {rows.length === 0 ? (
          <EmptyState icon={Network} title="No runs for this ε yet" description="Run component4/federated/sweep.py to generate results." />
        ) : (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Global accuracy</h3>
              <MetricChart rows={rows} metric="accuracy" label="Accuracy" />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Global macro-F1 (all tiers weighted equally)
              </h3>
              <MetricChart rows={rows} metric="f1" label="Macro-F1" />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Global loss</h3>
              <MetricChart rows={rows} metric="loss" label="Loss" />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Privacy budget spent (ε)</h3>
              <MetricChart rows={rows} metric="eps" label="Epsilon spent" target={selected} />
            </div>
          </div>
        )}
      </Panel>
    </>
  )
}
