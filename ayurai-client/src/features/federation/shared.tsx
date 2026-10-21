import * as React from "react"
import { Link } from "react-router"
import { LogIn } from "lucide-react"

import { Notice } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { toErrorInfo, type ErrorInfo } from "@/context/workspace"
import { isAbortError, isApiError } from "@/lib/api/client"
import {
  component4Api,
  type BaselineRow,
  type FederationConfig,
  type FederationRun,
  type SummaryRow,
} from "@/lib/api/component4"

/** Display names for the reference points in results/baselines.csv. */
export const baselineLabels: Record<BaselineRow["method"], string> = {
  majority_class: "Always predict the most common tier",
  centralised_no_dp: "Centralised training (data pooled, no DP)",
  fedavg_no_dp: "FedAvg without DP",
  fedprox_no_dp: "FedProx without DP",
}

/** Shown when the results come from the real CP-AnemiC data. */
export function RealDataNotice({ config }: { config: FederationConfig }) {
  const patients = config.clinics.reduce((sum, c) => sum + c.low + c.moderate + c.high, 0)
  return (
    <Notice tone="info" className="mb-5" title="Real data: CP-AnemiC v2 (Component 1 dataset)">
      {patients} patients' conjunctiva photos, each summarised as 10 colour (pallor) features, labelled with lab
      haemoglobin: High risk Hb &lt; {config.hb_thresholds.high_risk_below}, Moderate below{" "}
      {config.hb_thresholds.low_risk_from}, otherwise Low. The dataset is small and imbalanced, so macro-F1 is shown
      next to accuracy and results vary between runs.
    </Notice>
  )
}

/** Series colours: FedProx (proposed) in brand green, FedAvg (baseline) in slate. */
export const strategyStyle = {
  fedprox: { label: "FedProx (μ = 0.1)", color: "#047857", dash: undefined },
  fedavg: { label: "FedAvg (baseline)", color: "#64748b", dash: "5 4" },
} as const

/**
 * Component 4 data is only shown to signed-in users in live mode.
 * Demo mode does not invent federated-learning results.
 */
export function C4SignInRequired({ what }: { what: string }) {
  return (
    <Notice tone="neutral" icon={LogIn} title="Sign in to view Component 4 data">
      <p>
        {what} come from the Component 4 service and are not simulated in demo mode. Sign in to switch to live mode.
      </p>
      <Button size="sm" className="mt-2 bg-emerald-700 hover:bg-emerald-800" render={<Link to="/login" />} nativeButton={false}>
        <LogIn /> Sign in
      </Button>
    </Notice>
  )
}

type FederationData = {
  config: FederationConfig
  runs: FederationRun[]
  summary: SummaryRow[] | null // null until federated/sweep.py has been run
  baselines: BaselineRow[] | null // null until the sweep has produced baselines.csv
}

// A 404 just means "not produced yet", which is not an error for the page
const nullIf404 = (error: unknown) => (isApiError(error) && error.status === 404 ? null : Promise.reject(error))

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ErrorInfo }
  | { status: "success"; data: FederationData }

/** Load experiment config, per-round runs and the summary in parallel. */
export function useFederationData() {
  const { user } = useAuth()
  const [state, setState] = React.useState<LoadState>({ status: "loading" })
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    if (!user) return
    const controller = new AbortController()
    Promise.all([
      component4Api.federationConfig(controller.signal),
      component4Api.federationRuns(controller.signal),
      component4Api.federationSummary(controller.signal).catch(nullIf404),
      component4Api.federationBaselines(controller.signal).catch(nullIf404),
    ])
      .then(([config, runs, summary, baselines]) =>
        setState({ status: "success", data: { config, runs, summary, baselines } }),
      )
      .catch((error) => {
        if (!isAbortError(error)) setState({ status: "error", error: toErrorInfo(error) })
      })
    return () => controller.abort()
  }, [user, tick])

  // Show the loading state from the click handler, not from inside the effect
  const reload = () => {
    setState({ status: "loading" })
    setTick((value) => value + 1)
  }
  return { state, reload }
}

/** Average the per-round metrics of all runs with the same strategy and ε. */
export function meanByRound(runs: FederationRun[], strategy: string, epsilon: number) {
  const matching = runs.filter((run) => run.strategy === strategy && run.epsilon === epsilon)
  const byRound = new Map<number, { accuracy: number[]; f1: number[]; loss: number[]; eps: number[] }>()
  for (const run of matching) {
    for (const row of run.rounds) {
      const bucket = byRound.get(row.round) ?? { accuracy: [], f1: [], loss: [], eps: [] }
      if (row.accuracy !== null) bucket.accuracy.push(row.accuracy)
      if (row.macro_f1 !== null && row.macro_f1 !== undefined) bucket.f1.push(row.macro_f1)
      if (row.loss !== null) bucket.loss.push(row.loss)
      if (row.epsilon_spent !== null) bucket.eps.push(row.epsilon_spent)
      byRound.set(row.round, bucket)
    }
  }
  const mean = (values: number[]) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : null)
  return {
    runCount: matching.length,
    rounds: [...byRound.entries()]
      .sort(([a], [b]) => a - b)
      .map(([round, bucket]) => ({
        round,
        accuracy: mean(bucket.accuracy),
        macro_f1: mean(bucket.f1),
        loss: mean(bucket.loss),
        epsilon_spent: mean(bucket.eps),
      })),
  }
}
