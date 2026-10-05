import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Loader2,
  BarChart3,
  ShieldCheck,
  TrendingUp,
  Lock,
  GitBranch,
  RefreshCw,
  Info,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  Database,
  Layers,
  PlayCircle,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  Legend,
  LineChart,
  Line,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import DataTable from '../components/DataTable.jsx'
import ErrorState from '../components/ErrorState.jsx'
import EmptyState from '../components/EmptyState.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import Toast from '../components/Toast.jsx'

import { dashboardApi } from '../api/dashboardApi.js'
import {
  evaluationApi,
  extractCategorySections,
  normalizeEvaluation,
} from '../api/evaluationApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber } from '../utils/format.js'

// ── helpers ─────────────────────────────────────────────────────

const CATEGORY_META = {
  statistical_similarity: {
    label: 'Statistical Similarity',
    icon: BarChart3,
    accent: 'brand',
    description:
      'Distributional similarity between real and synthetic columns.',
  },
  data_quality: {
    label: 'Correlation / Quality',
    icon: ShieldCheck,
    accent: 'emerald',
    description:
      'Numerical feature correlation, covariance preservation, and quality.',
  },
  ml_utility: {
    label: 'ML Utility',
    icon: TrendingUp,
    accent: 'amber',
    description:
      'How well models trained on one split perform on the other.',
  },
  privacy: {
    label: 'Privacy',
    icon: Lock,
    accent: 'rose',
    description:
      'Duplicate and exact-match checks plus privacy risk indicators.',
  },
  relationship_integrity: {
    label: 'Relationship Integrity',
    icon: GitBranch,
    accent: 'ink',
    description:
      'Foreign-key consistency and preservation of relationships.',
  },
}

const CATEGORY_ORDER = [
  'statistical_similarity',
  'data_quality',
  'ml_utility',
  'privacy',
  'relationship_integrity',
]

function colorForScore(score) {
  if (score == null) return '#94a3b8'
  if (score >= 80) return '#10b981'
  if (score >= 50) return '#f59e0b'
  return '#ef4444'
}

function toneForScore(score) {
  if (score == null) return 'ink'
  if (score >= 80) return 'emerald'
  if (score >= 50) return 'amber'
  return 'rose'
}

function formatMetricValue(v) {
  if (v == null) return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v)
    const s = v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
    return s
  }
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  return String(v)
}

function prettifyMetricKey(k) {
  return String(k)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ── subcomponents ───────────────────────────────────────────────

function CategoryScoreCard({ categoryKey, section, active, onClick }) {
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
              section
                ? 'bg-brand-50 text-brand-600'
                : 'bg-ink-100 text-ink-400',
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
          <span className="shrink-0 text-[10px] font-medium text-ink-400">
            n/a
          </span>
        )}
      </div>
      <p className="text-[11px] leading-snug text-ink-500">
        {meta?.description}
      </p>
    </button>
  )
}

function NotReturnedCard({ categoryKey }) {
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

function ColumnScoreChart({ columns, overallScore }) {
  const data = columns
    .filter((c) => c.score != null)
    .map((c) => ({ name: c.name, score: c.score }))

  if (data.length === 0) return null

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            horizontal={false}
            stroke="#e2e8f0"
          />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: '#64748b' }}
            stroke="#cbd5e1"
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11, fill: '#334155' }}
            stroke="#cbd5e1"
            width={150}
          />
          <Tooltip
            formatter={(v) => [
              typeof v === 'number' ? v.toFixed(2) : v,
              'Score',
            ]}
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: '1px solid #e2e8f0',
            }}
          />
          <Bar dataKey="score" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={colorForScore(entry.score)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function CategoryMetricsChart({ section }) {
  // Radar of the extra metrics, if numeric
  const numeric = (section.extraMetrics || []).filter(
    (m) => typeof m.value === 'number',
  )
  if (numeric.length < 3) return null

  const data = numeric.map((m) => ({
    metric: prettifyMetricKey(m.label),
    value: Math.abs(m.value),
  }))

  const maxVal = Math.max(...data.map((d) => d.value), 1)

  return (
    <div style={{ width: '100%', height: 260 }}>
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fontSize: 10, fill: '#475569' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, maxVal]}
            tick={{ fontSize: 9, fill: '#94a3b8' }}
            stroke="#cbd5e1"
          />
          <Radar
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.35}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: '1px solid #e2e8f0',
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

