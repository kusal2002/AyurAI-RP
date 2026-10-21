import * as React from "react"
import { AlertOctagon, FlaskConical, Inbox, Loader2, RefreshCw } from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ErrorInfo } from "@/context/workspace"
import { cn } from "@/lib/utils"

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1.5 text-xs font-semibold tracking-wide text-emerald-700 uppercase">
            {eyebrow}
          </p>
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && (
          <div className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-500">{description}</div>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Panel({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
  id,
  step,
}: {
  title?: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
  bodyClassName?: string
  id?: string
  step?: number
}) {
  return (
    <section
      id={id}
      className={cn(
        "min-w-0 rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/30",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            {step !== undefined && (
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-xs font-bold text-emerald-800 ring-1 ring-emerald-200">
                {step}
              </span>
            )}
            <div className="min-w-0">
              {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
              {description && <div className="mt-0.5 text-xs leading-5 text-slate-500">{description}</div>}
            </div>
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  )
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon
  title: string
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center px-4 py-10 text-center", className)}>
      <div className="flex size-11 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
        <Icon aria-hidden className="size-5" />
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-800">{title}</h3>
      {description && (
        <div className="mt-1 max-w-md text-sm leading-6 text-slate-500">{description}</div>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({
  error,
  title = "The request could not be completed",
  onRetry,
}: {
  error: ErrorInfo
  title?: string
  onRetry?: () => void
}) {
  return (
    <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50/60 p-4">
      <div className="flex items-start gap-3">
        <AlertOctagon aria-hidden className="mt-0.5 size-5 shrink-0 text-rose-700" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-rose-900">{title}</p>
          <p className="mt-1 text-sm leading-6 text-rose-800">{error.message}</p>
          {error.details.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-rose-800">
              {error.details.map((detail) => (
                <li key={detail} className="break-words">
                  {detail}
                </li>
              ))}
            </ul>
          )}
          {onRetry && (
            <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
              <RefreshCw /> Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export function LoadingState({ label, lines = 3 }: { label: string; lines?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 aria-hidden className="size-4 animate-spin text-emerald-700" />
        {label}
      </p>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton key={index} className="h-4 bg-slate-100" style={{ width: `${90 - index * 15}%` }} />
      ))}
    </div>
  )
}

export function Notice({
  tone = "info",
  icon: Icon,
  title,
  children,
  className,
}: {
  tone?: "info" | "caution" | "demo" | "neutral" | "critical"
  icon?: LucideIcon
  title?: string
  children: React.ReactNode
  className?: string
}) {
  const styles = {
    info: "border-sky-200 bg-sky-50/70 text-sky-900",
    caution: "border-amber-200 bg-amber-50/70 text-amber-900",
    demo: "border-violet-200 bg-violet-50/70 text-violet-900",
    neutral: "border-slate-200 bg-slate-50 text-slate-700",
    critical: "border-rose-200 bg-rose-50/70 text-rose-900",
  }[tone]
  const DefaultIcon = Icon ?? (tone === "demo" ? FlaskConical : AlertOctagon)
  return (
    <div className={cn("flex gap-3 rounded-xl border px-4 py-3 text-xs leading-5", styles, className)}>
      <DefaultIcon aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}

export function KeyValueList({
  items,
  className,
}: {
  items: { label: string; value: React.ReactNode }[]
  className?: string
}) {
  return (
    <dl className={cn("divide-y divide-slate-100 rounded-xl border border-slate-200", className)}>
      {items.map((item) => (
        <div key={item.label} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-4 py-2.5">
          <dt className="text-xs text-slate-500">{item.label}</dt>
          <dd className="min-w-0 max-w-full text-right text-sm font-medium break-words text-slate-800 sm:max-w-[65%]">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function IdChip({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <code
      className={cn(
        "inline-block max-w-full truncate rounded-md bg-slate-100 px-1.5 py-0.5 align-middle font-mono text-[11px] text-slate-700",
        className,
      )}
    >
      {children}
    </code>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  label: string
  className?: string
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      aria-label={label}
      className={cn(
        "h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 focus:outline-none",
        className,
      )}
    />
  )
}

export function FilterChips<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition",
              selected
                ? "bg-emerald-700 text-white ring-emerald-700"
                : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50",
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export const fieldClass =
  "mt-1.5 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100 focus:outline-none disabled:bg-slate-50 disabled:text-slate-400"
