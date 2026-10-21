import { Link } from "react-router"
import { ChevronRight, ClipboardCheck, Leaf, ScrollText, ShieldCheck, Stethoscope } from "lucide-react"

const stages = [
  {
    code: "C1",
    title: "Screening",
    detail: "Anemia risk tier, confidence and symptom IDs",
    to: "/screening/new",
    icon: Stethoscope,
  },
  {
    code: "C2",
    title: "Ayurvedic reasoning",
    detail: "Knowledge-graph interpretation, evidence, candidates",
    to: "/analysis",
    icon: Leaf,
  },
  {
    code: "C3",
    title: "Safety gate",
    detail: "Herb–drug interactions and contraindications",
    to: "/safety",
    icon: ShieldCheck,
  },
  {
    code: "Review",
    title: "Practitioner review",
    detail: "Human decision; nothing is auto-approved",
    to: "/review",
    icon: ClipboardCheck,
  },
]

/** How the four components relate. Component 4 is cross-cutting, not a stage. */
export function WorkflowStrip() {
  return (
    <div>
      <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage, index) => (
          <li key={stage.code} className="relative">
            <Link
              to={stage.to}
              className="flex h-full items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 transition hover:border-emerald-300 hover:bg-emerald-50/40"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                <stage.icon aria-hidden className="size-4.5" />
              </span>
              <span className="min-w-0">
                <span className="block text-[10px] font-bold tracking-wide text-emerald-700">{stage.code}</span>
                <span className="block text-sm font-semibold text-slate-800">{stage.title}</span>
                <span className="mt-0.5 block text-xs leading-5 text-slate-500">{stage.detail}</span>
              </span>
            </Link>
            {index < stages.length - 1 && (
              <ChevronRight
                aria-hidden
                className="absolute top-1/2 -right-2.5 z-10 hidden size-4 -translate-y-1/2 rounded-full bg-[#f7f9f8] text-slate-400 xl:block"
              />
            )}
          </li>
        ))}
      </ol>
      <Link
        to="/governance"
        className="mt-2 flex items-center gap-3 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 px-3 py-2.5 text-xs text-slate-600 transition hover:border-emerald-300"
      >
        <ScrollText aria-hidden className="size-4 shrink-0 text-slate-500" />
        <span>
          <strong className="font-semibold text-slate-800">C4 · Governance &amp; privacy</strong> spans every
          stage (sign-in, access control, decisions and a tamper-evident audit log).
        </span>
      </Link>
    </div>
  )
}