function SectionPanel({ categoryKey, section }) {
  const meta = CATEGORY_META[categoryKey]

  if (!section) {
    return <NotReturnedCard categoryKey={categoryKey} />
  }

  const hasColumnMetrics = section.columns.some(
    (c) => c.score != null || Object.keys(c.metrics).length > 0,
  )

  return (
    <div className="dx-card overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-50 text-brand-600">
            {(() => {
              const Icon = meta?.icon || BarChart3
              return <Icon size={16} />
            })()}
          </div>
          <div>
            <p className="text-sm font-semibold text-ink-900">
              {meta?.label || categoryKey}
            </p>
            <p className="mt-0.5 text-[11px] text-ink-500">
              {meta?.description}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {section.evaluatedColumns != null && (
            <span className="text-[11px] text-ink-500">
              {formatNumber(section.evaluatedColumns)} evaluated
              {section.totalCommonColumns != null &&
                ` · ${formatNumber(section.totalCommonColumns)} common`}
            </span>
          )}
          {section.score != null && (
            <span
              className="rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums text-white"
              style={{ backgroundColor: colorForScore(section.score) }}
            >
              {section.score.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Extra metrics strip */}
      {section.extraMetrics && section.extraMetrics.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-ink-100 px-5 py-3">
          {section.extraMetrics.map((m) => (
            <span
              key={m.label}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink-50 px-2.5 py-1 text-[11px] ring-1 ring-inset ring-ink-200"
            >
              <span className="text-ink-500">
                {prettifyMetricKey(m.label)}
              </span>
              <span className="font-medium text-ink-800 tabular-nums">
                {formatMetricValue(m.value)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Not Applicable notice */}
      {(section.raw?.status === 'not_applicable' ||
        section.status === 'not_applicable') && (
        <div className="border-b border-ink-100 bg-amber-50/60 px-5 py-3 text-xs text-amber-900">
          <span className="font-semibold">Status: Not Applicable</span> —{' '}
          {section.raw?.reason ||
            section.reason ||
            'This metric is not applicable for this dataset.'}
        </div>
      )}

      {/* ML Utility Detail Panel */}
      {categoryKey === 'ml_utility' && section.raw?.task_type && (
        <div className="border-b border-ink-100 px-5 py-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-lg bg-ink-50 p-2.5">
              <span className="text-[10px] text-ink-500 uppercase tracking-wider font-semibold">Task Type</span>
              <p className="mt-0.5 text-xs font-semibold capitalize text-ink-900">{section.raw.task_type}</p>
            </div>
            <div className="rounded-lg bg-ink-50 p-2.5">
              <span className="text-[10px] text-ink-500 uppercase tracking-wider font-semibold">Target Column</span>
              <p className="mt-0.5 text-xs font-semibold text-ink-900 font-mono">{section.raw.target_column || '—'}</p>
            </div>
            <div className="rounded-lg bg-ink-50 p-2.5">
              <span className="text-[10px] text-ink-500 uppercase tracking-wider font-semibold">Model</span>
              <p className="mt-0.5 text-xs font-semibold text-ink-900">{section.raw.model_type || 'RandomForest'}</p>
            </div>
            <div className="rounded-lg bg-ink-50 p-2.5">
              <span className="text-[10px] text-ink-500 uppercase tracking-wider font-semibold">Utility Score</span>
              <p className="mt-0.5 text-xs font-bold text-emerald-600">
                {section.raw.utility_score != null ? `${section.raw.utility_score.toFixed(2)}` : '—'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Charts + table */}
      {hasColumnMetrics ? (
        <div className="px-5 py-5 space-y-6">
          <div>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Per-column scores
            </h3>
            <ColumnScoreChart
              columns={section.columns}
              overallScore={section.score}
            />
          </div>

          {section.columns.length > 0 && (
            <div>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
                Metrics by column
              </h3>
              <DataTable
                data={section.columns}
                getRowKey={(r) => r.name}
                columns={[
                  {
                    key: 'name',
                    header: 'Column',
                    render: (r) => (
                      <span className="font-medium text-ink-900">{r.name}</span>
                    ),
                  },
                  {
                    key: 'columnType',
                    header: 'Type',
                    render: (r) =>
                      r.columnType ? (
                        <span className="inline-flex items-center rounded-md bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-700">
                          {r.columnType}
                        </span>
                      ) : (
                        <span className="text-[11px] text-ink-400">—</span>
                      ),
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    render: (r) => {
                      if (r.status === 'excluded') {
                        return (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-600 border border-slate-200">
                            Excluded
                          </span>
                        )
                      }
                      return r.status ? (
                        <StatusBadge
                          status={r.status}
                          variant={
                            r.status === 'evaluated' ? 'success' : 'neutral'
                          }
                        />
                      ) : (
                        <span className="text-[11px] text-ink-400">—</span>
                      )
                    },
                  },
                  {
                    key: 'metrics',
                    header: 'Metrics',
                    render: (r) => {
                      if (r.status === 'excluded') {
                        const reasonStr =
                          r.reason || r.raw?.reason || 'Excluded column'
                        return (
                          <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                            Reason: {prettifyMetricKey(reasonStr)}
                          </span>
                        )
                      }
                      const entries = Object.entries(r.metrics || {})
                      if (entries.length === 0) {
                        return (
                          <span className="text-[11px] text-ink-400">—</span>
                        )
                      }
                      return (
                        <div className="flex flex-wrap gap-1.5">
                          {entries.map(([k, v]) => (
                            <span
                              key={k}
                              className="inline-flex items-center gap-1 rounded-md bg-ink-50 px-2 py-0.5 font-mono text-[11px] text-ink-700 ring-1 ring-inset ring-ink-200"
                              title={prettifyMetricKey(k)}
                            >
                              <span className="text-ink-400">
                                {prettifyMetricKey(k)}:
                              </span>
                              <span>{formatMetricValue(v)}</span>
                            </span>
                          ))}
                        </div>
                      )
                    },
                  },
                  {
                    key: 'score',
                    header: 'Score',
                    width: '180px',
                    render: (r) => {
                      if (r.status === 'excluded' || r.score == null) {
                        return (
                          <span className="text-xs font-mono text-ink-400">—</span>
                        )
                      }
                      const pct = Math.max(0, Math.min(100, r.score))
                      return (
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-ink-100">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: colorForScore(r.score),
                              }}
                            />
                          </div>
                          <span className="text-xs font-medium text-ink-800 tabular-nums">
                            {r.score.toFixed(2)}
                          </span>
                        </div>
                      )
                    },
                  },
                ]}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="px-5 py-6">
          <div className="rounded-lg border border-dashed border-ink-200 bg-ink-50/60 px-4 py-5 text-xs text-ink-500">
            The backend returned this category but no per-column detail.
          </div>
        </div>
      )}
    </div>
  )
}

function HistoryTable({ rows }) {
  if (!rows || rows.length === 0) return null

  return (
    <DataTable
      data={rows}
      getRowKey={(r, i) =>
        r?.result_id ?? r?.resultId ?? r?.id ?? i
      }
      columns={[
        {
          key: 'result',
          header: 'Result',
          render: (r) =>
            r?.result_id != null || r?.resultId != null ? (
              <span className="font-mono text-xs text-ink-700">
                #{r.result_id ?? r.resultId}
              </span>
            ) : (
              '—'
            ),
        },
        {
          key: 'dataset',
          header: 'Dataset',
          render: (r) => r?.dataset_name || r?.name || r?.dataset_id || '—',
        },
        {
          key: 'score',
          header: 'Overall',
          render: (r) => {
            const s =
              r?.overall_score ?? r?.score ?? r?.average_score ?? null
            if (s == null) return '—'
            return (
              <span
                className="font-medium tabular-nums"
                style={{ color: colorForScore(s) }}
              >
                {Number(s).toFixed(2)}
              </span>
            )
          },
        },
        {
          key: 'created_at',
          header: 'Created',
          render: (r) =>
            r?.created_at
              ? new Date(r.created_at).toLocaleString()
              : '—',
        },
      ]}
    />
  )
}

// ── main page ───────────────────────────────────────────────────

export default function EvaluationDashboard() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const resultIdParam = searchParams.get('result_id')

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeCategory, setActiveCategory] = useState(
    'statistical_similarity',
  )
  const [toast, setToast] = useState(null)

  const autoRanRef = useRef(false)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await dashboardApi.get()
      setData(res.data)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async () => {
    if (!resultIdParam) return
    setLoading(true)
    setError('')
    try {
      const res = await evaluationApi.run(resultIdParam)
      setData(res.data)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [resultIdParam])

  useEffect(() => {
    if (autoRanRef.current) return
    autoRanRef.current = true
    if (resultIdParam) loadDetail()
    else loadDashboard()
  }, [resultIdParam, loadDashboard, loadDetail])

  const reload = () => {
    if (resultIdParam) loadDetail()
    else loadDashboard()
  }

  // Extract category sections from whatever raw payload we have
  const categories = useMemo(
    () => extractCategorySections(data || {}),
    [data],
  )

  // Aggregate stats & history — only if /dashboard returned them
  const dashboardNormalized = useMemo(() => {
    if (!data || resultIdParam) return null
    const d = data.data && typeof data.data === 'object' ? data.data : data
    const num = (...keys) => {
      for (const k of keys) {
        if (typeof d[k] === 'number') return d[k]
      }
      return null
    }
    const arr = (...keys) => {
      for (const k of keys) {
        if (Array.isArray(d[k])) return d[k]
      }
      return []
    }
    return {
      stats: {
        evaluations: num(
          'total_evaluations',
          'evaluations_count',
          'evaluation_count',
        ),
        datasets: num(
          'total_datasets',
          'datasets_count',
          'dataset_count',
        ),
        generations: num(
          'total_generations',
          'generations_count',
          'generation_count',
        ),
        averageScore: num('average_score', 'avg_score'),
      },
      history: arr(
        'evaluations',
        'recent_evaluations',
        'history',
        'runs',
      ),
    }
  }, [data, resultIdParam])

  // Overall score display
  const overallScore = useMemo(() => {
    if (dashboardNormalized?.stats?.averageScore != null) {
      return dashboardNormalized.stats.averageScore
    }
    for (const key of CATEGORY_ORDER) {
      if (categories[key]?.score != null) return categories[key].score
    }
    return null
  }, [categories, dashboardNormalized])

  // Is there anything to show?
  const anyCategory = CATEGORY_ORDER.some((k) => categories[k])
  const isEmpty = !loading && !error && !anyCategory

  const activeSection = categories[activeCategory]

  return (
    <>
      <Toast
        open={!!toast}
        type={toast?.type || 'success'}
        title={toast?.title}
        message={toast?.message}
        onClose={() => setToast(null)}
      />

      <PageHeader
        title="Evaluation Dashboard"
        subtitle="Synthetic-data quality assessment across statistical, utility, privacy, and integrity metrics."
        breadcrumb={
          resultIdParam ? (
            <Link
              to="/evaluations"
              className="inline-flex items-center gap-1 hover:text-ink-700"
            >
              <ArrowLeft size={12} /> All evaluations
            </Link>
          ) : null
        }
        actions={
          <>
            <button
              type="button"
              className="dx-btn-outline"
              onClick={reload}
              disabled={loading}
            >
              <RefreshCw
                size={14}
                className={loading ? 'animate-spin' : ''}
              />
              Refresh
            </button>
            <button
              type="button"
              className="dx-btn-primary"
              onClick={() => navigate('/reports')}
            >
              View report <ArrowRight size={12} />
            </button>
          </>
        }
      />

      {resultIdParam && (
        <div className="mb-5 rounded-lg border border-ink-200 bg-ink-50/60 px-4 py-3 text-xs text-ink-600">
          Detailed view for{' '}
          <span className="font-medium text-ink-800">
            result #{resultIdParam}
          </span>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading && !error && (
        <div className="dx-card">
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-ink-500">
            <Loader2 size={16} className="animate-spin" />
            {resultIdParam
              ? 'Loading evaluation…'
              : 'Loading dashboard…'}
          </div>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* ── Stats strip ─────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={BarChart3}
              label="Overall score"
              value={
                overallScore != null ? overallScore.toFixed(2) : null
              }
              hint={
                dashboardNormalized?.stats?.averageScore != null
                  ? 'Average across evaluations'
                  : 'From the loaded evaluation'
              }
              accent={
                overallScore != null ? toneForScore(overallScore) : 'ink'
              }
            />
            <StatCard
              icon={Database}
              label="Datasets"
              value={
                dashboardNormalized?.stats?.datasets != null
                  ? formatNumber(dashboardNormalized.stats.datasets)
                  : null
              }
              accent="brand"
            />
            <StatCard
              icon={Layers}
              label="Generations"
              value={
                dashboardNormalized?.stats?.generations != null
                  ? formatNumber(dashboardNormalized.stats.generations)
                  : null
              }
              accent="ink"
            />
            <StatCard
              icon={ShieldCheck}
              label="Evaluations"
              value={
                dashboardNormalized?.stats?.evaluations != null
                  ? formatNumber(dashboardNormalized.stats.evaluations)
                  : null
              }
              accent="emerald"
            />
          </div>

          {/* ── Category strip ──────────────────────────────── */}
          <div className="mt-6">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">
              Metric categories
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {CATEGORY_ORDER.map((key) => (
                <CategoryScoreCard
                  key={key}
                  categoryKey={key}
                  section={categories[key]}
                  active={activeCategory === key}
                  onClick={() => setActiveCategory(key)}
                />
              ))}
            </div>
          </div>

          {/* ── Active category panel ───────────────────────── */}
          <div className="mt-6">
            <SectionPanel
              categoryKey={activeCategory}
              section={activeSection}
            />
          </div>

          {/* ── History table ───────────────────────────────── */}
          {dashboardNormalized?.history &&
            dashboardNormalized.history.length > 0 && (
              <div className="mt-8">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-ink-900">
                    Recent evaluations
                  </h2>
                  <span className="text-xs text-ink-500">
                    {dashboardNormalized.history.length} run
                    {dashboardNormalized.history.length === 1 ? '' : 's'}
                  </span>
                </div>
                <HistoryTable rows={dashboardNormalized.history} />
              </div>
            )}

          {/* ── Empty state ─────────────────────────────────── */}
          {isEmpty && (
            <div className="mt-8">
              <EmptyState
                icon={AlertCircle}
                title="No evaluation data yet"
                description={
                  resultIdParam
                    ? 'The backend returned no metrics for this result.'
                    : 'Run a generation, then evaluate it. The dashboard will populate automatically.'
                }
                action={
                  <button
                    className="dx-btn-primary mt-2"
                    onClick={() => navigate('/dashboard')}
                  >
                    <PlayCircle size={14} /> Open datasets
                  </button>
                }
              />
            </div>
          )}

          {/* ── About panel ─────────────────────────────────── */}
          <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2"></div>
            <aside className="space-y-4">
              <div className="dx-card p-5">
                <div className="flex items-center gap-2 text-brand-600">
                  <Info size={16} />
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    About the dashboard
                  </span>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-ink-600">
                  <li>· Metric categories appear only when the backend returns them.</li>
                  <li>
                    · Missing categories are labelled{' '}
                    <span className="font-mono">n/a</span> — no invented values.
                  </li>
                  <li>· Click a category card to view its detailed breakdown.</li>
                  <li>
                    · Deep-link a single evaluation with{' '}
                    <code className="font-mono">?result_id=X</code>.
                  </li>
                </ul>
              </div>
            </aside>
          </div>
        </>
      )}
    </>
  )
}