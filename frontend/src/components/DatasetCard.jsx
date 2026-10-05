import { Database, Rows3, Columns3, ArrowRight } from 'lucide-react'
import StatusBadge from './StatusBadge.jsx'

export default function DatasetCard({ dataset, onClick }) {
  const name =
    dataset?.name ||
    dataset?.dataset_name ||
    dataset?.filename ||
    'Untitled dataset'

  const rows =
    dataset?.rows ?? dataset?.num_rows ?? dataset?.row_count ?? null
  const cols =
    dataset?.columns ?? dataset?.num_columns ?? dataset?.column_count ?? null
  const created = dataset?.created_at || dataset?.uploaded_at || null
  const status = dataset?.status
  const id = dataset?.id || dataset?.dataset_id

  const fmt = (n) =>
    typeof n === 'number' ? new Intl.NumberFormat().format(n) : null

  return (
    <button
      type="button"
      onClick={onClick}
      className="dx-card group flex w-full flex-col gap-3 p-5 text-left transition hover:border-brand-300 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
            <Database size={16} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-900">{name}</p>
            {id && (
              <p className="mt-0.5 truncate font-mono text-[10px] text-ink-400">
                {id}
              </p>
            )}
          </div>
        </div>
        {status && <StatusBadge status={status} />}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-500">
        {rows != null && (
          <span className="inline-flex items-center gap-1.5">
            <Rows3 size={12} /> {fmt(rows)} rows
          </span>
        )}
        {cols != null && (
          <span className="inline-flex items-center gap-1.5">
            <Columns3 size={12} /> {cols} cols
          </span>
        )}
        {created && (
          <span>· {new Date(created).toLocaleDateString()}</span>
        )}
      </div>

      <div className="flex items-center justify-end text-xs font-medium text-brand-600 opacity-0 transition group-hover:opacity-100">
        Open profile <ArrowRight size={12} />
      </div>
    </button>
  )
}