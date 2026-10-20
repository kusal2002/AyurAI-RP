import * as React from "react"
import { useLocation, useNavigate } from "react-router"
import { FlaskConical, Leaf, LogIn } from "lucide-react"

import { Notice, fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { useWorkspace } from "@/context/workspace"
import { errorMessage } from "@/lib/api/client"

/** Component 4 sign-in (JWT). Required for live mode; demo mode needs no account. */
export function LoginPage() {
  const { signIn } = useAuth()
  const { mode, setMode } = useWorkspace()
  const navigate = useNavigate()
  const location = useLocation()
  // Where to go after sign-in: the page that redirected here, or the overview
  const from = (location.state as { from?: string } | null)?.from ?? "/"

  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await signIn(username.trim(), password)
      if (mode !== "live") setMode("live") // signed-in users work with live services
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
      setPassword("") // never keep the password in state longer than needed
    }
  }

  function continueWithDemo() {
    if (mode !== "demo") setMode("demo")
    navigate("/", { replace: true })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f7f9f8] px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-emerald-700 text-white">
            <Leaf aria-hidden className="size-5" />
          </span>
          <div>
            <p className="text-base font-semibold text-slate-900">AyurAI</p>
            <p className="text-[10px] font-semibold tracking-[0.16em] text-slate-400 uppercase">Clinical workspace</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Sign in</h1>
            <p className="mt-1 text-xs text-slate-500">Required for live mode. Access is limited by your role and clinic.</p>
          </div>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Username</span>
            <input
              className={fieldClass}
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              className={fieldClass}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error && <Notice tone="critical">{error}</Notice>}

          <Button type="submit" className="w-full bg-emerald-700 hover:bg-emerald-800" disabled={submitting}>
            <LogIn /> {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <Button variant="outline" className="mt-3 w-full" onClick={continueWithDemo}>
          <FlaskConical /> Continue with demo data (no sign-in)
        </Button>
        <p className="mt-3 text-center text-[11px] text-slate-400">
          Demo mode shows fictional fixtures only; nothing is sent to any service.
        </p>
      </div>
    </div>
  )
}
