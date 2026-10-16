// src/components/evaluation/MLUtilityPanel.jsx
import MetricExplainer from '../MetricExplainer.jsx'
import { mlUtilityDoc } from './metricDocs.js'
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
    const level = tone.includes('emerald') ? 'good' : tone.includes('amber') ? 'warn' : 'bad'
    return { d, tone, level }
  }

  const LEVELS = {
    good: { label: 'Close', pill: 'bg-emerald-50 text-emerald-700 ring-emerald-200', dot: 'bg-emerald-500' },
    warn: { label: 'Small gap', pill: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
    bad: { label: 'Large gap', pill: 'bg-rose-50 text-rose-700 ring-rose-200', dot: 'bg-rose-500' },
  }

  const legendRules = isClf
    ? { good: 'within 0.05 of real', warn: '0.05 to 0.15 lower', bad: 'more than 0.15 lower' }
    : { good: 'up to 10% off (R²: within 0.05)', warn: 'up to 25% off (R²: up to 0.20)', bad: 'more than that' }

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
            This checks whether the synthetic data is <em>useful for training models</em>.
            A model is trained on the synthetic data and tested on real data it
            has never seen. If the synthetic data captured the real patterns, the
            model performs about as well as one trained on the real data.
          </p>
        </div>

        {status === 'pending_target' && (
          <div className="rounded-lg border border-brand-200 bg-brand-50/50 p-4 text-xs text-brand-900">
            <p className="font-semibold">Target Selection Pending</p>
            <p className="mt-1 text-brand-700">
              Select a target column in the card above and click <strong>Proceed</strong> to run the ML Utility evaluation.
            </p>
          </div>
        )}

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
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            <p>{raw.reason}</p>
            {raw.reason_detail && (
              <p className="mt-2 font-mono text-[11px] text-amber-700/80">
                Technical detail: {raw.reason_detail}
              </p>
            )}
          </div>
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
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500" title="Synthetic → Real minus Real → Real">Gap vs real (Δ)</th>
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
                          {delta ? (
                            <span className="inline-flex items-center justify-end gap-2">
                              {`${delta.d > 0 ? '+' : ''}${delta.d.toFixed(4)}`}
                              <span className={['rounded-full px-2 py-0.5 font-sans text-[10px] font-medium ring-1 ring-inset', LEVELS[delta.level].pill].join(' ')}>
                                {LEVELS[delta.level].label}
                              </span>
                            </span>
                          ) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-2 rounded-lg bg-ink-50/60 px-4 py-3 text-xs text-ink-600">
              <p>
                <span className="font-semibold text-ink-800">How to read the last column: </span>
                it is the synthetic-trained model minus the real-trained model. A minus sign
                means the synthetic data gave a weaker model on that metric.
              </p>
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
                {['good', 'warn', 'bad'].map((lv) => (
                  <span key={lv} className="inline-flex items-center gap-1.5">
                    <span className={['h-2 w-2 rounded-full', LEVELS[lv].dot].join(' ')} />
                    <span className="font-medium text-ink-800">{LEVELS[lv].label}:</span> {legendRules[lv]}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-ink-500">
                A red row marks a big gap on that one metric. It does not mean the evaluation failed.
              </p>
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

        <MetricExplainer {...mlUtilityDoc(isClf)} />
      </div>
    </div>
  )
}