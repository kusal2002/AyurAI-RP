import * as React from "react"
import { CheckCircle2, CircleDashed, RefreshCw, ShieldCheck, XCircle } from "lucide-react"

import { SourceBadge } from "@/components/shared/case"
import { EmptyState, IdChip, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, type StatusSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { useWorkspace } from "@/context/workspace"
import { C4SignInRequired } from "@/features/federation/shared"
import { errorMessage, isAbortError } from "@/lib/api/client"
import { component4Api, type AuditEntry, type ChainStatus } from "@/lib/api/component4"
import { formatDateTime } from "@/lib/labels"

const implemented: StatusSpec = { label: "Implemented", tone: "positive", icon: CheckCircle2 }
const partial: StatusSpec = { label: "Partial", tone: "caution", icon: CircleDashed }
const missing: StatusSpec = { label: "Not implemented", tone: "neutral", icon: XCircle }

/** Verified against the repository source; update when backend capabilities change. */
const capabilities: { area: string; status: StatusSpec; detail: string }[] = [
  {
    area: "Reasoning audit metadata",
    status: partial,
    detail:
      "Component 2 emits one JSON audit line per reasoning request to the server log (logger ayurai.c2.audit). It excludes symptom IDs, risk tier, confidence and free text. Component 4 provides an ingestion endpoint (POST /api/v1/c4/audit/events) but Component 2 does not send its records there yet.",
  },
  {
    area: "Tamper-evident audit log (Component 4)",
    status: implemented,
    detail:
      "Sign-ins (including failures), decisions and verifications are appended to a hash-chained log: each entry stores the SHA-256 of the previous entry, so any edit or deletion is detected by chain verification. Entries hold identifiers only, never free text.",
  },
  {
    area: "Practitioner feedback trail",
    status: partial,
    detail:
      "Feedback is stored append-only in Neo4j and linked to reviewed claims. There is no endpoint to list past feedback and no database uniqueness constraint on feedback IDs.",
  },
  {
    area: "Authentication and role-based access",
    status: partial,
    detail:
      "Component 4 issues JWTs (bcrypt-hashed passwords) and enforces practitioner / supervisor / researcher roles, limiting practitioners to their own clinic. Live mode requires sign-in. The Component 2 and Component 3 APIs still do not check tokens, and Component 2 reviewer roles remain self-declared.",
  },
  {
    area: "Final decision / approval records",
    status: implemented,
    detail:
      "Approve, request-changes and reject are recorded by Component 4 (POST /api/v1/c4/decisions) with the reviewer and clinic taken from the token. A rationale is required for reject and request-changes.",
  },
  {
    area: "Privacy controls (encryption, retention, consent)",
    status: missing,
    detail: "No encryption-at-rest, retention or consent management is implemented in the repository. Use synthetic or de-identified data only.",
  },
  {
    area: "Federated learning with differential privacy",
    status: partial,
    detail:
      "FedAvg and FedProx (μ = 0.1) train across three simulated clinic nodes with Opacus DP at five ε values; the ε spent is tracked per round. Training still uses placeholder data until the Component 1 dataset is connected.",
  },
  {
    area: "Blockchain anchoring (Ethereum Sepolia)",
    status: missing,
    detail: "Planned: periodically write the audit chain's head hash to Sepolia so the log can be verified externally. Not implemented yet.",
  },
  {
    area: "Federated knowledge-graph learning (FAKL)",
    status: missing,
    detail: "Planned: federate practitioner-feedback-driven changes to claim confidence across clinics. Not implemented yet.",
  },
  {
    area: "Client-side data handling",
    status: implemented,
    detail:
      "This interface keeps case data in memory only (no localStorage/sessionStorage), never puts case data in URLs, does not log request or response bodies, and separates demo fixtures from live service data. The Component 4 sign-in token is also kept in memory only.",
  },
]

const chainValid: StatusSpec = { label: "Chain intact", tone: "positive", icon: CheckCircle2 }
const chainBroken: StatusSpec = { label: "Tampering detected", tone: "critical", icon: XCircle }

/** Live audit ledger from Component 4, with hash-chain verification for supervisors. */
function AuditLedger() {
  const { user } = useAuth()
  const { mode } = useWorkspace()
  const [entries, setEntries] = React.useState<AuditEntry[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [chain, setChain] = React.useState<ChainStatus | null>(null)
  const [verifying, setVerifying] = React.useState(false)
  const [tick, setTick] = React.useState(0)

  const enabled = mode === "live" && user !== null && user.role !== "researcher"

  React.useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    component4Api
      .auditLogs(controller.signal)
      .then((data) => {
        setEntries(data)
        setError(null)
      })
      .catch((err) => {
        if (!isAbortError(err)) setError(errorMessage(err))
      })
    return () => controller.abort()
  }, [enabled, tick])

  async function verify() {
    setVerifying(true)
    try {
      setChain(await component4Api.verifyChain())
      setTick((value) => value + 1) // the verification itself is audited, so reload
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setVerifying(false)
    }
  }

  if (mode !== "live" || !user) {
    return <div className="p-5"><C4SignInRequired what="Audit log entries" /></div>
  }
  if (user.role === "researcher") {
    return <div className="p-5"><Notice tone="neutral">Researchers do not have access to the audit log.</Notice></div>
  }

  return (
    <div className="space-y-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        {user.role === "supervisor" ? (
          <Button variant="outline" size="sm" onClick={verify} disabled={verifying}>
            <ShieldCheck /> {verifying ? "Verifying…" : "Verify hash chain"}
          </Button>
        ) : (
          <p className="text-xs text-slate-500">Showing entries for {user.clinic_id}. Chain verification is supervisor-only.</p>
        )}
        <Button variant="ghost" size="sm" onClick={() => setTick((value) => value + 1)}>
          <RefreshCw /> Refresh
        </Button>
        {chain && (
          <span className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
            <StatusBadge spec={chain.valid ? chainValid : chainBroken} />
            {chain.entries_checked} entries checked
            {chain.first_invalid_id !== null && <> · first invalid entry <IdChip>#{chain.first_invalid_id}</IdChip></>}
          </span>
        )}
      </div>

      {error && <Notice tone="critical">{error}</Notice>}

      {entries === null ? (
        <p className="text-sm text-slate-500">Loading audit log…</p>
      ) : entries.length === 0 ? (
        <EmptyState title="No audit entries yet" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-100">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Resource</th>
                <th className="px-4 py-3">Entry hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((entry) => (
                <tr key={entry.id} className={chain?.first_invalid_id === entry.id ? "bg-rose-50" : undefined}>
                  <td className="px-4 py-2.5 text-xs text-slate-400">{entry.id}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{formatDateTime(entry.timestamp)}</td>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-slate-800">{entry.actor}</span>
                    <span className="ml-1.5 text-xs text-slate-400">{entry.role}{entry.clinic_id ? ` · ${entry.clinic_id}` : ""}</span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">{entry.action}</td>
                  <td className="px-4 py-2.5">{entry.resource ? <IdChip>{entry.resource}</IdChip> : "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-slate-500" title={entry.entry_hash}>
                    {entry.entry_hash.slice(0, 12)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function GovernancePage() {
  const { cases } = useWorkspace()
  const activity = cases
    .flatMap((record) => [
      ...(record.c2.status === "success"
        ? [{ at: record.c2.receivedAt, caseRef: record.caseRef, record, event: "Component 2 reasoning response received", ref: record.c2.data.request_id }]
        : []),
      ...(record.c3.status === "success"
        ? [{ at: record.c3.receivedAt, caseRef: record.caseRef, record, event: "Component 3 safety report received", ref: record.c3.data.assessment_id }]
        : []),
      ...record.feedback.map((entry) => ({
        at: entry.submittedAt,
        caseRef: record.caseRef,
        record,
        event:
          entry.outcome.status === "recorded"
            ? "Practitioner feedback recorded by Component 2"
            : entry.outcome.status === "demo_not_sent"
              ? "Demo feedback (not sent)"
              : "Practitioner feedback failed",
        ref: entry.outcome.status === "recorded" ? entry.outcome.response.feedback_id : null,
      })),
    ])
    .sort((a, b) => b.at.localeCompare(a.at))

  return (
    <>
      <PageHeader
        eyebrow="Component 4 · Governance"
        title="Audit & governance"
        description="What governance, audit and privacy capabilities exist today, and what this session has done."
      />
      <Notice tone="caution" className="mb-5" title="No compliance claims">
        This prototype has not been certified or clinically validated, and no regulatory compliance is claimed. The
        status below reflects the code in the repository.
      </Notice>

      <Panel title="Capability status" bodyClassName="p-0" className="mb-6">
        <ul className="divide-y divide-slate-100">
          {capabilities.map((capability) => (
            <li key={capability.area} className="grid grid-cols-1 gap-2 px-5 py-4 md:grid-cols-[260px_140px_minmax(0,1fr)] md:items-start">
              <p className="text-sm font-semibold text-slate-800">{capability.area}</p>
              <div><StatusBadge spec={capability.status} /></div>
              <p className="text-sm leading-6 text-slate-600">{capability.detail}</p>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        title="Audit ledger (Component 4)"
        description="Server-side, append-only and hash-chained. Practitioners see their own clinic; supervisors see everything and can verify the chain."
        bodyClassName="p-0"
        className="mb-6"
      >
        <AuditLedger />
      </Panel>

      <Panel
        title="Session activity"
        description="Local record of actions in this browser tab. This is not an audit log: it is not stored, signed or tamper-evident."
        bodyClassName="p-0"
      >
        {activity.length === 0 ? (
          <EmptyState title="No activity in this session" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-3">Time</th>
                  <th className="px-4 py-3">Case</th>
                  <th className="px-4 py-3">Event</th>
                  <th className="px-4 py-3">Service reference</th>
                  <th className="px-5 py-3">Data</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {activity.map((item, index) => (
                  <tr key={index}>
                    <td className="px-5 py-3 text-xs text-slate-500">{formatDateTime(item.at)}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{item.caseRef}</td>
                    <td className="px-4 py-3 text-slate-700">{item.event}</td>
                    <td className="px-4 py-3">{item.ref ? <IdChip>{item.ref}</IdChip> : "—"}</td>
                    <td className="px-5 py-3"><SourceBadge record={item.record} /></td>
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
