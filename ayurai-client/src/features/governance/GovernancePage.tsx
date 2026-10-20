import * as React from "react"
import { CheckCircle2, CircleDashed, ExternalLink, Link2, RefreshCw, ShieldCheck, XCircle } from "lucide-react"

import { SourceBadge } from "@/components/shared/case"
import { EmptyState, IdChip, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, type StatusSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { useWorkspace } from "@/context/workspace"
import { C4SignInRequired } from "@/features/federation/shared"
import { errorMessage, isAbortError } from "@/lib/api/client"
import {
  component4Api,
  type Anchor,
  type AnchorVerification,
  type AuditEntry,
  type ChainStatus,
} from "@/lib/api/component4"
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
      "Sign-ins (including failures), decisions, verifications and anchoring are appended to a hash-chained log: each entry stores the SHA-256 of the previous entry, so editing or removing any entry breaks the chain. Limitation: deleting the newest entries leaves a shorter chain that still verifies locally; this is only detected for entries covered by a blockchain anchor. Component 4's own entries hold identifiers, not free text (failed sign-ins record the username typed; Component 2 / 3 event details are stored as sent).",
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
      "FedAvg and FedProx (μ = 0.1) train across three simulated clinic nodes with Opacus DP at five ε values; the ε spent stays within target in every setting. Training uses Component 1's CP-AnemiC dataset (251 patients, lab-measured Hb) through simple colour features of the conjunctiva, compared against centralised and no-DP baselines. Partial because it is not yet the image model itself, the dataset is small, and the clinics are simulated.",
  },
  {
    area: "Blockchain anchoring (Ethereum Sepolia)",
    status: implemented,
    detail:
      "A supervisor can write the audit chain's newest hash to the AuditAnchor contract on the Sepolia test network; only the 32-byte hash goes on-chain. Verification compares every anchored hash with the database, which also detects a full rewrite of the log (with recomputed hashes) that the local hash check alone would miss, for all entries up to the latest anchor. Entries added after the last anchor are protected only by the local hash chain. Anchoring is manual (not scheduled) and uses a testnet, not a production network.",
  },
  {
    area: "Federated knowledge-graph learning (FAKL)",
    status: partial,
    detail:
      "Prototype: the FAKL algorithm (per-clinic agree / disagree counts, small-count suppression, optional DP noise, federated confidence update) is implemented and tested on synthetic claims in Component 2's schema, and matches centralised pooling exactly without privacy. Not yet connected to Component 2's real graph, which has no claims or clinic-tagged feedback yet (live check on the Knowledge federation page). Full implementation scheduled Dec 2026 – Feb 2027.",
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
const onchainMatch: StatusSpec = { label: "Matches blockchain", tone: "positive", icon: CheckCircle2 }
const onchainMismatch: StatusSpec = { label: "Differs from blockchain", tone: "critical", icon: XCircle }

const shortHash = (value: string | null) => (value ? `${value.slice(0, 10)}…` : "deleted")

/**
 * Supervisor-only: anchor the audit chain's head hash on Ethereum Sepolia and
 * check every anchor against the database as it is now (proposal FR9).
 */
function BlockchainPanel() {
  const { user } = useAuth()
  const { mode } = useWorkspace()
  const [anchors, setAnchors] = React.useState<Anchor[] | null>(null)
  const [verification, setVerification] = React.useState<AnchorVerification | null>(null)
  const [busy, setBusy] = React.useState<"anchor" | "verify" | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [tick, setTick] = React.useState(0)

  const enabled = mode === "live" && user?.role === "supervisor"

  React.useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    component4Api
      .anchors(controller.signal)
      .then((data) => {
        setAnchors(data)
        setError(null)
      })
      .catch((err) => {
        if (!isAbortError(err)) setError(errorMessage(err))
      })
    return () => controller.abort()
  }, [enabled, tick])

  async function run(kind: "anchor" | "verify") {
    setBusy(kind)
    setError(null)
    try {
      if (kind === "anchor") await component4Api.anchorToChain()
      else setVerification(await component4Api.verifyAgainstChain())
      setTick((value) => value + 1)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  if (mode !== "live" || !user) {
    return <div className="p-5"><C4SignInRequired what="Blockchain anchors" /></div>
  }
  if (user.role !== "supervisor") {
    return <div className="p-5"><Notice tone="neutral">Blockchain anchoring and on-chain verification are supervisor-only.</Notice></div>
  }

  return (
    <div className="space-y-4 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" className="bg-emerald-700 hover:bg-emerald-800" onClick={() => run("anchor")} disabled={busy !== null}>
          <Link2 /> {busy === "anchor" ? "Anchoring… waiting for the block" : "Anchor to Sepolia"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => run("verify")} disabled={busy !== null || !anchors?.length}>
          <ShieldCheck /> {busy === "verify" ? "Verifying…" : "Verify against blockchain"}
        </Button>
      </div>

      {error && <Notice tone="critical">{error}</Notice>}

      {verification && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <StatusBadge spec={verification.local_chain_valid ? chainValid : chainBroken} />
          <StatusBadge spec={verification.all_anchors_match ? onchainMatch : onchainMismatch} />
          {verification.anchors_checked} anchor(s) compared with the database as it is now
          {verification.local_chain_valid && !verification.all_anchors_match && (
            <span className="font-semibold text-rose-700">
              — the log was rewritten with recomputed hashes; only the blockchain check can detect this.
            </span>
          )}
        </div>
      )}

      {anchors === null ? (
        <p className="text-sm text-slate-500">Loading anchors…</p>
      ) : anchors.length === 0 ? (
        <EmptyState title="No anchors yet" description="Anchor the audit chain to record its current state on Sepolia." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-100">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                <th className="px-4 py-3">On-chain #</th>
                <th className="px-4 py-3">Covers entries</th>
                <th className="px-4 py-3">Anchored hash</th>
                <th className="px-4 py-3">Block</th>
                <th className="px-4 py-3">By / when</th>
                <th className="px-4 py-3">Check</th>
                <th className="px-4 py-3">Transaction</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {anchors.map((anchor) => {
                const check = verification?.checks.find((c) => c.anchor_id === anchor.id)
                return (
                  <tr key={anchor.id}>
                    <td className="px-4 py-2.5 font-medium text-slate-800">#{anchor.onchain_id}</td>
                    <td className="px-4 py-2.5 text-slate-600">1 – {anchor.head_entry_id}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-slate-500" title={anchor.head_hash}>
                      {shortHash(anchor.head_hash)}
                      {check && !check.matches && (
                        <span className="block text-rose-700">database now: {shortHash(check.current_db_hash)}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums text-slate-600">{anchor.block_number}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">
                      {anchor.anchored_by}
                      <span className="block">{formatDateTime(anchor.created_at)}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      {check ? <StatusBadge spec={check.matches ? onchainMatch : onchainMismatch} /> : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <a
                        href={anchor.explorer_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:underline"
                      >
                        Etherscan <ExternalLink aria-hidden className="size-3" />
                      </a>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

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
        title="Blockchain anchoring (Ethereum Sepolia)"
        description="The newest audit hash is written to a public smart contract. Because each hash includes the previous one, an anchor fixes the whole log up to that entry; nobody can rewrite it afterwards without the mismatch showing here."
        bodyClassName="p-0"
        className="mb-6"
      >
        <BlockchainPanel />
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
