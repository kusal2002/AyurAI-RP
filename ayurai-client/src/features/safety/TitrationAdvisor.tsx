import * as React from "react"
import {
  Activity,
  Calendar,
  CheckSquare,
  Clock,
  Eye,
  Pill,
  ShieldCheck,
  Square,
} from "lucide-react"

import type { SurveillanceGuidance, TitrationGuidance } from "@/lib/api/types"

interface TitrationAdvisorProps {
  titration: TitrationGuidance | null
  surveillance: SurveillanceGuidance | null
}

export function TitrationAdvisor({ titration, surveillance }: TitrationAdvisorProps) {
  const [completedLabs, setCompletedLabs] = React.useState<Record<string, boolean>>({})

  function toggleLab(item: string) {
    setCompletedLabs((prev) => ({ ...prev, [item]: !prev[item] }))
  }

  const hasTitration = Boolean(
    titration?.recommended_dose_adjustment || titration?.separation_window || titration?.duration_limit
  )
  const hasSurveillance = Boolean(
    (surveillance?.lab_monitoring && surveillance.lab_monitoring.length > 0) ||
      (surveillance?.clinical_signs_to_watch && surveillance.clinical_signs_to_watch.length > 0)
  )

  if (!hasTitration && !hasSurveillance) {
    return (
      <div className="rounded-lg border border-slate-100 bg-white p-4 text-center">
        <ShieldCheck className="mx-auto size-5 text-emerald-600 mb-1" />
        <p className="text-xs font-semibold text-slate-700">No Titration Adjustment Required</p>
        <p className="text-[11px] text-slate-500">
          Standard therapeutic dosing schedule approved without mandatory temporal separation.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
      {/* 1. Visual 4-Hour Separation Window */}
      {titration?.separation_window && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <h5 className="text-xs font-bold text-indigo-950 flex items-center gap-1.5">
              <Clock className="size-3.5 text-indigo-700" /> Dosing Time Separation Window
            </h5>
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-800">
              {titration.separation_window}
            </span>
          </div>

          <p className="text-xs text-indigo-900 leading-relaxed">
            Administer co-prescribed pharmaceutical drugs and Ayurvedic formulations with at least a{" "}
            <strong>4-hour separation gap</strong> to prevent acute gastrointestinal binding and competitive CYP450 peak concentrations.
          </p>

          {/* Timeline Visual */}
          <div className="pt-2">
            <div className="flex items-center justify-between text-[11px] font-semibold text-slate-700">
              <span className="flex items-center gap-1 text-slate-900">
                <Pill className="size-3 text-indigo-600" /> 08:00 AM (Allopathic Co-Rx)
              </span>
              <span className="text-indigo-700 text-[10px] bg-indigo-100 px-1.5 py-0.5 rounded">
                ≥ 4h Metabolic Buffer
              </span>
              <span className="flex items-center gap-1 text-emerald-900">
                <Activity className="size-3 text-emerald-600" /> 12:00 PM (Ayurvedic Herb)
              </span>
            </div>
            <div className="relative mt-2 h-2.5 w-full rounded-full bg-slate-200 overflow-hidden">
              <div className="absolute left-0 top-0 h-full w-1/4 bg-indigo-500 rounded-l-full" />
              <div className="absolute left-1/4 top-0 h-full w-2/4 bg-indigo-200" />
              <div className="absolute right-0 top-0 h-full w-1/4 bg-emerald-500 rounded-r-full" />
            </div>
          </div>
        </div>
      )}

      {/* 2. Step-Down Titration Schedule */}
      {titration?.recommended_dose_adjustment && (
        <div className="space-y-2">
          <h5 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <Calendar className="size-3.5 text-amber-600" /> Clinical Dose Titration Schedule
          </h5>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-xs">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 space-y-1">
              <div className="font-bold text-slate-800 flex items-center justify-between">
                <span>Phase 1: Initiation</span>
                <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-semibold">50% Dose</span>
              </div>
              <p className="text-[11px] text-slate-600">
                {titration.recommended_dose_adjustment}
              </p>
            </div>

            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 space-y-1">
              <div className="font-bold text-slate-800 flex items-center justify-between">
                <span>Phase 2: Review</span>
                <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-semibold">Day 7–10</span>
              </div>
              <p className="text-[11px] text-slate-600">
                Review renal/hepatic labs & clinical tolerance prior to therapeutic escalation.
              </p>
            </div>

            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 space-y-1">
              <div className="font-bold text-slate-800 flex items-center justify-between">
                <span>Phase 3: Target Dose</span>
                <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded font-semibold">100% Dose</span>
              </div>
              <p className="text-[11px] text-slate-600">
                Full therapeutic dose with duration limit: <strong>{titration.duration_limit || "4–6 weeks"}</strong>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Laboratory Surveillance Checklist & Signs to Watch */}
      {hasSurveillance && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
          {/* Lab Checklist */}
          {surveillance?.lab_monitoring && surveillance.lab_monitoring.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3.5 space-y-2">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <Activity className="size-3.5 text-blue-600" /> Mandatory Laboratory Surveillance
              </h5>
              <div className="space-y-1.5">
                {surveillance.lab_monitoring.map((lab, i) => {
                  const isChecked = Boolean(completedLabs[lab])
                  return (
                    <button
                      type="button"
                      key={i}
                      onClick={() => toggleLab(lab)}
                      className="w-full text-left flex items-start gap-2 p-1.5 rounded hover:bg-slate-100 transition-colors text-xs text-slate-800"
                    >
                      {isChecked ? (
                        <CheckSquare className="size-3.5 text-emerald-600 mt-0.5 shrink-0" />
                      ) : (
                        <Square className="size-3.5 text-slate-400 mt-0.5 shrink-0" />
                      )}
                      <span className={isChecked ? "line-through text-slate-400" : ""}>{lab}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Clinical Signs to Watch */}
          {surveillance?.clinical_signs_to_watch && surveillance.clinical_signs_to_watch.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50/30 p-3.5 space-y-2">
              <h5 className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                <Eye className="size-3.5 text-amber-700" /> Clinical Signs for Surveillance
              </h5>
              <ul className="space-y-1 text-xs text-amber-950">
                {surveillance.clinical_signs_to_watch.map((sign, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-amber-600 font-bold">•</span>
                    <span>{sign}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
