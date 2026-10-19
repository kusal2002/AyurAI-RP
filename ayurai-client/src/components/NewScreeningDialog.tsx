
import { useState } from "react"
import {
  Activity,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Upload,
  UserRound,
  X,
} from "lucide-react"

type Props = {
  onClose: () => void
}

type ScreeningFile = File | null

function UploadField({
  title,
  description,
  file,
  accept,
  onChange,
}: {
  title: string
  description: string
  file: ScreeningFile
  accept: string
  onChange: (file: ScreeningFile) => void
}) {
  return (
    <label className="flex cursor-pointer flex-col rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4 transition hover:border-emerald-500 hover:bg-emerald-50/40">
      <span className="flex items-center gap-2 text-sm font-semibold text-slate-800">
        <Upload size={17} className="text-emerald-700" />
        {title}
      </span>
      <span className="mt-1 text-xs leading-5 text-slate-500">
        {description}
      </span>
      <span className="mt-3 truncate text-xs font-medium text-emerald-800">
        {file ? file.name : "Choose a local file"}
      </span>
      <input
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
    </label>
  )
}

const inputClass =
  "mt-1.5 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"

export default function NewScreeningDialog({ onClose }: Props) {
  const [step, setStep] = useState(1)
  const [caseReference, setCaseReference] = useState("AY-DEMO-001")
  const [ageGroup, setAgeGroup] = useState("")
  const [sexAtBirth, setSexAtBirth] = useState("not-provided")

  const [eyeImage, setEyeImage] = useState<ScreeningFile>(null)
  const [tongueImage, setTongueImage] = useState<ScreeningFile>(null)
  const [nailImage, setNailImage] = useState<ScreeningFile>(null)
  const [ppgFile, setPpgFile] = useState<ScreeningFile>(null)

  const [fatigue, setFatigue] = useState("not-answered")
  const [dizziness, setDizziness] = useState("not-answered")
  const [dietContext, setDietContext] = useState("not-answered")
  const [completed, setCompleted] = useState(false)

  const inputCount = [
    eyeImage,
    tongueImage,
    nailImage,
    ppgFile,
  ].filter(Boolean).length

  function nextStep() {
    setStep((current) => Math.min(3, current + 1))
  }

  function previousStep() {
    setStep((current) => Math.max(1, current - 1))
  }

  const steps = [
    { number: 1, label: "Case context", icon: UserRound },
    { number: 2, label: "Screening inputs", icon: Activity },
    { number: 3, label: "Review", icon: ClipboardList },
  ]

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center overflow-y-auto bg-slate-950/40 p-3 backdrop-blur-sm sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="screening-title"
        className="my-auto flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4 sm:px-7">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-700">
              <Activity size={15} />
              SCREENING WORKSPACE
            </div>
            <h2
              id="screening-title"
              className="mt-1.5 text-xl font-semibold tracking-tight text-slate-900"
            >
              {completed ? "Demo screening prepared" : "New screening"}
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Local prototype · No patient data is sent to a server
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close screening form"
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X size={19} />
          </button>
        </header>

        {!completed && (
          <div className="grid grid-cols-3 gap-2 border-b border-slate-100 px-5 py-4 sm:px-7">
            {steps.map(({ number, label, icon: Icon }) => (
              <div
                key={number}
                className={`flex items-center gap-2 rounded-xl p-2 sm:p-3 ${
                  step === number
                    ? "bg-emerald-50 text-emerald-800"
                    : step > number
                      ? "text-emerald-700"
                      : "text-slate-400"
                }`}
              >
                {step > number ? (
                  <CheckCircle2 size={19} className="shrink-0" />
                ) : (
                  <Icon size={19} className="shrink-0" />
                )}
                <span className="min-w-0">
                  <span className="block text-[10px] opacity-70">
                    STEP {number}
                  </span>
                  <span className="block truncate text-xs font-semibold sm:text-sm">
                    {label}
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7 sm:py-6">
          {completed ? (
            <div className="py-8 text-center">
              <div className="mx-auto flex size-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
                <CheckCircle2 size={32} />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-slate-900">
                Demo workflow complete
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
                The form was completed locally for interface testing. No
                screening case was created in a database, no AI inference ran,
                and no clinical result was generated.
              </p>
              <button
                onClick={onClose}
                className="mt-6 rounded-xl bg-emerald-700 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-800"
              >
                Return to dashboard
              </button>
            </div>
          ) : (
            <>
              {step === 1 && (
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    Case context
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    Use fictional information while testing this prototype.
                    We will connect validated fields to the screening API later.
                  </p>

                  <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <label className="text-sm font-medium text-slate-700">
                      Case reference
                      <input
                        value={caseReference}
                        onChange={(event) =>
                          setCaseReference(event.target.value)
                        }
                        placeholder="AY-DEMO-001"
                        className={inputClass}
                      />
                    </label>

                    <label className="text-sm font-medium text-slate-700">
                      Age group
                      <select
                        value={ageGroup}
                        onChange={(event) => setAgeGroup(event.target.value)}
                        className={inputClass}
                      >
                        <option value="">Not specified</option>
                        <option value="under-18">Under 18</option>
                        <option value="18-29">18–29 years</option>
                        <option value="30-44">30–44 years</option>
                        <option value="45-59">45–59 years</option>
                        <option value="60-plus">60 years or older</option>
                      </select>
                    </label>

                    <label className="text-sm font-medium text-slate-700 sm:col-span-2">
                      Sex assigned at birth
                      <select
                        value={sexAtBirth}
                        onChange={(event) => setSexAtBirth(event.target.value)}
                        className={inputClass}
                      >
                        <option value="not-provided">Not provided</option>
                        <option value="female">Female</option>
                        <option value="male">Male</option>
                        <option value="other">Other / prefer to describe</option>
                      </select>
                      <span className="mt-1.5 block text-xs font-normal text-slate-400">
                        Optional prototype field; actual requirements need
                        clinical and ethics review.
                      </span>
                    </label>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    Screening inputs
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    Select local sample files to preview the input workflow.
                    Files stay in this browser and are not uploaded.
                  </p>

                  <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <UploadField
                      title="Eye / conjunctiva image"
                      description="Image file: JPG, PNG or WebP"
                      file={eyeImage}
                      accept="image/jpeg,image/png,image/webp"
                      onChange={setEyeImage}
                    />
                    <UploadField
                      title="Tongue image"
                      description="Image file: JPG, PNG or WebP"
                      file={tongueImage}
                      accept="image/jpeg,image/png,image/webp"
                      onChange={setTongueImage}
                    />
                    <UploadField
                      title="Nail images"
                      description="Image file: JPG, PNG or WebP"
                      file={nailImage}
                      accept="image/jpeg,image/png,image/webp"
                      onChange={setNailImage}
                    />
                    <UploadField
                      title="PPG signal sample"
                      description="Signal file: CSV, JSON or TXT"
                      file={ppgFile}
                      accept=".csv,.json,.txt,text/csv,application/json,text/plain"
                      onChange={setPpgFile}
                    />
                  </div>

                  <div className="mt-6 rounded-xl border border-slate-200 p-4">
                    <h4 className="text-sm font-semibold text-slate-800">
                      Structured questionnaire
                    </h4>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Example fields only; this is not yet the approved research
                      questionnaire.
                    </p>
                    <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <label className="text-sm text-slate-600">
                        Unusual fatigue
                        <select
                          value={fatigue}
                          onChange={(event) => setFatigue(event.target.value)}
                          className={inputClass}
                        >
                          <option value="not-answered">Not answered</option>
                          <option value="yes">Yes</option>
                          <option value="no">No</option>
                        </select>
                      </label>
                      <label className="text-sm text-slate-600">
                        Dizziness
                        <select
                          value={dizziness}
                          onChange={(event) => setDizziness(event.target.value)}
                          className={inputClass}
                        >
                          <option value="not-answered">Not answered</option>
                          <option value="yes">Yes</option>
                          <option value="no">No</option>
                        </select>
                      </label>
                      <label className="text-sm text-slate-600 sm:col-span-2">
                        Dietary context
                        <select
                          value={dietContext}
                          onChange={(event) => setDietContext(event.target.value)}
                          className={inputClass}
                        >
                          <option value="not-answered">Not answered</option>
                          <option value="mixed">Mixed diet</option>
                          <option value="vegetarian">Vegetarian</option>
                          <option value="other">Other / not specified</option>
                        </select>
                      </label>
                    </div>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    Review before continuing
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    Confirm the information you entered. This step does not run
                    the screening model or create a persistent case.
                  </p>

                  <div className="mt-5 divide-y divide-slate-100 rounded-xl border border-slate-200">
                    {[
                      ["Case reference", caseReference || "Not provided"],
                      ["Age group", ageGroup || "Not specified"],
                      ["Sex assigned at birth", sexAtBirth],
                      ["Input files selected", `${inputCount} of 4`],
                      ["Fatigue response", fatigue],
                      ["Dizziness response", dizziness],
                      ["Dietary context", dietContext],
                    ].map(([label, value]) => (
                      <div
                        key={label}
                        className="flex flex-wrap justify-between gap-2 px-4 py-3"
                      >
                        <span className="text-sm text-slate-500">{label}</span>
                        <span className="max-w-[60%] break-words text-right text-sm font-medium text-slate-800">
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
                    <ClipboardList size={18} className="mt-0.5 shrink-0" />
                    <p>
                      <strong>Demo only:</strong> No anemia risk level,
                      Ayurvedic recommendation, safety decision or diagnosis
                      will be produced by this form.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {!completed && (
          <footer className="flex items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/60 px-5 py-4 sm:px-7">
            <button
              onClick={step === 1 ? onClose : previousStep}
              className="inline-flex items-center gap-1 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              {step > 1 && <ChevronLeft size={16} />}
              {step === 1 ? "Cancel" : "Back"}
            </button>

            <span className="hidden text-xs text-slate-400 sm:block">
              Step {step} of 3
            </span>

            <button
              onClick={() => {
                if (step < 3) {
                  nextStep()
                } else {
                  setCompleted(true)
                }
              }}
              disabled={step === 1 && !caseReference.trim()}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {step === 3 ? "Finish demo" : "Continue"}
              {step < 3 && <ChevronRight size={16} />}
            </button>
          </footer>
        )}
      </section>
    </div>
  )
}
