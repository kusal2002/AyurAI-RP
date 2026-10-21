import { createApiClient } from "@/lib/api/client"
import type { HealthResponse } from "@/lib/api/types"
import { env } from "@/lib/env"

/**
 * Component 4 FastAPI governance service (component4/api/main.py).
 * TypeScript mirrors of component4/api/schemas.py.
 */

export type C4Role = "practitioner" | "supervisor" | "researcher"

export type C4User = { username: string; role: C4Role; clinic_id: string | null }

export type LoginResponse = { access_token: string; token_type: string; user: C4User }

export type DecisionValue = "approve" | "request_changes" | "reject"

export type DecisionCreate = {
  case_ref: string
  c2_request_id?: string | null
  c3_assessment_id?: string | null
  decision: DecisionValue
  rationale: string
}

export type Decision = DecisionCreate & {
  id: number
  reviewer: string
  clinic_id: string | null
  created_at: string
}

export type AuditEntry = {
  id: number
  timestamp: string
  actor: string
  role: string
  clinic_id: string | null
  action: string
  resource: string | null
  details: Record<string, unknown>
  prev_hash: string
  entry_hash: string
}

export type ChainStatus = {
  valid: boolean
  entries_checked: number
  first_invalid_id: number | null
  head_hash: string | null
}

/** One audit-chain head hash written to the AuditAnchor contract on Ethereum Sepolia. */
export type Anchor = {
  id: number
  created_at: string
  head_entry_id: number
  head_hash: string
  onchain_id: number
  tx_hash: string
  block_number: number
  contract_address: string
  anchored_by: string
  explorer_url: string
}

export type AnchorVerification = {
  local_chain_valid: boolean
  anchors_checked: number
  all_anchors_match: boolean
  checks: {
    anchor_id: number
    onchain_id: number
    head_entry_id: number
    onchain_hash: string
    current_db_hash: string | null
    matches: boolean
  }[]
}

export type FederationConfig = {
  num_clinics: number
  num_rounds: number
  local_epochs: number
  proximal_mu: number
  delta: number
  max_grad_norm: number
  epsilons: number[]
  learning_rate: number
  /** true when training uses the real CP-AnemiC features, false for placeholder data */
  real_data: boolean
  hb_thresholds: { high_risk_below: number; low_risk_from: number }
  clinics: { clinic_id: number; name: string; low: number; moderate: number; high: number }[]
}

export type RoundMetrics = {
  round: number
  loss: number | null
  accuracy: number | null
  macro_f1: number | null
  epsilon_spent: number | null
}

/** Read-only readiness check of Component 2's knowledge graph for FAKL (counts only). */
export type FaklStatus = {
  configured: boolean
  connected: boolean
  error: string | null
  counts: {
    claims: number
    claims_with_confidence: number
    feedback: number
    feedback_with_clinic: number
    feedback_links: number
  } | null
}

/** FAKL prototype results on SYNTHETIC data (CSV values arrive as strings). */
export type FaklPrototype = {
  summary: {
    setting: string
    epsilon: string
    min_votes: string
    mean_abs_diff: string
    std: string
    values_shared_per_clinic: string
    data: string
  }[]
  claims: {
    claim_id: string
    statement: string
    prior: string
    centralised: string
    federated: string
    federated_suppression: string
    federated_dp_eps1: string
    data: string
  }[]
}

/** One row of results/baselines.csv (CSV values arrive as strings). */
export type BaselineRow = {
  method: "majority_class" | "centralised_no_dp" | "fedavg_no_dp" | "fedprox_no_dp"
  accuracy_mean: string
  accuracy_std: string
  macro_f1_mean: string
  runs: string
  data_source: string
}

export type FederationRun = {
  strategy: "fedavg" | "fedprox"
  epsilon: number
  run: number
  rounds: RoundMetrics[]
}

/** One row of results/summary.csv (CSV values arrive as strings). */
export type SummaryRow = {
  strategy: "fedavg" | "fedprox"
  target_epsilon: string
  runs: string
  rounds: string
  final_accuracy_mean: string
  final_accuracy_std: string
  final_macro_f1_mean?: string
  final_macro_f1_std?: string
  epsilon_spent_max: string
  data_source: string
}

// The JWT used for requests. The AuthProvider sets it after sign-in and when it
// restores a sign-in from this tab's sessionStorage (never localStorage).
let authToken: string | null = null
export function setAuthToken(token: string | null) {
  authToken = token
}

export const component4Client = createApiClient(
  "Component 4 governance service",
  env.c4BaseUrl,
  () => authToken,
)

export const component4Api = {
  health: (signal?: AbortSignal) => component4Client.get<HealthResponse>("/health", { signal }),

  login: (username: string, password: string) =>
    component4Client.post<LoginResponse>("/api/v1/c4/auth/login", { username, password }),

  /** POST /api/v1/c4/decisions — practitioner or supervisor only. */
  createDecision: (decision: DecisionCreate) =>
    component4Client.post<Decision>("/api/v1/c4/decisions", decision),
  listDecisions: (caseRef?: string, signal?: AbortSignal) =>
    component4Client.get<Decision[]>(
      `/api/v1/c4/decisions${caseRef ? `?case_ref=${encodeURIComponent(caseRef)}` : ""}`,
      { signal },
    ),

  auditLogs: (signal?: AbortSignal) =>
    component4Client.get<AuditEntry[]>("/api/v1/c4/audit/logs?limit=200", { signal }),
  /** Supervisor only: recompute every hash in the audit chain. */
  verifyChain: () => component4Client.get<ChainStatus>("/api/v1/c4/audit/verify"),

  /** Supervisor only: write the audit chain's head hash to Sepolia (waits for the block). */
  anchorToChain: () =>
    component4Client.post<Anchor>("/api/v1/c4/audit/anchor", {}, { timeoutMs: 120_000 }),
  anchors: (signal?: AbortSignal) =>
    component4Client.get<Anchor[]>("/api/v1/c4/audit/anchors", { signal }),
  /** Supervisor only: compare every on-chain anchor with the database as it is now. */
  verifyAgainstChain: () =>
    component4Client.get<AnchorVerification>("/api/v1/c4/audit/anchors/verify", { timeoutMs: 60_000 }),

  federationConfig: (signal?: AbortSignal) =>
    component4Client.get<FederationConfig>("/api/v1/c4/federation/config", { signal }),
  federationRuns: (signal?: AbortSignal) =>
    component4Client.get<FederationRun[]>("/api/v1/c4/federation/runs", { signal }),
  federationSummary: (signal?: AbortSignal) =>
    component4Client.get<SummaryRow[]>("/api/v1/c4/federation/summary", { signal }),
  faklPrototype: (signal?: AbortSignal) =>
    component4Client.get<FaklPrototype>("/api/v1/c4/fakl/prototype", { signal }),
  faklStatus: (signal?: AbortSignal) =>
    component4Client.get<FaklStatus>("/api/v1/c4/fakl/status", { signal, timeoutMs: 30_000 }),
  federationBaselines: (signal?: AbortSignal) =>
    component4Client.get<BaselineRow[]>("/api/v1/c4/federation/baselines", { signal }),
}
