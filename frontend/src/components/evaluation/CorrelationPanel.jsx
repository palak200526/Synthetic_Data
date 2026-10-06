// src/components/evaluation/CorrelationPanel.jsx
import MetricExplainer from '../MetricExplainer.jsx'
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
      ? 'The synthetic data preserves the relationships between numerical columns very well. Downstream models should behave similarly on both datasets.'
      : overall >= 50
      ? 'Relationships between numerical columns are partially preserved. Some dependencies have been weakened — see the drifted pairs below.'
      : 'Relationships between numerical columns are largely broken. Models trained on this synthetic data may not transfer to the real data.'

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
          <p className="mt-1 text-sm leading-relaxed text-ink-600">
            Correlation and covariance describe <em>how columns move together</em>.
            If <code className="font-mono text-xs">age</code> and{' '}
            <code className="font-mono text-xs">income</code> are positively correlated
            in the real data, this metric checks whether the synthetic data preserves
            that relationship. A high score means the synthetic data has learned the
            same internal dependencies — a low score means columns move independently
            in the synthetic data even though they don't in the real data.
          </p>
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
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Correlation similarity</span>
              <p className="mt-1 text-xl font-bold text-ink-900">
                {corrSim != null ? `${corrSim.toFixed(2)}%` : '—'}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Covariance similarity</span>
              <p className="mt-1 text-xl font-bold text-ink-900">
                {covSim != null ? `${covSim.toFixed(2)}%` : '—'}
              </p>
            </div>
          </div>
        )}

        <div className={['rounded-lg border p-4 text-xs leading-relaxed', bannerTone].join(' ')}>
          <strong>Interpretation: </strong>
          {bannerText}
        </div>

        {status === 'not_applicable' && raw.reason && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            {raw.reason}
          </p>
        )}

        {diverging.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Pairs with the largest drift
            </h3>
            <div className="overflow-hidden rounded-lg border border-ink-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-200 bg-ink-50/60">
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-500">Column pair</th>
                    <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">Real</th>
                    <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">Synthetic</th>
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
              Numerical columns evaluated ({numericalColumns.length})
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

        <MetricExplainer
          title="How the correlation score is calculated"
          intro="Two sub-scores are computed and averaged. Each measures a different facet of how column relationships are preserved."
          formula={
            'correlation_similarity = (1 - mean(|R_real - R_synth|) / 2) * 100\n' +
            'covariance_similarity  = (1 - mean(normalized |C_real - C_synth|)) * 100\n' +
            'overall_score = mean(correlation_similarity, covariance_similarity)'
          }
          steps={[
            'Extract all eligible numerical columns from both datasets.',
            'Compute the real correlation matrix R_real and the synthetic correlation matrix R_synth.',
            'Compute the real and synthetic covariance matrices the same way.',
            'For every pair of columns, take the absolute difference between real and synthetic values.',
            'Average the differences, scale them to [0, 1], and convert to a percentage similarity.',
            'Final score is the mean of the correlation and covariance sub-scores.',
          ]}
          interpretation={[
            { range: '≥ 80%', label: 'Excellent — column dependencies preserved', tone: 'emerald' },
            { range: '50–79%', label: 'Partial preservation — some pairs drift', tone: 'amber' },
            { range: '< 50%',  label: 'Poor preservation — dependencies broken', tone: 'rose' },
          ]}
          references={['Pearson correlation', 'Covariance matrix']}
        />
      </div>
    </div>
  )
}