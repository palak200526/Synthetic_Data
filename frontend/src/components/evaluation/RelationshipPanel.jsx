// src/components/evaluation/RelationshipPanel.jsx
import MetricExplainer from '../MetricExplainer.jsx'
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

        {refs.length > 0 && (
          <div className="space-y-2">
            {refs.map((r, i) => (
              <div
                key={r.relationship_id ?? i}
                className="rounded-lg border border-ink-200 bg-ink-50/60 p-3 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-ink-800">
                    #{r.parent_dataset_id} → #{r.child_dataset_id}
                  </span>
                  <span className={r.valid ? 'text-emerald-600' : 'text-rose-600'}>
                    {r.valid ? 'Valid' : 'Invalid'}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-ink-500">
                  <span className="font-mono">{r.parent_column}</span>
                  <span className="mx-1">→</span>
                  <span className="font-mono">{r.child_column}</span>
                  {r.referential_integrity_score != null && (
                    <span className="ml-2">· {r.referential_integrity_score.toFixed(2)}%</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <MetricExplainer
          title="How referential integrity is calculated"
          intro="For each configured relationship, we count how many synthetic child records reference a primary key that exists in the synthetic parent."
          formula="score = (valid_child_records / total_child_records) * 100"
          steps={[
            'Read the list of configured parent-child relationships for the dataset group.',
            'Extract the set of primary keys from the synthetic parent table.',
            'For every synthetic child record, check whether its foreign key is in the parent key set.',
            'Count the valid records and divide by the total.',
            'Average across all relationships to get the overall score.',
          ]}
          interpretation={[
            { range: '100%',  label: 'Every child record references an existing parent', tone: 'emerald' },
            { range: '<100%', label: 'Some child records are orphaned', tone: 'rose' },
          ]}
          references={['Relational foreign-key constraint']}
        />
      </div>
    </div>
  )
}