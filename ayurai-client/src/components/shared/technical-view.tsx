import { Code2 } from "lucide-react"

import { useAccess } from "@/lib/access"
import { cn } from "@/lib/utils"

/**
 * "Technical details" switch for supervisors and researchers. Renders nothing
 * for practitioners, who always see the clean clinical view.
 */
export function TechnicalViewSwitch({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  const { canUseTechnicalView } = useAccess()
  if (!canUseTechnicalView) return null
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={cn(
        "inline-flex h-8 items-center gap-2 rounded-lg border px-3 text-xs font-semibold transition",
        on
          ? "border-slate-800 bg-slate-800 text-white hover:bg-slate-700"
          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
      )}
    >
      <Code2 aria-hidden className="size-3.5" />
      Technical details
      <span
        aria-hidden
        className={cn(
          "relative h-4 w-7 rounded-full transition",
          on ? "bg-emerald-400" : "bg-slate-200",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 size-3 rounded-full bg-white shadow transition-all",
            on ? "left-3.5" : "left-0.5",
          )}
        />
      </span>
    </button>
  )
}
