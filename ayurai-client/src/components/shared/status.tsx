import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  CircleHelp,
  CircleSlash,
  CloudOff,
  FlaskConical,
  GitCompareArrows,
  Loader2,
  PauseCircle,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  ThumbsDown,
  ThumbsUp,
  UserCheck,
  XCircle,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Status badges always pair a colour with an icon and a text label so that
 * status is never communicated by colour alone.
 */

export type Tone = "positive" | "caution" | "critical" | "neutral" | "info" | "demo"

const toneStyles: Record<Tone, string> = {
  positive: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  caution: "bg-amber-50 text-amber-800 ring-amber-200",
  critical: "bg-rose-50 text-rose-800 ring-rose-200",
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  info: "bg-sky-50 text-sky-800 ring-sky-200",
  demo: "bg-violet-50 text-violet-800 ring-violet-200",
}

export type StatusSpec = { label: string; tone: Tone; icon: LucideIcon; description?: string }

export function StatusBadge({
  spec,
  className,
  size = "sm",
  title,
}: {
  spec: StatusSpec
  className?: string
  size?: "sm" | "md"
  title?: string
}) {
  const Icon = spec.icon
  return (
    <span
      title={title ?? spec.description}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full font-semibold ring-1 ring-inset",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        toneStyles[spec.tone],
        className,
      )}
    >
      <Icon aria-hidden className={size === "sm" ? "size-3.5 shrink-0" : "size-4 shrink-0"} />
      <span className="truncate">{spec.label}</span>
    </span>
  )
}

export const sufficiencySpecs: Record<string, StatusSpec> = {
  sufficient_for_review: {
    label: "Sufficient for review",
    tone: "positive",
    icon: CheckCircle2,
    description: "Meets the provisional sufficiency policy. Practitioner review is still required.",
  },
  insufficient_evidence: {
    label: "Insufficient evidence",
    tone: "caution",
    icon: CircleDashed,
    description: "Not enough independent, provenance-complete evidence.",
  },
  conflicting_evidence: {
    label: "Conflicting evidence",
    tone: "critical",
    icon: GitCompareArrows,
    description: "Contradicting evidence or a disputed claim was found. Conflicts are never outvoted.",
  },
  unverified_claims: {
    label: "Unverified claims",
    tone: "caution",
    icon: CircleHelp,
    description: "The path relies on claims that are not literature-supported or practitioner-verified.",
  },
  out_of_scope: {
    label: "Out of scope",
    tone: "neutral",
    icon: Ban,
    description: "No supplied symptom matched a stored concept.",
  },
}

export function sufficiencySpec(status: string): StatusSpec {
  return sufficiencySpecs[status] ?? { label: status, tone: "neutral", icon: CircleHelp }
}

export const verificationSpecs: Record<string, StatusSpec> = {
  practitioner_verified: { label: "Practitioner verified", tone: "positive", icon: UserCheck },
  literature_supported: { label: "Literature supported", tone: "info", icon: CheckCircle2 },
  unverified: { label: "Unverified", tone: "caution", icon: CircleHelp },
  disputed: { label: "Disputed", tone: "critical", icon: AlertTriangle },
}

export function verificationSpec(status: string): StatusSpec {
  return verificationSpecs[status] ?? { label: status, tone: "neutral", icon: CircleHelp }
}

export const relationshipSpecs: Record<"SUPPORTS" | "CONTRADICTS", StatusSpec> = {
  SUPPORTS: { label: "Supports", tone: "positive", icon: ThumbsUp },
  CONTRADICTS: { label: "Contradicts", tone: "critical", icon: ThumbsDown },
}

export const dispositionSpecs: Record<string, StatusSpec> = {
  forward_for_safety_assessment: {
    label: "Forwarded to safety check",
    tone: "info",
    icon: ShieldCheck,
    description: "Component 2 forwards this candidate to Component 3. This is not an approval.",
  },
  withheld_pending_review: {
    label: "Withheld pending review",
    tone: "neutral",
    icon: PauseCircle,
    description: "Not forwarded automatically; practitioner review is needed first.",
  },
}

export function dispositionSpec(value: string): StatusSpec {
  return dispositionSpecs[value] ?? { label: value, tone: "neutral", icon: CircleHelp }
}

export const decisionSpecs: Record<string, StatusSpec> = {
  recommend_for_review: {
    label: "Recommend for review",
    tone: "positive",
    icon: CheckCircle2,
    description: "Evidence policy met and no upstream risk rule triggered. A practitioner must still review.",
  },
  caution: {
    label: "Caution",
    tone: "caution",
    icon: AlertTriangle,
    description: "Shown with caution: conflicting or unverified evidence, or an upstream risk rule (high tier, missing or low C1 confidence).",
  },
  abstain: {
    label: "Abstain",
    tone: "critical",
    icon: CircleSlash,
    description: "Component 2 declined to recommend because its evidence policy was not met.",
  },
}

export function decisionSpec(decision: string | undefined): StatusSpec {
  return (decision && decisionSpecs[decision]) || { label: decision ?? "Unknown decision", tone: "neutral", icon: CircleHelp }
}

/** Provisional research records: never shown without this label. */
export const provisionalSpec: StatusSpec = {
  label: "Unverified — practitioner review pending",
  tone: "caution",
  icon: CircleDashed,
  description:
    "AI-assisted draft quoted from the cited source. Not approved knowledge, not clinical evidence of efficacy, and never sufficient for a recommendation.",
}

export const evidenceRoleSpecs: Record<string, StatusSpec> = {
  claim_support: { label: "Primary text", tone: "neutral", icon: CircleDashed, description: "Quoted from the original-language source." },
  translation_support: { label: "Translation", tone: "neutral", icon: CircleDashed, description: "Quoted from a published translation of the source." },
  modern_reference: {
    label: "Modern reference (qualifies)",
    tone: "info",
    icon: CircleHelp,
    description: "Modern literature that qualifies the traditional claim. It is kept separate and does not support it.",
  },
}

export const abstentionSpec: StatusSpec = {
  label: "Abstained — no recommendation",
  tone: "caution",
  icon: CircleSlash,
  description: "Component 2 declined to recommend because its evidence policy was not met.",
}

export const safetySpecs: Record<string, StatusSpec> = {
  "Low Risk": {
    label: "Low Risk",
    tone: "positive",
    icon: ShieldCheck,
    description: "As classified by Component 3. Means no configured rule matched; it is not proof of safety.",
  },
  Caution: { label: "Caution", tone: "caution", icon: ShieldAlert },
  "High Risk": { label: "High Risk", tone: "critical", icon: ShieldX },
}

export function safetySpec(tier: string): StatusSpec {
  return safetySpecs[tier] ?? { label: tier, tone: "neutral", icon: CircleHelp }
}

export const serviceStateSpecs = {
  loading: { label: "Checking…", tone: "neutral", icon: Loader2 },
  online: { label: "Online", tone: "positive", icon: CheckCircle2 },
  degraded: { label: "Degraded", tone: "caution", icon: AlertTriangle },
  offline: { label: "Unavailable", tone: "critical", icon: CloudOff },
  missing: { label: "Not implemented", tone: "neutral", icon: XCircle },
  demo: { label: "Demo data", tone: "demo", icon: FlaskConical },
} satisfies Record<string, StatusSpec>

export const demoSpec: StatusSpec = serviceStateSpecs.demo
