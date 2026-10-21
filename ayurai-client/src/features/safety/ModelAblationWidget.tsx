import * as React from "react"
import {
  Check,
  Copy,
  Flame,
  Layers,
  Sparkles,
} from "lucide-react"

import { Button } from "@/components/ui/button"

export function ModelAblationWidget() {
  const [selectedMetric, setSelectedMetric] = React.useState<"macro_f1" | "accuracy" | "pr_auc" | "brier">("macro_f1")
  const [copiedLatex, setCopiedLatex] = React.useState(false)

  const models = [
    {
      id: "M1",
      name: "Heuristic Rules Alone",
      desc: "Static dictionary & rule lookup",
      accuracy: 32.7,
      macro_f1: 0.3944,
      pr_auc: 0.4869,
      roc_auc: 0.6439,
      sensitivity: 0.5608,
      specificity: 0.7501,
      brier: 0.9693,
      color: "bg-slate-400",
      textColor: "text-slate-600",
    },
    {
      id: "M2",
      name: "Static GNN Link Alone",
      desc: "Patient-blind GAT graph link prediction",
      accuracy: 26.0,
      macro_f1: 0.3966,
      pr_auc: 0.5788,
      roc_auc: 0.6650,
      sensitivity: 0.6389,
      specificity: 0.6921,
      brier: 1.4079,
      color: "bg-sky-400",
      textColor: "text-sky-700",
    },
    {
      id: "M3",
      name: "Naive Context Concat",
      desc: "Flat concatenation [h || x] into MLP",
      accuracy: 73.3,
      macro_f1: 0.2821,
      pr_auc: 0.7898,
      roc_auc: 0.8834,
      sensitivity: 0.3333,
      specificity: 0.6667,
      brier: 0.3367,
      color: "bg-amber-400",
      textColor: "text-amber-700",
    },
    {
      id: "M4",
      name: "Context Fusion (Ours)",
      desc: "Dynamic vulnerability gating + safety override",
      accuracy: 90.7,
      macro_f1: 0.8771,
      pr_auc: 0.9403,
      roc_auc: 0.9640,
      sensitivity: 0.8707,
      specificity: 0.9173,
      brier: 0.1549,
      color: "bg-emerald-600",
      textColor: "text-emerald-700",
      highlight: true,
    },
  ]

  const subgroups = [
    { name: "Overall Patient Cohort", count: 1000, m3: 0.2846, m4: 0.8395, gain: "+195.0%" },
    { name: "Renal Impairment (eGFR < 60)", count: 244, m3: 0.2784, m4: 0.7327, gain: "+163.2%" },
    { name: "Polypharmacy (≥ 3 co-medications)", count: 662, m3: 0.2891, m4: 0.7581, gain: "+162.2%" },
    { name: "Elderly Cohort (Age ≥ 65)", count: 308, m3: 0.2871, m4: 0.6579, gain: "+129.2%" },
  ]

  const latexCode = `\\begin{table*}[t]
\\centering
\\caption{Ablation Study: Empirical Performance Comparison on Held-Out Test Set (N = 150).}
\\begin{tabular}{llccccc}
\\toprule
\\textbf{Model} & \\textbf{Strategy} & \\textbf{Accuracy} & \\textbf{Macro-F1} & \\textbf{PR-AUC} & \\textbf{Sensitivity} & \\textbf{Brier Score} \\\\
\\midrule
$M_1$ (Rules) & Static Lookup & 32.7\\% & 0.3944 & 0.4869 & 0.5608 & 0.9693 \\\\
$M_2$ (GNN) & Static Graph & 26.0\\% & 0.3966 & 0.5788 & 0.6389 & 1.4079 \\\\
$M_3$ (Naive Concat) & Concatenation & 73.3\\% & 0.2821 & 0.7898 & 0.3333 & 0.3367 \\\\
$M_4$ (\\textbf{Ours}) & \\textbf{Vulnerability Gating} & \\textbf{90.7\\%} & \\textbf{0.8771} & \\textbf{0.9403} & \\textbf{0.8707} & \\textbf{0.1549} \\\\
\\bottomrule
\\end{tabular}
\\end{table*}`

  function copyLatex() {
    navigator.clipboard.writeText(latexCode)
    setCopiedLatex(true)
    setTimeout(() => setCopiedLatex(false), 2000)
  }

  return (
    <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-emerald-100 p-1 text-emerald-800">
              <Sparkles className="size-4" />
            </span>
            <h3 className="text-base font-bold text-slate-900">
              Component 3: Research Ablation Benchmarks (Chapter 5 Validation)
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Empirical comparison of architectural models across the 500 patient cohort (1,000 paired evaluations).
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={copyLatex}
          className="text-xs gap-1.5 border-slate-200 hover:bg-slate-50"
        >
          {copiedLatex ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
          {copiedLatex ? "LaTeX Copied!" : "Copy LaTeX for Thesis"}
        </Button>
      </div>

      {/* Novelty Performance Callout Banner */}
      <div className="rounded-xl border border-emerald-300 bg-gradient-to-r from-emerald-500/10 via-teal-500/5 to-transparent p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-emerald-700 text-white p-2.5 shadow-sm">
            <Flame className="size-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-emerald-950">
              Novelty Confirmed: +210.9% Macro-F1 Gain over Naive Context Concat
            </h4>
            <p className="text-xs text-emerald-800">
              Dynamic vulnerability gating prevents minority-class safety collapse, elevating Macro-F1 from 0.2821 ($M_3$) to <strong>0.8771 ($M_4$)</strong>.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-semibold">
          <div className="text-center">
            <span className="block text-slate-400 uppercase text-[10px]">Test Accuracy</span>
            <span className="text-base font-extrabold text-emerald-800">90.7%</span>
          </div>
          <div className="text-center">
            <span className="block text-slate-400 uppercase text-[10px]">PR-AUC</span>
            <span className="text-base font-extrabold text-emerald-800">0.9403</span>
          </div>
          <div className="text-center">
            <span className="block text-slate-400 uppercase text-[10px]">Brier Score</span>
            <span className="text-base font-extrabold text-emerald-800">0.1549</span>
          </div>
        </div>
      </div>

      {/* Metric Selector Tabs */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
            Model Performance Comparison (Held-Out Test Set N = 150)
          </span>
          <div className="flex gap-1.5 rounded-lg bg-slate-100 p-1 text-xs">
            <button
              type="button"
              onClick={() => setSelectedMetric("macro_f1")}
              className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                selectedMetric === "macro_f1" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Macro-F1
            </button>
            <button
              type="button"
              onClick={() => setSelectedMetric("accuracy")}
              className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                selectedMetric === "accuracy" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Accuracy
            </button>
            <button
              type="button"
              onClick={() => setSelectedMetric("pr_auc")}
              className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                selectedMetric === "pr_auc" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              PR-AUC
            </button>
            <button
              type="button"
              onClick={() => setSelectedMetric("brier")}
              className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                selectedMetric === "brier" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Brier Score
            </button>
          </div>
        </div>

        {/* Comparative Bars */}
        <div className="space-y-2.5 pt-1">
          {models.map((m) => {
            const rawVal =
              selectedMetric === "macro_f1"
                ? m.macro_f1
                : selectedMetric === "accuracy"
                ? m.accuracy / 100
                : selectedMetric === "pr_auc"
                ? m.pr_auc
                : 1.0 - Math.min(1.0, m.brier) // Invert Brier for visual bar (higher is better)

            const displayVal =
              selectedMetric === "accuracy"
                ? `${m.accuracy.toFixed(1)}%`
                : selectedMetric === "brier"
                ? `${m.brier.toFixed(4)} (lower is better)`
                : rawVal.toFixed(4)

            const pctWidth = Math.max(8, Math.min(100, rawVal * 100))

            return (
              <div
                key={m.id}
                className={`rounded-lg border p-3 transition-colors ${
                  m.highlight ? "border-emerald-300 bg-emerald-50/30" : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900">
                      {m.id}: {m.name}
                    </span>
                    <span className="text-[11px] text-slate-500">({m.desc})</span>
                  </div>
                  <span className={`font-mono font-bold ${m.textColor}`}>{displayVal}</span>
                </div>
                <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${m.color}`}
                    style={{ width: `${pctWidth}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Subgroup Analysis Section */}
      <div className="space-y-3 pt-2">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
          <Layers className="size-3.5 text-indigo-600" /> Clinical Vulnerability Subgroups (N = 1,000 Cohort)
        </h4>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Subgroup</th>
                <th className="py-2.5 px-3 text-center">N Samples</th>
                <th className="py-2.5 px-3 text-center">M3 Naive F1</th>
                <th className="py-2.5 px-3 text-center">M4 Context Fusion F1</th>
                <th className="py-2.5 px-3 text-right">Relative Gain</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {subgroups.map((sg, i) => (
                <tr key={i} className="hover:bg-slate-50/50">
                  <td className="py-2 px-3 font-sans font-medium text-slate-900">{sg.name}</td>
                  <td className="py-2 px-3 text-center text-slate-600">{sg.count}</td>
                  <td className="py-2 px-3 text-center text-slate-500">{sg.m3.toFixed(4)}</td>
                  <td className="py-2 px-3 text-center font-bold text-emerald-800 bg-emerald-50/50">
                    {sg.m4.toFixed(4)}
                  </td>
                  <td className="py-2 px-3 text-right font-bold text-emerald-700">{sg.gain}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
