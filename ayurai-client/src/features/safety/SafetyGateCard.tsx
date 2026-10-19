import * as React from "react"
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Pill,
  ShieldAlert,
  ShieldCheck,
  Siren,
  XCircle,
} from "lucide-react"

import { IdChip } from "@/components/shared/page"
import { StatusBadge, safetySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import type { EvaluatedCandidateSafety } from "@/lib/api/types"
import { formatScore } from "@/lib/labels"
import { TitrationAdvisor } from "./TitrationAdvisor"

export type SignOffAction = "accept" | "modify" | "reject"

interface SafetyGateCardProps {
  evaluation: EvaluatedCandidateSafety
  onSignOff?: (candidateId: string, action: SignOffAction, notes?: string) => void
}

export function SafetyGateCard({ evaluation, onSignOff }: SafetyGateCardProps) {
  const [activeTab, setActiveTab] = React.useState<"interactions" | "directives" | "contraindications">("interactions")
  const [signedOffAction, setSignedOffAction] = React.useState<SignOffAction | null>(null)

  function handleSignOff(action: SignOffAction) {
    setSignedOffAction(action)
    if (onSignOff) {
      onSignOff(evaluation.candidate_id, action)
    }
  }

  const isHighRisk = evaluation.safety_tier === "High Risk"
  const isCaution = evaluation.safety_tier === "Caution"

  return (
    <article
      className={`rounded-xl border transition-all duration-200 ${
        isHighRisk
          ? "border-rose-200 bg-rose-50/20 shadow-xs"
          : isCaution
          ? "border-amber-200 bg-amber-50/20 shadow-xs"
          : "border-emerald-200 bg-emerald-50/20 shadow-xs"
      }`}
    >
      {/* Top Header Banner */}
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200/80 bg-white/80 p-5 rounded-t-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900">{evaluation.candidate_name}</h3>
            <IdChip>{evaluation.candidate_id}</IdChip>
          </div>
          <p className="text-xs text-slate-500">
            Safety Gate Assessment · Confidence: <span className="font-semibold">{formatScore(evaluation.confidence)}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge size="md" spec={safetySpec(evaluation.safety_tier)} />
          {evaluation.escalate_to_practitioner && (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-1 text-xs font-semibold text-rose-800">
              <Siren className="size-3.5 animate-pulse text-rose-600" /> Practitioner Escalation
            </span>
          )}
        </div>
      </header>

      {/* Main Body */}
      <div className="p-5 space-y-4">
        {/* Summary Warning Callout */}
        <div
          className={`flex items-start gap-3 rounded-lg border p-3.5 text-xs ${
            isHighRisk
              ? "border-rose-300 bg-rose-50 text-rose-900"
              : isCaution
              ? "border-amber-300 bg-amber-50 text-amber-900"
              : "border-emerald-300 bg-emerald-50 text-emerald-900"
          }`}
        >
          {isHighRisk ? (
            <ShieldAlert className="mt-0.5 size-4.5 shrink-0 text-rose-600" />
          ) : isCaution ? (
            <AlertTriangle className="mt-0.5 size-4.5 shrink-0 text-amber-600" />
          ) : (
            <ShieldCheck className="mt-0.5 size-4.5 shrink-0 text-emerald-600" />
          )}
          <div className="space-y-1">
            <p className="font-semibold">{evaluation.summary_warning}</p>
            <p className="text-[11px] opacity-85">
              Evaluated by Component 3 Dynamic Context Fusion & Knowledge Graph Safety Gate.
            </p>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex gap-2 border-b border-slate-200">
          <button
            type="button"
            onClick={() => setActiveTab("interactions")}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "interactions"
                ? "border-emerald-700 text-emerald-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Herb-Drug Interactions ({evaluation.interaction_findings.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("directives")}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "directives"
                ? "border-emerald-700 text-emerald-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Clinical Titration & Directives
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("contraindications")}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "contraindications"
                ? "border-emerald-700 text-emerald-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Contraindications & Modifiers ({evaluation.contraindications_triggered.length + evaluation.patient_risk_modifiers.length})
          </button>
        </div>

        {/* Tab 1: Interaction Findings */}
        {activeTab === "interactions" && (
          <div className="space-y-3">
            {evaluation.interaction_findings.length === 0 ? (
              <div className="rounded-lg border border-slate-100 bg-white p-4 text-center">
                <CheckCircle2 className="mx-auto size-5 text-emerald-600 mb-1" />
                <p className="text-xs font-medium text-slate-700">No interaction rule or biological pathway match</p>
                <p className="text-[11px] text-slate-500">
                  None of the patient's concurrent medications trigger an established or predicted CYP450 / transporter interaction with {evaluation.candidate_name}.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Herb Constituent</th>
                      <th className="py-2.5 px-3">Target Drug</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3">Biochemical Mechanism</th>
                      <th className="py-2.5 px-3">Evidence Grade</th>
                      <th className="py-2.5 px-3">PubMed / Literature</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {evaluation.interaction_findings.map((f, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/70">
                        <td className="py-2.5 px-3 font-semibold text-slate-900">{f.herb_or_constituent}</td>
                        <td className="py-2.5 px-3 font-medium text-indigo-900 flex items-center gap-1.5">
                          <Pill className="size-3 text-indigo-500" /> {f.target_drug}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">{f.interaction_type}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                              f.severity.toLowerCase() === "high" || f.severity.toLowerCase() === "severe"
                                ? "bg-rose-100 text-rose-800"
                                : f.severity.toLowerCase() === "moderate"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-emerald-100 text-emerald-800"
                            }`}
                          >
                            {f.severity}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-700 max-w-[280px]">{f.mechanism}</td>
                        <td className="py-2.5 px-3">
                          <span className="font-semibold text-slate-800">{f.evidence_strength}</span>
                          <span className="block text-[10px] text-slate-400">Score {formatScore(f.prediction_confidence)}</span>
                        </td>
                        <td className="py-2.5 px-3">
                          {f.source_refs.length === 0 ? (
                            <span className="text-slate-400">—</span>
                          ) : (
                            f.source_refs.map((src, sIdx) => {
                              const pmidClean = src.pmid_or_ref?.replace(/\D/g, "")
                              return (
                                <div key={sIdx} className="mb-1 last:mb-0">
                                  {pmidClean ? (
                                    <a
                                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmidClean}/`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 text-emerald-700 hover:text-emerald-900 underline font-medium"
                                    >
                                      PMID:{pmidClean} <ExternalLink className="size-2.5" />
                                    </a>
                                  ) : (
                                    <span className="text-slate-600">{src.source_title || src.citation_type}</span>
                                  )}
                                </div>
                              )
                            })
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Clinical Titration & Directives */}
        {activeTab === "directives" && (
          <TitrationAdvisor titration={evaluation.titration_plan} surveillance={evaluation.surveillance} />
        )}

        {/* Tab 3: Contraindications & Patient Modifiers */}
        {activeTab === "contraindications" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                <AlertCircle className="size-3.5 text-rose-600" /> Contraindications Triggered
              </h4>
              {evaluation.contraindications_triggered.length === 0 ? (
                <p className="text-xs text-slate-500">None triggered for this patient profile.</p>
              ) : (
                <ul className="space-y-1.5">
                  {evaluation.contraindications_triggered.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-rose-800 bg-rose-50 p-2 rounded">
                      <AlertTriangle className="size-3.5 shrink-0 mt-0.5 text-rose-600" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                <Clock className="size-3.5 text-indigo-600" /> Patient Risk Modifiers
              </h4>
              {evaluation.patient_risk_modifiers.length === 0 ? (
                <p className="text-xs text-slate-500">No active patient risk modifiers flagged.</p>
              ) : (
                <ul className="space-y-1.5">
                  {evaluation.patient_risk_modifiers.map((item, i) => (
                    <li key={i} className="text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-100">
                      • {item}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Bottom Practitioner Action Bar */}
        <div className="pt-3 border-t border-slate-200/60 flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-500">
            {signedOffAction ? (
              <span className="inline-flex items-center gap-1.5 font-semibold text-emerald-700 bg-emerald-100/70 px-2.5 py-1 rounded">
                <CheckCircle2 className="size-3.5 text-emerald-600" />
                Decision recorded: {signedOffAction.toUpperCase()}
              </span>
            ) : (
              <span>Practitioner sign-off required prior to clinical prescription.</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={signedOffAction === "reject"}
              onClick={() => handleSignOff("reject")}
              className="text-rose-700 border-rose-200 hover:bg-rose-50"
            >
              <XCircle className="size-3.5 mr-1" /> Reject
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={signedOffAction === "modify"}
              onClick={() => handleSignOff("modify")}
              className="text-amber-800 border-amber-200 hover:bg-amber-50"
            >
              <AlertTriangle className="size-3.5 mr-1" /> Modify Co-Rx
            </Button>
            <Button
              size="sm"
              disabled={signedOffAction === "accept"}
              onClick={() => handleSignOff("accept")}
              className="bg-emerald-700 hover:bg-emerald-800 text-white"
            >
              <CheckCircle2 className="size-3.5 mr-1" /> Accept Assessment
            </Button>
          </div>
        </div>
      </div>
    </article>
  )
}
