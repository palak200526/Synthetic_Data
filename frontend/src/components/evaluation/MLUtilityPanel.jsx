// src/components/evaluation/MLUtilityPanel.jsx
import MetricExplainer from '../MetricExplainer.jsx'
import { CATEGORY_META, colorForScore } from './helpers.jsx'

export default function MLUtilityPanel({ section }) {
  const meta = CATEGORY_META.ml_utility
  const Icon = meta.icon
  const raw = section.raw || {}
  const status = raw.status || 'not_applicable'
  const synth = raw.synthetic_metrics || {}
  const base = raw.baseline_metrics || {}
  const isClf = raw.task_type === 'classification'
  const metricKeys = isClf
    ? ['accuracy', 'precision', 'recall', 'f1']
    : ['mae', 'rmse', 'r2']
  const featureColumns = Array.isArray(raw.feature_columns) ? raw.feature_columns : []

  const formatDelta = (k, b, s) => {
    if (b == null || s == null) return null
    const d = s - b
    let tone
    if (isClf) {
      if (d >= -0.05) tone = 'text-emerald-600'
      else if (d >= -0.15) tone = 'text-amber-600'
      else tone = 'text-rose-600'
    } else if (k === 'r2') {
      tone = d >= -0.05 ? 'text-emerald-600' : d >= -0.2 ? 'text-amber-600' : 'text-rose-600'
    } else {
      const rel = Math.abs(b) > 0 ? Math.abs(d) / Math.abs(b) : 0
      tone = rel <= 0.1 ? 'text-emerald-600' : rel <= 0.25 ? 'text-amber-600' : 'text-rose-600'
    }
    return { d, tone }
  }

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

      <div className="px-5 py-5 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-ink-900">What this measures</h3>
          <p className="mt-1 text-sm leading-relaxed text-ink-600">
            This evaluates whether the synthetic data is <em>useful for training models</em>.
            We train a model on the synthetic data and test it on the real data. If
            the synthetic data has captured the underlying patterns, the model will
            perform almost as well as one trained on real data.
          </p>
        </div>

        {status === 'evaluated' && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Task</span>
              <p className="mt-1 text-sm font-semibold capitalize text-ink-900">
                {raw.task_type || 'N/A'}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Target</span>
              <p className="mt-1 text-sm font-semibold text-ink-900 font-mono truncate">
                {raw.target_column || '—'}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Model</span>
              <p className="mt-1 text-sm font-semibold text-ink-900">
                {raw.model_type || 'RandomForest'}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-4">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Utility score</span>
              <p className="mt-1 text-xl font-bold" style={{ color: colorForScore(raw.utility_score) }}>
                {raw.utility_score != null ? `${raw.utility_score.toFixed(2)}%` : '—'}
              </p>
            </div>
          </div>
        )}

        {status === 'not_applicable' && raw.reason && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            {raw.reason}
          </p>
        )}

        {Object.keys(base).length > 0 && Object.keys(synth).length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Baseline vs synthetic-trained model
            </h3>
            <div className="overflow-hidden rounded-lg border border-ink-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-200 bg-ink-50/60">
                    <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-500">Metric</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">Real → Real</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">Synthetic → Real</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {metricKeys.map((k) => {
                    const b = base[k]
                    const s = synth[k]
                    if (b == null && s == null) return null
                    const delta = formatDelta(k, b, s)
                    return (
                      <tr key={k} className="border-b border-ink-100 last:border-b-0">
                        <td className="px-4 py-2.5 text-xs font-medium text-ink-700 uppercase">{k}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs text-ink-800">
                          {typeof b === 'number' ? b.toFixed(4) : '—'}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs text-ink-800">
                          {typeof s === 'number' ? s.toFixed(4) : '—'}
                        </td>
                        <td className={['px-4 py-2.5 text-right font-mono text-xs', delta ? delta.tone : 'text-ink-400'].join(' ')}>
                          {delta ? `${delta.d > 0 ? '+' : ''}${delta.d.toFixed(4)}` : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {featureColumns.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Feature columns ({featureColumns.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {featureColumns.map((c) => (
                <span key={c} className="rounded-md bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-700">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        <MetricExplainer
          title="How the ML utility score is calculated"
          intro="We run a 'synthetic-train / real-test' experiment. The score reflects how much predictive power is lost when you replace real training data with synthetic data."
          formula={
            isClf
              ? 'utility_score = (F1_synth_model / F1_baseline_model) * 100'
              : 'utility_score = (1 - |RMSE_synth - RMSE_baseline| / RMSE_baseline) * 100'
          }
          steps={
            isClf
              ? [
                  'Identify a target column (low-cardinality categorical, or numeric with many unique values).',
                  'Split the real dataset into Real-Train and Real-Test.',
                  'Train a RandomForest classifier on Real-Train (baseline) and evaluate on Real-Test.',
                  'Train a second RandomForest classifier on the synthetic data and evaluate on the same Real-Test.',
                  'Compute the ratio of synthetic F1 to baseline F1, capped at 100%.',
                ]
              : [
                  'Identify a continuous target column with variance.',
                  'Split the real dataset into Real-Train and Real-Test.',
                  'Train a RandomForest regressor on Real-Train (baseline) and evaluate RMSE on Real-Test.',
                  'Train a second RandomForest regressor on the synthetic data and evaluate RMSE on the same Real-Test.',
                  'Compute the relative RMSE difference and convert it to a similarity score.',
                ]
          }
          interpretation={[
            { range: '≥ 80%', label: 'Synthetic data is nearly as predictive as real data', tone: 'emerald' },
            { range: '50–79%', label: 'Useful, but some signal is lost', tone: 'amber' },
            { range: '< 50%',  label: 'Not a good substitute for real training data', tone: 'rose' },
          ]}
          references={['Synthetic-Train / Real-Test benchmark']}
        />
      </div>
    </div>
  )
}