// src/components/MetricExplainer.jsx
import { useState } from 'react'
import { Calculator, ChevronDown } from 'lucide-react'

/**
 * Collapsible panel that explains how a metric is calculated.
 *
 * Props:
 *   title       — panel header (default: 'How is this calculated?')
 *   intro       — one-line summary of what the metric measures
 *   formula     — optional formula / pseudo-code (rendered monospaced)
 *   steps       — ordered list of how the score is computed
 *   interpretation — array of { range, label, tone } for score ranges
 *   references  — array of source names (papers, docs)
 */
export default function MetricExplainer({
  title = 'How is this calculated?',
  intro,
  formula,
  steps = [],
  interpretation = [],
  references = [],
}) {
  const [open, setOpen] = useState(false)

  const tones = {
    emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber:   'bg-amber-50 text-amber-700 ring-amber-200',
    rose:    'bg-rose-50 text-rose-700 ring-rose-200',
    ink:     'bg-ink-100 text-ink-600 ring-ink-200',
  }

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-ink-200 bg-ink-50/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-ink-700 hover:bg-ink-100/60"
      >
        <span className="inline-flex items-center gap-1.5">
          <Calculator size={12} className="text-brand-600" />
          {title}
        </span>
        <ChevronDown
          size={12}
          className={['text-ink-400 transition-transform', open ? 'rotate-180' : ''].join(' ')}
        />
      </button>

      {open && (
        <div className="space-y-3 border-t border-ink-200 bg-white px-3 py-3 text-xs text-ink-600">
          {intro && <p className="leading-relaxed">{intro}</p>}

          {formula && (
            <div className="overflow-x-auto rounded-md bg-ink-900 px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-100">
              <pre className="whitespace-pre-wrap">{formula}</pre>
            </div>
          )}

          {steps.length > 0 && (
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                Steps
              </p>
              <ol className="list-decimal space-y-1 pl-5">
                {steps.map((s, i) => (
                  <li key={i} className="leading-relaxed">{s}</li>
                ))}
              </ol>
            </div>
          )}

          {interpretation.length > 0 && (
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                How to read the score
              </p>
              <ul className="space-y-1">
                {interpretation.map((row, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span
                      className={[
                        'inline-flex shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset',
                        tones[row.tone] || tones.ink,
                      ].join(' ')}
                    >
                      {row.range}
                    </span>
                    <span className="leading-snug">{row.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {references.length > 0 && (
            <p className="pt-1 text-[11px] text-ink-500">
              <span className="font-semibold text-ink-600">Sources: </span>
              {references.join(' · ')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}