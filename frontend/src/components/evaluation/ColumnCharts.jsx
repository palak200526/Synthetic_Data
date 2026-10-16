// src/components/evaluation/ColumnCharts.jsx
// One vertical per-column chart for the Statistical Similarity section with a
// toggle:  Score  |  Real vs Synthetic (two overlapping lines)
import { useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  LabelList,
} from 'recharts'


// One theme colour (project brand indigo) for every chart:
//   real      = light tint with an outline
//   synthetic = solid brand colour
const BRAND = '#4f46e5' // brand-600
const REAL_FILL = '#a5b4fc' // brand-300
const REAL_STROKE = '#6366f1' // brand-500
const REAL_COLOR = BRAND
const SYNTH_COLOR = BRAND

const METRICS = [
  { key: 'mean', label: 'Mean' },
  { key: 'std', label: 'Std dev' },
  { key: 'min', label: 'Min' },
  { key: 'max', label: 'Max' },
]

const AXIS_TICK = { fontSize: 11, fill: '#334155' }

function fmt(v) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  const abs = Math.abs(v)
  if (abs !== 0 && (abs >= 1e6 || abs < 0.01)) return v.toExponential(2)
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function ScoreChart({ columns }) {
  const data = columns
    .filter((c) => c.score != null)
    .map((c) => ({ name: c.name, score: c.score }))
  if (data.length === 0) return null

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis
            dataKey="name"
            tick={AXIS_TICK}
            stroke="#cbd5e1"
            interval={0}
            angle={-25}
            textAnchor="end"
            height={70}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: '#64748b' }}
            stroke="#cbd5e1"
            width={40}
          />
          <Tooltip
            formatter={(v) => [typeof v === 'number' ? v.toFixed(2) : v, 'Score']}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
          />
          <Bar dataKey="score" fill={BRAND} radius={[4, 4, 0, 0]} maxBarSize={56}>
            <LabelList
              dataKey="score"
              position="top"
              formatter={(v) => (typeof v === 'number' ? v.toFixed(1) : v)}
              style={{ fontSize: 11, fill: '#334155', fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * One chart style for both numeric and categorical comparisons:
 * wide light bar = real, narrow solid bar centered inside it = synthetic.
 * data: [{ name, Real, Synthetic, ...extra }]
 */
function OverlayBars({ data, domain, tickFormatter, tooltipFormatter }) {
  return (
    <div style={{ width: '100%', height: 340 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          {/* Two axes with the same categories let the narrow Synthetic bar
              sit centered INSIDE the wide Real bar (one bar per item). */}
          <XAxis
            xAxisId="real"
            dataKey="name"
            tick={AXIS_TICK}
            stroke="#cbd5e1"
            interval={0}
            angle={-25}
            textAnchor="end"
            height={70}
          />
          <XAxis xAxisId="synthetic" dataKey="name" hide />
          <YAxis
            domain={domain}
            tick={{ fontSize: 11, fill: '#64748b' }}
            stroke="#cbd5e1"
            width={44}
            tickFormatter={tickFormatter}
          />
          <Tooltip
            cursor={{ fill: 'rgba(148,163,184,0.12)' }}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
            formatter={tooltipFormatter}
            itemStyle={{ color: '#1e293b' }}
            labelStyle={{ color: '#0f172a', fontWeight: 600 }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            verticalAlign="top"
            height={28}
            formatter={(value) => (
              <span style={{ color: '#334155', fontWeight: 500 }}>{value}</span>
            )}
          />
          <Bar
            xAxisId="real"
            dataKey="Real"
            fill={REAL_FILL}
            stroke={REAL_STROKE}
            strokeWidth={2}
            radius={[4, 4, 0, 0]}
            barSize={64}
            isAnimationActive={false}
          />
          <Bar
            xAxisId="synthetic"
            dataKey="Synthetic"
            fill={SYNTH_COLOR}
            radius={[4, 4, 0, 0]}
            barSize={28}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function RealVsSyntheticChart({ columns }) {
  const [metric, setMetric] = useState('mean')

  const numeric = useMemo(
    () =>
      columns.filter(
        (c) =>
          c.status === 'evaluated' &&
          c.raw?.source &&
          c.raw?.synthetic &&
          typeof c.raw.source.mean === 'number',
      ),
    [columns],
  )

  const data = useMemo(
    () =>
      numeric.map((c) => {
        const real = Number(c.raw.source[metric])
        const synth = Number(c.raw.synthetic[metric])
        // Columns have very different scales, so each pair is shown as a
        // percentage of the larger of the two values.
        const denom = Math.max(Math.abs(real), Math.abs(synth))
        return {
          name: c.name,
          Real: denom > 0 ? (Math.abs(real) / denom) * 100 : 0,
          Synthetic: denom > 0 ? (Math.abs(synth) / denom) * 100 : 0,
          realValue: real,
          synthValue: synth,
        }
      }),
    [numeric, metric],
  )

  if (numeric.length === 0) return null

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setMetric(m.key)}
              className={[
                'rounded-full px-3 py-1 text-[11px] font-medium ring-1 ring-inset transition',
                metric === m.key
                  ? 'bg-brand-600 text-white ring-brand-600'
                  : 'bg-white text-ink-600 ring-ink-200 hover:bg-ink-50',
              ].join(' ')}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-ink-500">
          Each pair is shown as a % of the larger value, so columns with
          different scales can share one chart. Hover for actual values.
        </p>
      </div>

      <OverlayBars
        data={data}
        domain={[0, 100]}
        tickFormatter={(v) => `${v}%`}
        tooltipFormatter={(v, name, item) => [
          fmt(name === 'Real' ? item.payload.realValue : item.payload.synthValue),
          name,
        ]}
      />
      <p className="mt-1 text-[11px] text-ink-400">
        Light wide bar = real, narrow solid bar = synthetic. The closer the top
        of the solid bar is to the top of the wide bar, the closer the
        synthetic data is to the real data.
      </p>

    </div>
  )
}

function CategoryChart({ columns }) {
  const cats = useMemo(
    () =>
      columns.filter(
        (c) =>
          c.status === 'evaluated' &&
          c.columnType === 'categorical' &&
          Array.isArray(c.raw?.distribution) &&
          c.raw.distribution.length > 0,
      ),
    [columns],
  )
  const [selected, setSelected] = useState('')
  const current = cats.find((c) => c.name === selected) || cats[0]

  if (cats.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-ink-200 bg-ink-50 p-4 text-xs text-ink-500">
        Category proportions are not stored for this evaluation yet. Click
        <strong> Re-evaluate</strong> to generate them.
      </p>
    )
  }

  const data = current.raw.distribution.map((d) => ({
    name: d.category,
    Real: d.real,
    Synthetic: d.synthetic,
  }))

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {cats.map((c) => (
            <button
              key={c.name}
              type="button"
              onClick={() => setSelected(c.name)}
              className={[
                'rounded-full px-3 py-1 text-[11px] font-medium ring-1 ring-inset transition',
                current.name === c.name
                  ? 'bg-brand-600 text-white ring-brand-600'
                  : 'bg-white text-ink-600 ring-ink-200 hover:bg-ink-50',
              ].join(' ')}
            >
              {c.name}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-ink-500">
          Share of rows in each category (top 10). Score for this column:{' '}
          <strong>{current.score != null ? current.score.toFixed(2) : '—'}</strong>
        </p>
      </div>

      <OverlayBars
        data={data}
        tickFormatter={(v) => `${v}%`}
        tooltipFormatter={(v, name) => [`${Number(v).toFixed(2)}%`, name]}
      />
      <p className="mt-1 text-[11px] text-ink-400">
        Light wide bar = real share, narrow solid bar = synthetic share. The
        closer the top of the solid bar is to the top of the wide bar in every
        category, the better the synthetic data keeps this column's category mix.
      </p>
    </div>
  )
}

export default function ColumnCharts({ columns }) {
  const [view, setView] = useState('score')
  const [kind, setKind] = useState('numeric')
  const hasNumeric = columns.some(
    (c) => c.status === 'evaluated' && c.raw?.source && c.raw?.synthetic,
  )
  const hasCategorical = columns.some(
    (c) => c.status === 'evaluated' && c.columnType === 'categorical',
  )
  const showKind = hasNumeric && hasCategorical
  const activeKind = !hasNumeric ? 'categorical' : !hasCategorical ? 'numeric' : kind

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
          {view === 'score' ? 'Per-column similarity score' : 'Real vs synthetic'}
        </h3>
        <div className="inline-flex rounded-lg bg-ink-100 p-0.5">
          {[
            { id: 'score', label: 'Score' },
            { id: 'compare', label: 'Real vs Synthetic', disabled: !hasNumeric && !hasCategorical },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              disabled={t.disabled}
              onClick={() => setView(t.id)}
              className={[
                'rounded-md px-3 py-1 text-xs font-medium transition disabled:opacity-40',
                view === t.id
                  ? 'bg-white text-ink-900 shadow-sm'
                  : 'text-ink-500 hover:text-ink-800',
              ].join(' ')}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {view === 'compare' && showKind && (
        <div className="mb-3 inline-flex rounded-lg bg-ink-100 p-0.5">
          {[
            { id: 'numeric', label: 'Numeric columns' },
            { id: 'categorical', label: 'Categorical columns' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setKind(t.id)}
              className={[
                'rounded-md px-3 py-1 text-xs font-medium transition',
                activeKind === t.id
                  ? 'bg-white text-ink-900 shadow-sm'
                  : 'text-ink-500 hover:text-ink-800',
              ].join(' ')}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {view === 'score' ? (
        <ScoreChart columns={columns} />
      ) : activeKind === 'categorical' ? (
        <CategoryChart columns={columns} />
      ) : (
        <RealVsSyntheticChart columns={columns} />
      )}
    </div>
  )
}