export default function StatCard({
  icon: Icon,
  label,
  title,
  value,
  hint,
  description,
  subtitle,
  accent,
  tone,
  loading = false,
}) {
  const textLabel = label ?? title ?? ''
  const textHint = hint ?? description ?? subtitle
  const accentKey = accent ?? tone ?? 'brand'

  const accents = {
    brand:   'bg-brand-50 text-brand-600',
    ink:     'bg-ink-100 text-ink-600',
    neutral: 'bg-ink-100 text-ink-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    success: 'bg-emerald-50 text-emerald-600',
    amber:   'bg-amber-50 text-amber-600',
    warning: 'bg-amber-50 text-amber-600',
    rose:    'bg-rose-50 text-rose-600',
    error:   'bg-rose-50 text-rose-600',
  }

  return (
    <div className="dx-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            {textLabel}
          </p>
          <div className="mt-2">
            {loading ? (
              <div className="h-7 w-16 animate-pulse rounded bg-ink-100" />
            ) : (
              <p className="text-2xl font-semibold tracking-tight text-ink-900">
                {value ?? '—'}
              </p>
            )}
          </div>
          {textHint && !loading && (
            <p className="mt-1 text-[11px] text-ink-400">{textHint}</p>
          )}
        </div>
        {Icon && (
          <div
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${
              accents[accentKey] || accents.brand
            }`}
          >
            <Icon size={16} />
          </div>
        )}
      </div>
    </div>
  )
}