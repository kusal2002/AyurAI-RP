import * as React from "react"
import { useNavigate } from "react-router"
import { FileJson, FileUp, Play, PlayCircle } from "lucide-react"

import { EmptyState, IdChip, Notice, PageHeader, Panel, fieldClass } from "@/components/shared/page"
import { StatusBadge, decisionSpec, serviceStateSpecs, sufficiencySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { KnowledgeScopeToggle } from "@/components/shared/c2"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { c1View, type C1ScreeningPayload } from "@/lib/api/types"
import { formatScore } from "@/lib/labels"
import { cn } from "@/lib/utils"
import scenarioFile from "@/lib/samples/c1_screening_scenarios.json"

type Scenario = { scenario_id: string; title: string; expected: string; payload: C1ScreeningPayload }
const scenarios = (scenarioFile as { scenarios: Scenario[] }).scenarios

const MAX_FILE_BYTES = 5 * 1024 * 1024
const MAX_PAYLOADS = 200

/** Light structural check; the service validates the full contract. */
function looksLikePayload(value: unknown): value is C1ScreeningPayload {
  if (typeof value !== "object" || value === null) return false
  const record = value as Record<string, unknown>
  const result = record.screening_result as Record<string, unknown> | undefined
  return (
    typeof record.screening_id === "string" &&
    typeof result?.risk_level === "string" &&
    Array.isArray(record.symptoms)
  )
}

/** Accepts one payload, an array, {payloads: [...]} or {scenarios: [{payload}]}. */
function extractPayloads(parsed: unknown): { payloads: C1ScreeningPayload[]; rejected: number } {
  let items: unknown[] = []
  if (Array.isArray(parsed)) items = parsed
  else if (typeof parsed === "object" && parsed !== null) {
    const record = parsed as Record<string, unknown>
    if (Array.isArray(record.payloads)) items = record.payloads
    else if (Array.isArray(record.scenarios))
      items = (record.scenarios as Record<string, unknown>[]).map((item) => item.payload)
    else items = [parsed]
  }
  const payloads = items.filter(looksLikePayload)
  return { payloads, rejected: items.length - payloads.length }
}

function symptomSummary(payload: C1ScreeningPayload) {
  const present = c1View(payload).symptoms.filter((item) => item.present).map((item) => item.name)
  return present.length ? present.join(", ") : "none present"
}

function OutcomeBadge({ record }: { record: CaseRecord }) {
  const state = record.c2
  if (state.status === "loading") return <StatusBadge spec={serviceStateSpecs.loading} />
  if (state.status === "idle") return <span className="text-xs text-slate-400">Queued</span>
  if (state.status === "error") {
    const mapping = record.c1?.mapping
    const label =
      mapping?.status === "blocked"
        ? "Blocked"
        : mapping?.status === "insufficient_input"
          ? "No symptom resolved"
          : "Request failed"
    return <StatusBadge spec={{ ...serviceStateSpecs.degraded, label }} />
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <StatusBadge spec={decisionSpec(state.data.decision)} />
      {state.data.decision !== "abstain" && <StatusBadge spec={sufficiencySpec(state.data.sufficiency_status)} />}
    </span>
  )
}

export function ImportC1Page() {
  const { cases, importC1Payloads, selectCase, knowledgeScope, setKnowledgeScope } = useWorkspace()
  const navigate = useNavigate()
  const [text, setText] = React.useState("")
  const [sourceLabel, setSourceLabel] = React.useState("pasted JSON")
  const [parseError, setParseError] = React.useState<string | null>(null)
  const [running, setRunning] = React.useState(false)
  const [importedIds, setImportedIds] = React.useState<string[]>([])

  const parsed = React.useMemo(() => {
    if (!text.trim()) return null
    try {
      return extractPayloads(JSON.parse(text))
    } catch {
      return null
    }
  }, [text])

  const imported = cases.filter((record) => importedIds.includes(record.id))

  const loadScenario = (id: string) => {
    const scenario = scenarios.find((item) => item.scenario_id === id)
    if (!scenario) return
    setText(JSON.stringify(scenario.payload, null, 2))
    setSourceLabel(`synthetic scenario ${scenario.scenario_id}`)
    setParseError(null)
  }

  const loadAllScenarios = () => {
    setText(JSON.stringify(scenarios.map((item) => item.payload), null, 2))
    setSourceLabel("synthetic scenarios (all)")
    setParseError(null)
  }

  const onFile = async (file: File | undefined) => {
    if (!file) return
    if (file.size > MAX_FILE_BYTES) {
      setParseError("File is larger than 5 MB.")
      return
    }
    setText(await file.text())
    setSourceLabel(`file ${file.name}`)
    setParseError(null)
  }

  const run = async () => {
    if (!text.trim()) return
    let result
    try {
      result = extractPayloads(JSON.parse(text))
    } catch {
      setParseError("Not valid JSON.")
      return
    }
    if (result.payloads.length === 0) {
      setParseError("No Component 1 payload found (expected screening_id, screening_result.risk_level and symptoms).")
      return
    }
    if (result.payloads.length > MAX_PAYLOADS) {
      setParseError(`At most ${MAX_PAYLOADS} payloads per run.`)
      return
    }
    setParseError(null)
    setRunning(true)
    try {
      const ids = await importC1Payloads(result.payloads, sourceLabel)
      setImportedIds((current) => [...ids, ...current])
    } finally {
      setRunning(false)
    }
  }

  const open = (id: string) => {
    selectCase(id)
    navigate("/analysis")
  }

  return (
    <>
      <PageHeader
        eyebrow="Component 1 → Component 2"
        title="Import Component 1 output"
        description="Send Component 1 screening payloads through the integration endpoint. The service maps symptom names to knowledge-graph symptoms without guessing, then runs Component 2 reasoning."
      />

      <div className="mb-5">
        <KnowledgeScopeToggle value={knowledgeScope} onChange={setKnowledgeScope} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Payloads" description="One payload, a JSON array, a {payloads: [...]} file, or the scenario file">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <span>Synthetic scenario</span>
              <select
                className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-sm"
                defaultValue=""
                onChange={(event) => loadScenario(event.target.value)}
                aria-label="Load a synthetic scenario"
              >
                <option value="" disabled>
                  Choose…
                </option>
                {scenarios.map((item) => (
                  <option key={item.scenario_id} value={item.scenario_id}>
                    {item.scenario_id}: {item.title}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="outline" size="sm" onClick={loadAllScenarios}>
              <FileJson /> All {scenarios.length} scenarios
            </Button>
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
              <FileUp className="size-3.5" aria-hidden /> Upload JSON file
              <input
                type="file"
                accept="application/json,.json"
                className="sr-only"
                onChange={(event) => void onFile(event.target.files?.[0])}
              />
            </label>
          </div>
          <textarea
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              setSourceLabel("pasted JSON")
            }}
            spellCheck={false}
            rows={16}
            aria-label="Component 1 payload JSON"
            placeholder='{"screening_id": "...", "screening_result": {"risk_level": "moderate", ...}, "symptoms": [{"name": "fatigue", "present": true}], ...}'
            className={cn(fieldClass, "h-auto min-h-64 py-2 font-mono text-xs")}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-slate-500">
              {parsed
                ? `${parsed.payloads.length} payload(s) recognised${parsed.rejected ? `, ${parsed.rejected} item(s) ignored` : ""} · source: ${sourceLabel}`
                : text.trim()
                  ? "Not valid JSON yet."
                  : "Load a scenario, upload a file or paste JSON."}
            </p>
            <Button
              className="bg-emerald-700 hover:bg-emerald-800"
              disabled={running || !parsed?.payloads.length}
              onClick={() => void run()}
            >
              <Play /> {running ? "Running…" : `Run ${parsed?.payloads.length ?? 0} through C1 → C2`}
            </Button>
          </div>
          {parseError && (
            <Notice tone="critical" title="Cannot import" className="mt-3">
              {parseError}
            </Notice>
          )}
        </Panel>

        <Panel title="What is sent">
          <ul className="list-disc space-y-1.5 pl-5 text-xs leading-5 text-slate-600">
            <li>The whole payload goes to the Component 2 service, which validates the provisional C1 contract.</li>
            <li>
              Component 2 keeps only the risk tier, the confidence (as metadata) and the IDs of present symptoms that
              resolve exactly by ID, name or alias. Unknown and ambiguous names are reported, never guessed.
            </li>
            <li>Haemoglobin, modality results and demographics are not used for reasoning.</li>
            <li>Cases stay in this browser tab only: a refresh keeps them, closing the tab clears them.</li>
            <li>
              Synthetic scenarios are invented. NHANES reference-derived files (from{" "}
              <code>python -m app.integration.c1_reference_samples</code>) contain real de-identified survey data:
              statistical use only, never attempt to identify anyone.
            </li>
          </ul>
        </Panel>
      </div>

      <Panel title="Imported in this session" className="mt-6" bodyClassName="p-0">
        {imported.length === 0 ? (
          <div className="p-5">
            <EmptyState icon={PlayCircle} title="Nothing imported yet" description="Run payloads to see the symptom mapping and the Component 2 outcome for each." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-3">Screening</th>
                  <th className="px-3 py-3">Tier</th>
                  <th className="px-3 py-3">Confidence</th>
                  <th className="px-3 py-3">Present symptoms</th>
                  <th className="px-3 py-3">Mapping</th>
                  <th className="px-3 py-3">Component 2</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {imported.map((record) => {
                  const payload = record.c1?.payload
                  const mapping = record.c1?.mapping
                  return (
                    <tr key={record.id}>
                      <td className="px-5 py-2.5">
                        <IdChip>{record.caseRef}</IdChip>
                        <p className="mt-0.5 text-[11px] text-slate-400">{record.c1?.payloadSource}</p>
                      </td>
                      <td className="px-3 py-2.5 capitalize">{payload?.screening_result.risk_level}</td>
                      <td className="px-3 py-2.5">{payload ? formatScore(c1View(payload).confidence) : "—"}</td>
                      <td className="px-3 py-2.5 text-xs text-slate-600">{payload ? symptomSummary(payload) : "—"}</td>
                      <td className="px-3 py-2.5 text-xs text-slate-600">
                        {mapping ? (
                          <>
                            {mapping.resolved_symptoms.length} resolved
                            {mapping.unresolved_symptoms.length > 0 && (
                              <span className="text-amber-700">
                                {" "}
                                · {mapping.unresolved_symptoms.map((item) => `${item.input_name} (${item.status.replace(/_/g, " ")})`).join(", ")}
                              </span>
                            )}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <OutcomeBadge record={record} />
                        {record.c2.status === "success" && (
                          <p className="mt-0.5 text-[11px] text-slate-400">
                            {record.c2.data.candidates.length} candidate(s)
                          </p>
                        )}
                      </td>
                      <td className="px-5 py-2.5 text-right">
                        <Button variant="outline" size="sm" onClick={() => open(record.id)}>
                          Open
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
