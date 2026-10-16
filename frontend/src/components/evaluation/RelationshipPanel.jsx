// src/components/evaluation/RelationshipPanel.jsx
import MetricExplainer from '../MetricExplainer.jsx'
import { RELATIONSHIP_DOC } from './metricDocs.js'
import { CATEGORY_META, colorForScore } from './helpers.jsx'

export default function RelationshipPanel({ section }) {
  const meta = CATEGORY_META.relationship_integrity
  const Icon = meta.icon
  const raw = section.raw || {}
  const refs = Array.isArray(raw.relationships) ? raw.relationships : []

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

      <div className="px-5 py-5 space-y-4">
        <p className="text-xs leading-relaxed text-ink-600">
          Validates that every foreign key in a synthetic child table exists as a
          primary key in the corresponding synthetic parent table. This metric is
          only applicable to multi-table dataset groups.
        </p>

        {raw.status === 'not_applicable' && raw.reason && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            {raw.reason}
          </p>
        )}

        {raw.status === 'evaluated' && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-ink-50 p-3">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Total relationships</span>
              <p className="mt-1 text-base font-semibold text-ink-900">
                {raw.total_relationships ?? refs.length}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-3">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Valid relationships</span>
              <p className="mt-1 text-base font-semibold text-emerald-600">
                {raw.valid_relationships ?? refs.filter((r) => r.valid).length}
              </p>
            </div>
            <div className="rounded-lg bg-ink-50 p-3">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">Integrity score</span>
              <p className="mt-1 text-base font-semibold" style={{ color: colorForScore(section.score) }}>
                {section.score != null ? `${section.score.toFixed(2)}%` : '—'}
              </p>
            </div>
          </div>
        )}

        {refs.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
              Relationship details ({refs.length})
            </h4>
            {refs.map((r, i) => (
              <div
                key={r.relationship_id ?? i}
                className="rounded-lg border border-ink-200 bg-white p-3.5 text-xs shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-ink-900">
                      Table #{r.parent_dataset_id} → Table #{r.child_dataset_id}
                    </span>
                    {r.relationship_type && (
                      <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] font-medium text-ink-600">
                        {r.relationship_type}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {r.referential_integrity_score != null && (
                      <span className="font-mono font-semibold" style={{ color: colorForScore(r.referential_integrity_score) }}>
                        {r.referential_integrity_score.toFixed(2)}%
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        r.valid
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-rose-50 text-rose-700 border border-rose-200'
                      }`}
                    >
                      {r.valid ? 'Valid' : 'Invalid'}
                    </span>
                  </div>
                </div>

                <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-ink-600">
                  <div className="flex items-center gap-1.5 font-mono text-[11px]">
                    <span className="rounded bg-ink-50 px-1.5 py-0.5 text-ink-800">
                      {r.parent_column}
                    </span>
                    <span className="text-ink-400">→</span>
                    <span className="rounded bg-ink-50 px-1.5 py-0.5 text-ink-800">
                      {r.child_column}
                    </span>
                  </div>

                  {r.total_synthetic_child_records != null && (
                    <span className="text-[11px] text-ink-500">
                      <strong className="text-ink-700">{r.valid_synthetic_child_records ?? (r.total_synthetic_child_records - (r.invalid_synthetic_child_records || 0))}</strong> of{' '}
                      <strong className="text-ink-700">{r.total_synthetic_child_records}</strong> child records valid
                    </span>
                  )}
                </div>

                {r.reason && (
                  <p className="mt-2 text-[11px] text-rose-600">
                    {r.reason}
                  </p>
                )}

                {Array.isArray(r.invalid_sample) && r.invalid_sample.length > 0 && (
                  <div className="mt-2 rounded bg-rose-50/70 p-2 text-[11px] text-rose-800">
                    <span className="font-semibold">Invalid FK sample: </span>
                    <span className="font-mono">{r.invalid_sample.join(', ')}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <MetricExplainer {...RELATIONSHIP_DOC} />
      </div>
    </div>
  )
}