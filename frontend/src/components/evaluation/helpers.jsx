// src/components/evaluation/helpers.jsx
import { BarChart3, ShieldCheck, TrendingUp, GitBranch } from 'lucide-react'

// ── Category metadata ─────────────────────────────────────────

export const CATEGORY_META = {
  statistical_similarity: {
    label: 'Statistical Similarity',
    icon: BarChart3,
    accent: 'brand',
    description: 'Distributional similarity between real and synthetic columns.',
  },
  data_quality: {
    label: 'Correlation & Covariance',
    icon: ShieldCheck,
    accent: 'emerald',
    description: 'Whether column-to-column dependencies are preserved in the synthetic data.',
  },
  ml_utility: {
    label: 'ML Utility',
    icon: TrendingUp,
    accent: 'amber',
    description: 'How useful the synthetic data is for training downstream models.',
  },
  relationship_integrity: {
    label: 'Relationship Integrity',
    icon: GitBranch,
    accent: 'ink',
    description: 'Foreign-key consistency across linked tables.',
  },
}

export const CATEGORY_ORDER = [
  'statistical_similarity',
  'data_quality',
  'ml_utility',
  'relationship_integrity',
]

// ── Score helpers ─────────────────────────────────────────────

export function colorForScore(score) {
  if (score == null) return '#94a3b8'
  if (score >= 80) return '#10b981'
  if (score >= 50) return '#f59e0b'
  return '#ef4444'
}

export function toneForScore(score) {
  if (score == null) return 'ink'
  if (score >= 80) return 'emerald'
  if (score >= 50) return 'amber'
  return 'rose'
}

export function formatMetricValue(v) {
  if (v == null) return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v)
    return v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
  }
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  return String(v)
}

export function prettifyMetricKey(k) {
  return String(k)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/**
 * Extract top-N column pairs where the synthetic correlation drifted
 * furthest from the real correlation.
 */
export function topDivergingPairs(realMatrix, synthMatrix, topN = 5) {
  if (!realMatrix || !synthMatrix) return []
  const keys = Object.keys(realMatrix)
  const out = []
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const a = keys[i]
      const b = keys[j]
      const rv = realMatrix[a]?.[b]
      const sv = synthMatrix[a]?.[b]
      if (typeof rv !== 'number' || typeof sv !== 'number') continue
      out.push({ a, b, real: rv, synth: sv, diff: Math.abs(rv - sv) })
    }
  }
  out.sort((x, y) => y.diff - x.diff)
  return out.slice(0, topN)
}

// ── Small shared cards ────────────────────────────────────────

export function CategoryScoreCard({ categoryKey, section, active, onClick }) {
  const meta = CATEGORY_META[categoryKey]
  const Icon = meta?.icon || BarChart3
  const score = section?.score

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'group flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition',
        active
          ? 'border-brand-400 bg-brand-50/40 ring-2 ring-brand-500/20'
          : 'border-ink-200 bg-white hover:border-brand-300 hover:bg-ink-50/40',
      ].join(' ')}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={[
              'grid h-8 w-8 shrink-0 place-items-center rounded-lg',
              section ? 'bg-brand-50 text-brand-600' : 'bg-ink-100 text-ink-400',
            ].join(' ')}
          >
            <Icon size={14} />
          </div>
          <span className="truncate text-xs font-semibold text-ink-900">
            {meta?.label || categoryKey}
          </span>
        </div>
        {section ? (
          <span
            className="shrink-0 text-sm font-semibold tabular-nums"
            style={{ color: colorForScore(score) }}
          >
            {score != null ? score.toFixed(2) : '—'}
          </span>
        ) : (
          <span className="shrink-0 text-[10px] font-medium text-ink-400">n/a</span>
        )}
      </div>
      <p className="text-[11px] leading-snug text-ink-500">{meta?.description}</p>
    </button>
  )
}

export function NotReturnedCard({ categoryKey }) {
  const meta = CATEGORY_META[categoryKey]
  const Icon = meta?.icon || BarChart3
  return (
    <div className="dx-card flex flex-col items-start gap-2 p-5">
      <div className="flex items-center gap-2 text-ink-400">
        <Icon size={16} />
        <span className="text-xs font-semibold uppercase tracking-wider">
          {meta?.label || categoryKey}
        </span>
      </div>
      <p className="text-xs text-ink-500">
        This metric category has not been returned by the backend yet. No
        placeholder values are shown.
      </p>
    </div>
  )
}