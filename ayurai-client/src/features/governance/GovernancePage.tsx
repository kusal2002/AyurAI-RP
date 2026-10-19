import { CheckCircle2, CircleDashed, XCircle } from "lucide-react"

import { SourceBadge } from "@/components/shared/case"
import { EmptyState, IdChip, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, type StatusSpec } from "@/components/shared/status"
import { useWorkspace } from "@/context/workspace"
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
      "Component 2 emits one JSON audit line per reasoning request to the server log (logger ayurai.c2.audit). It excludes symptom IDs, risk tier, confidence and free text. There is no storage, retention policy or read API, so audit records cannot be shown here.",
  },
  {
    area: "Practitioner feedback trail",
    status: partial,
    detail:
      "Feedback is stored append-only in Neo4j and linked to reviewed claims. There is no endpoint to list past feedback and no database uniqueness constraint on feedback IDs.",
  },
  {
    area: "Authentication and role-based access",
    status: missing,
    detail:
      "Neither the Component 2 nor the Component 3 API authenticates requests. Reviewer roles are self-declared. This interface does not implement sign-in and does not restrict screens by role.",
  },
  {
    area: "Final decision / approval records",
    status: missing,
    detail: "No approval, rejection or change-request endpoint exists. The review screen keeps these actions disabled.",
  },
  {
    area: "Privacy controls (encryption, retention, consent)",
    status: missing,
    detail: "No encryption-at-rest, retention or consent management is implemented in the repository. Use synthetic or de-identified data only.",
  },
  {
    area: "Federated learning / blockchain governance (Component 4 proposal)",
    status: missing,
    detail: "Described in project documentation, but no Component 4 service code is present in this repository.",
  },
  {
    area: "Client-side data handling",
    status: implemented,
    detail:
      "This interface keeps case data in memory only (no localStorage/sessionStorage), never puts case data in URLs, does not log request or response bodies, and separates demo fixtures from live service data.",
  },
]

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
