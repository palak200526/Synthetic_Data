// src/components/evaluation/CorrelationPanel.jsx
import MetricExplainer from '../MetricExplainer.jsx'
import { CORRELATION_DOC, CATEGORICAL_ASSOCIATION_DOC } from './metricDocs.js'
import {
  CATEGORY_META,
  colorForScore,
  topDivergingPairs,
} from './helpers.jsx'

export default function CorrelationPanel({ section }) {
  const meta = CATEGORY_META.data_quality
  const Icon = meta.icon
  const raw = section.raw || {}

  const status = raw.status || 'not_applicable'
  const overall = section.score ?? raw.overall_score
  // Datasets with < 2 numeric columns are scored with Cramér's V on
  // category columns instead of Pearson correlation.
  const isCat = raw.association_type === 'cramers_v'
  const kind = isCat ? 'categorical' : 'numerical'
  const corrSim = raw.correlation_similarity
  const covSim = raw.covariance_similarity
  const numericalColumns = Array.isArray(raw.numerical_columns)
    ? raw.numerical_columns
    : []
  const diverging = topDivergingPairs(
    raw.source_correlation,
    raw.synthetic_correlation,
    5,
  )

  const bannerTone =
    overall == null
      ? 'border-ink-200 bg-ink-50 text-ink-700'
      : overall >= 80
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : overall >= 50
      ? 'border-amber-200 bg-amber-50 text-amber-900'
      : 'border-rose-200 bg-rose-50 text-rose-900'

  const bannerText =
    overall == null
      ? 'This metric is not applicable for this dataset.'
      : overall >= 80
      ? `The synthetic data preserves the relationships between ${kind} columns very well. Downstream models should behave similarly on both datasets.`
      : overall >= 50
      ? `Relationships between ${kind} columns are partially preserved. Some dependencies have been weakened — see the drifted pairs below.`
      : `Relationships between ${kind} columns are largely broken. Models trained on this synthetic data may not transfer to the real data.`

  return (
    <div className="dx-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-50 text-brand-600">
            <Icon size={16} />
          </div>
          <div>
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
              {meta.label}
              {isCat && (
                <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-200">
                  Categorical · Cramér&apos;s V
                </span>
              )}
            </p>
            <p className="mt-0.5 text-[11px] text-ink-500">{meta.description}</p>
          </div>
        </div>
        {overall != null && (
          <span
            className="rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums text-white"
            style={{ backgroundColor: colorForScore(overall) }}
          >
            {overall.toFixed(2)}
          </span>
        )}
      </div>

      <div className="px-5 py-5 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-ink-900">What this measures</h3>
          {isCat ? (
            <p className="mt-1 text-sm leading-relaxed text-ink-600">
              This check looks at <em>how strongly category columns are linked</em>.
              If, in the real data, knowing one column tells you a lot about
              another, the synthetic data should keep that link. A high score
              means the links between columns are preserved. A low score means
              they were lost, or that unrelated columns became tied together.
            </p>
          ) : (
            <p className="mt-1 text-sm leading-relaxed text-ink-600">
              Correlation and covariance describe <em>how columns move together</em>.
              If <code className="font-mono text-xs">study_hours</code> and{' '}
              <code className="font-mono text-xs">marks</code> rise together in the
              real data, this check confirms that the synthetic data keeps that
              link. A high score means the relationships between columns are
              preserved. A low score means they were lost, or that unrelated
              columns became tied together.
            </p>
          )}
        </div>

        {status === 'evaluated' && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Status</span>
              <p className="mt-1 text-sm font-semibold capitalize text-ink-900">
                {status.replace('_', ' ')}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Overall</span>
              <p className="mt-1 text-xl font-bold" style={{ color: colorForScore(overall) }}>
                {overall != null ? `${overall.toFixed(2)}%` : '—'}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">{isCat ? 'Association similarity (Cramér\'s V)' : 'Correlation similarity'}</span>
              <p className="mt-1 text-xl font-bold text-ink-900">
                {corrSim != null ? `${corrSim.toFixed(2)}%` : '—'}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Covariance similarity</span>
              <p className="mt-1 text-xl font-bold text-ink-900">
                {covSim != null ? `${covSim.toFixed(2)}%` : isCat ? 'Not used' : '—'}
              </p>
            </div>
          </div>
        )}

        <div className={['rounded-lg border p-4 text-xs leading-relaxed', bannerTone].join(' ')}>
          <strong>Interpretation: </strong>
          {bannerText}
        </div>

        {isCat ? (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 text-xs leading-relaxed text-indigo-900">
            <p className="font-semibold">
              Method used: Cramér&apos;s V (association), not Pearson correlation
            </p>
            <p className="mt-1">
              This dataset has fewer than 2 numeric columns, and Pearson
              correlation only works on numbers. For category columns, Cramér&apos;s V
              measures how strongly two columns are linked, from 0 (no link) to
              1 (one column fully decides the other). The score compares V in the
              real data with V in the synthetic data. Covariance is not
              calculated for category columns.
            </p>
            <p className="mt-1 text-indigo-800/80">
              On small tables, or columns with many distinct values, V can read 0
              or change a lot, so treat this score as a rough guide.
            </p>
          </div>
        ) : (
          raw.note && (
            <p className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-xs text-sky-800">
              {raw.note}
            </p>
          )
        )}

        {status === 'not_applicable' && raw.reason && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            {raw.reason}
          </p>
        )}

        {diverging.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Pairs with the largest drift{isCat ? ' (Cramér\'s V, 0 to 1)' : ''}
            </h3>
            <div className="overflow-hidden rounded-lg border border-ink-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-200 bg-ink-50/60">
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-500">Column pair</th>
                    <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">{isCat ? 'Real V' : 'Real'}</th>
                    <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">{isCat ? 'Synthetic V' : 'Synthetic'}</th>
                    <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {diverging.map((p, i) => (
                    <tr key={i} className="border-b border-ink-100 last:border-b-0">
                      <td className="px-4 py-2.5 text-xs">
                        <span className="font-mono text-ink-800">{p.a}</span>
                        <span className="mx-1.5 text-ink-400">↔</span>
                        <span className="font-mono text-ink-800">{p.b}</span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs text-ink-700">{p.real.toFixed(3)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs text-ink-700">{p.synth.toFixed(3)}</td>
                      <td
                        className={[
                          'px-4 py-2.5 text-right font-mono text-xs',
                          p.diff <= 0.1 ? 'text-emerald-600'
                            : p.diff <= 0.3 ? 'text-amber-600'
                            : 'text-rose-600',
                        ].join(' ')}
                      >
                        {p.diff.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {numericalColumns.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              {isCat ? 'Categorical' : 'Numerical'} columns evaluated ({numericalColumns.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {numericalColumns.map((c) => (
                <span key={c} className="rounded-md bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-700">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        <MetricExplainer {...(isCat ? CATEGORICAL_ASSOCIATION_DOC : CORRELATION_DOC)} />
      </div>
    </div>
  )
}