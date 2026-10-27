// src/components/AlgorithmPicker.jsx
import { useMemo, useState } from 'react'
import {
  ChevronDown,
  Star,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
} from 'lucide-react'
import { ALGORITHM_INFO } from './AlgorithmSummaryCard.jsx'

const ORDER = ['gaussian_copula', 'ctgan', 'tvae']

const isNumericDtype = (d) => /int|float|double|number|numeric|decimal/i.test(d || '')

/**
 * Picks the algorithm that suits the dataset best and says why.
 * Rules are deliberately simple so they can be explained to a user.
 */
export function recommendAlgorithm(profile) {
  const cols = Array.isArray(profile?.columns) ? profile.columns : []
  const rows = Number(profile?.rows) || 0
  if (cols.length === 0) {
    return {
      id: 'gaussian_copula',
      pct: null,
      rows,
      reason: 'Safe default. Open the details below to compare the other algorithms.',
    }
  }
  const numeric = cols.filter((c) => isNumericDtype(c.dtype)).length
  const ratio = numeric / cols.length
  const pct = Math.round(ratio * 100)

  if (ratio >= 0.6) {
    return {
      id: 'gaussian_copula',
      pct,
      rows,
      reason: `${pct}% of your columns are numeric, so Gaussian Copula keeps their distributions and correlations best.`,
    }
  }
  if (rows >= 1500) {
    return {
      id: 'ctgan',
      pct,
      rows,
      reason: `Your data is mostly categorical/mixed (${100 - pct}% non-numeric) and has ${rows.toLocaleString()} rows — enough for CTGAN to learn non-linear patterns between columns.`,
    }
  }
  return {
    id: 'tvae',
    pct,
    rows,
    reason: `Your data is mostly categorical/mixed (${100 - pct}% non-numeric) with only ${rows.toLocaleString()} rows. TVAE trains more stably than CTGAN on smaller datasets.`,
  }
}

function Details({ info }) {
  return (
    <div className="grid grid-cols-1 gap-4 border-t border-ink-100 bg-white/60 p-4 text-xs">
      <div>
        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
          <Zap size={11} className="text-brand-600" /> How it works
        </p>
        <ol className="list-decimal space-y-1 pl-4 leading-relaxed text-ink-700">
          {info.howItWorks.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      </div>
      <div>
        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
          <CheckCircle2 size={11} className="text-emerald-600" /> Strengths
        </p>
        <ul className="space-y-1 leading-relaxed text-ink-700">
          {info.strengths.map((s, i) => (
            <li key={i}>· {s}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
          <AlertTriangle size={11} className="text-amber-600" /> Trade-offs
        </p>
        <ul className="space-y-1 leading-relaxed text-ink-700">
          {info.limitations.map((s, i) => (
            <li key={i}>· {s}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function AlgorithmPicker({
  modelId,
  onSelect,
  disabled,
  profile,
}) {
  const [openId, setOpenId] = useState(null)
  const [showHow, setShowHow] = useState(false)
  const rec = useMemo(() => recommendAlgorithm(profile), [profile])

  return (
    <div className="mt-6">
      <h2 className="mb-3 text-sm font-semibold text-ink-900">
        Generation algorithm
      </h2>

      {/* Recommendation banner */}
      <div className="mb-4 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
        <Lightbulb size={16} className="mt-0.5 shrink-0 text-emerald-700" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-emerald-900">
            Recommended for your data: {ALGORITHM_INFO[rec.id].label}
          </p>
          <p className="mt-0.5 text-xs text-emerald-800">{rec.reason}</p>

          <button
            type="button"
            onClick={() => setShowHow((v) => !v)}
            className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-800 hover:underline"
          >
            How is this chosen?
            <ChevronDown
              size={12}
              className={showHow ? 'rotate-180 transition-transform' : 'transition-transform'}
            />
          </button>

          {showHow && (
            <div className="mt-2 rounded-lg bg-white/70 p-3 text-[11px] leading-snug text-emerald-900">
              <p className="font-semibold">
                We look at two things in your dataset: the share of numeric
                columns and the number of rows.
              </p>
              {rec.pct != null && (
                <p className="mt-1">
                  Your data: <strong>{rec.pct}% numeric columns</strong>,{' '}
                  <strong>{rec.rows.toLocaleString()} rows</strong>.
                </p>
              )}
              <ol className="mt-2 list-decimal space-y-1 pl-4">
                <li className={rec.id === 'gaussian_copula' ? 'font-semibold' : ''}>
                  60% or more numeric columns → Gaussian Copula (best at keeping
                  number distributions and correlations).
                </li>
                <li className={rec.id === 'ctgan' ? 'font-semibold' : ''}>
                  Otherwise, 1,500 or more rows → CTGAN (enough data to learn
                  complex patterns between mixed columns).
                </li>
                <li className={rec.id === 'tvae' ? 'font-semibold' : ''}>
                  Otherwise (smaller, mixed data) → TVAE (trains more stably on
                  fewer rows).
                </li>
              </ol>
              <p className="mt-2 text-emerald-800">
                This is a simple guideline, not a guarantee. You can pick any
                algorithm yourself and compare the results in Evaluation.
              </p>
            </div>
          )}
        </div>
        {modelId !== rec.id && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSelect(rec.id)}
            className="dx-btn-outline shrink-0 text-xs"
          >
            Use recommended
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 items-start gap-3 lg:grid-cols-3">
        {ORDER.map((id) => {
          const info = ALGORITHM_INFO[id]
          if (!info) return null
          const Icon = info.icon
          const active = id === modelId
          const isRec = id === rec.id
          const open = openId === id

          return (
            <div
              key={id}
              className={[
                'overflow-hidden rounded-xl border transition',
                active
                  ? 'border-brand-400 bg-brand-50/40 ring-2 ring-brand-500/20'
                  : isRec
                  ? 'border-emerald-300 bg-white'
                  : 'border-ink-200 bg-white hover:border-brand-300',
              ].join(' ')}
            >
              <button
                type="button"
                onClick={() => onSelect(id)}
                disabled={disabled}
                className="flex w-full flex-col items-start gap-2 p-4 text-left disabled:opacity-60"
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                      <Icon size={15} />
                    </div>
                    <span className="truncate text-sm font-semibold text-ink-900">
                      {info.label}
                    </span>
                  </div>
                  {isRec && (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-300">
                      <Star size={10} /> Best for your data
                    </span>
                  )}
                </div>

                <p className="text-[11px] font-medium text-ink-500">
                  {info.tagline}
                </p>
                <p className="text-xs leading-snug text-ink-600">
                  {info.oneLiner}
                </p>

                <p className="text-[11px] text-ink-500">
                  <span className="font-semibold text-ink-700">Best for: </span>
                  {info.bestFor}
                </p>
              </button>

              <button
                type="button"
                onClick={() => setOpenId(open ? null : id)}
                className="flex w-full items-center justify-between border-t border-ink-100 px-4 py-2 text-[11px] font-medium text-brand-700 hover:bg-ink-50"
              >
                {open ? 'Hide details' : 'How it works · strengths · trade-offs'}
                <ChevronDown
                  size={13}
                  className={open ? 'rotate-180 transition-transform' : 'transition-transform'}
                />
              </button>
              {open && <Details info={info} />}
            </div>
          )
        })}
      </div>

    </div>
  )
}