// src/components/evaluation/StatisticalPanel.jsx
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts'

import DataTable from '../DataTable.jsx'
import StatusBadge from '../StatusBadge.jsx'
import MetricExplainer from '../MetricExplainer.jsx'
import {
  CATEGORY_META,
  colorForScore,
  formatMetricValue,
  prettifyMetricKey,
} from './helpers.jsx'

function ColumnScoreChart({ columns }) {
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
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#64748b' }} stroke="#cbd5e1" />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#334155' }} stroke="#cbd5e1" width={150} />
          <Tooltip
            formatter={(v) => [typeof v === 'number' ? v.toFixed(2) : v, 'Score']}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
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

export default function StatisticalPanel({ section }) {
  const meta = CATEGORY_META.statistical_similarity
  const Icon = meta.icon
  const hasColumnMetrics = section.columns.some(
    (c) => c.score != null || Object.keys(c.metrics).length > 0,
  )

  return (
    <div className="dx-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-50 text-brand-600">
            <Icon size={16} />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink-900">{meta.label}</p>
            <p className="mt-0.5 text-[11px] text-ink-500">{meta.description}</p>
          </div>
        </div>
        {section.score != null && (
          <span
            className="rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums text-white"
            style={{ backgroundColor: colorForScore(section.score) }}
          >
            {section.score.toFixed(2)}
          </span>
        )}
      </div>

      {section.extraMetrics?.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-ink-100 px-5 py-3">
          {section.extraMetrics.map((m) => (
            <span
              key={m.label}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink-50 px-2.5 py-1 text-[11px] ring-1 ring-inset ring-ink-200"
            >
              <span className="text-ink-500">{prettifyMetricKey(m.label)}</span>
              <span className="font-medium text-ink-800 tabular-nums">
                {formatMetricValue(m.value)}
              </span>
            </span>
          ))}
        </div>
      )}

      <div className="border-b border-ink-100 bg-ink-50/40 px-5 py-4">
        <p className="text-xs leading-relaxed text-ink-600">
          Compares each column's marginal distribution between the real and
          synthetic datasets. Numbers use mean / std / KS; categories use
          Jensen-Shannon distance. Identifiers, dates, and free-form text are
          excluded automatically.
        </p>
      </div>

      {hasColumnMetrics ? (
        <div className="px-5 py-5 space-y-6">
          <div>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Per-column scores
            </h3>
            <ColumnScoreChart columns={section.columns} />
          </div>

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
                  render: (r) => <span className="font-medium text-ink-900">{r.name}</span>,
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
                        variant={r.status === 'evaluated' ? 'success' : 'neutral'}
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
                      const reasonStr = r.reason || r.raw?.reason || 'Excluded column'
                      return (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                          Reason: {prettifyMetricKey(reasonStr)}
                        </span>
                      )
                    }
                    const entries = Object.entries(r.metrics || {})
                    if (entries.length === 0) {
                      return <span className="text-[11px] text-ink-400">—</span>
                    }
                    return (
                      <div className="flex flex-wrap gap-1.5">
                        {entries.map(([k, v]) => (
                          <span
                            key={k}
                            className="inline-flex items-center gap-1 rounded-md bg-ink-50 px-2 py-0.5 font-mono text-[11px] text-ink-700 ring-1 ring-inset ring-ink-200"
                            title={prettifyMetricKey(k)}
                          >
                            <span className="text-ink-400">{prettifyMetricKey(k)}:</span>
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
                      return <span className="text-xs font-mono text-ink-400">—</span>
                    }
                    const pct = Math.max(0, Math.min(100, r.score))
                    return (
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-ink-100">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${pct}%`, backgroundColor: colorForScore(r.score) }}
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

          <MetricExplainer
            title="How the statistical similarity score is calculated"
            intro="Each eligible column is scored on its own, then all evaluated columns are averaged. Excluded columns (identifiers, dates, free-form text) do not affect the score."
            formula={
              'numerical  score = mean(mean_similarity, std_similarity, 1 - KS)\n' +
              'categorical score = 1 - JS_distance\n' +
              'column_score = that value * 100\n' +
              'overall = mean(all evaluated column scores)'
            }
            steps={[
              'Rule out identifiers, datetime columns, and free-form text.',
              'For numeric columns: compare mean, standard deviation, and a Kolmogorov–Smirnov test against the real distribution.',
              'For categorical columns: compute the Jensen-Shannon distance between real and synthetic value frequencies.',
              'Convert each sub-metric into a 0–100 similarity, then average per column.',
              'Average across all evaluated columns to get the overall score.',
            ]}
            interpretation={[
              { range: '≥ 80%', label: 'Synthetic columns match real distributions well', tone: 'emerald' },
              { range: '50–79%', label: 'Some distributional drift — check the low-scoring columns', tone: 'amber' },
              { range: '< 50%',  label: 'Distributions diverge significantly', tone: 'rose' },
            ]}
            references={['Kolmogorov–Smirnov statistic', 'Jensen-Shannon divergence']}
          />
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