import React from 'react'

export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

const toneStyles = {
  blue: 'border-blue-200 bg-blue-50 text-blue-700',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  amber: 'border-amber-200 bg-amber-50 text-amber-700',
  rose: 'border-rose-200 bg-rose-50 text-rose-700',
  violet: 'border-violet-200 bg-violet-50 text-violet-700',
  slate: 'border-slate-200 bg-slate-50 text-slate-700',
}

const metricToneStyles = {
  blue: 'from-blue-50 to-white text-blue-700 ring-blue-100',
  emerald: 'from-emerald-50 to-white text-emerald-700 ring-emerald-100',
  amber: 'from-amber-50 to-white text-amber-700 ring-amber-100',
  rose: 'from-rose-50 to-white text-rose-700 ring-rose-100',
  violet: 'from-violet-50 to-white text-violet-700 ring-violet-100',
  slate: 'from-slate-50 to-white text-slate-700 ring-slate-100',
}

export function Surface({ children, className = '', as: Component = 'section' }) {
  return (
    <Component className={cn('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>
      {children}
    </Component>
  )
}

export function StatusBadge({ children, tone = 'slate', className = '' }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold',
        toneStyles[tone] || toneStyles.slate,
        className,
      )}
    >
      {children}
    </span>
  )
}

export function MetricCard({ label, value, meta, icon: Icon, tone = 'blue', className = '' }) {
  return (
    <Surface className={cn('bg-gradient-to-br p-4 ring-1', metricToneStyles[tone] || metricToneStyles.blue, className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">{value}</p>
          {meta && <p className="mt-1 text-xs text-slate-500">{meta}</p>}
        </div>
        {Icon && (
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white/80 shadow-sm">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </div>
        )}
      </div>
    </Surface>
  )
}

export function ProgressBar({ value = 0, tone = 'blue', className = '' }) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0))
  const fills = {
    blue: 'bg-blue-600',
    emerald: 'bg-emerald-600',
    amber: 'bg-amber-500',
    rose: 'bg-rose-600',
    violet: 'bg-violet-600',
    slate: 'bg-slate-600',
  }

  return (
    <div className={cn('h-2 overflow-hidden rounded-full bg-slate-100', className)}>
      <div className={cn('h-full rounded-full transition-all duration-500', fills[tone] || fills.blue)} style={{ width: `${safeValue}%` }} />
    </div>
  )
}

export function SectionHeader({ eyebrow, title, action, children, className = '' }) {
  return (
    <div className={cn('flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between', className)}>
      <div className="min-w-0">
        {eyebrow && <p className="text-xs font-bold uppercase tracking-wide text-blue-700">{eyebrow}</p>}
        <h2 className="mt-1 text-xl font-bold text-slate-950">{title}</h2>
        {children && <p className="mt-1 max-w-3xl text-sm text-slate-500">{children}</p>}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, body, action, className = '' }) {
  return (
    <div className={cn('flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center', className)}>
      {Icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-white text-slate-500 shadow-sm">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
      )}
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      {body && <p className="mt-1 max-w-sm text-sm text-slate-500">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function IconButton({ label, children, className = '', ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-blue-200 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
