const VARIANTS = {
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-700 ring-amber-200',
  error:   'bg-rose-50 text-rose-700 ring-rose-200',
  info:    'bg-blue-50 text-blue-700 ring-blue-200',
  neutral: 'bg-ink-100 text-ink-600 ring-ink-200',
  brand:   'bg-brand-50 text-brand-700 ring-brand-200',
}

const STATUS_MAP = {
  completed: 'success',
  complete: 'success',
  success: 'success',
  done: 'success',
  finished: 'success',
  running: 'info',
  in_progress: 'info',
  processing: 'info',
  generating: 'info',
  evaluating: 'info',
  queued: 'neutral',
  pending: 'warning',
  waiting: 'warning',
  failed: 'error',
  error: 'error',
  cancelled: 'neutral',
  canceled: 'neutral',
  draft: 'neutral',
}

export default function StatusBadge({ status, label, variant }) {
  const key = String(status || '').toLowerCase()
  const v = variant || STATUS_MAP[key] || 'neutral'
  const text = label || status || 'unknown'

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ring-1 ring-inset ${VARIANTS[v]}`}
    >
      {String(text).replace(/_/g, ' ')}
    </span>
  )
}