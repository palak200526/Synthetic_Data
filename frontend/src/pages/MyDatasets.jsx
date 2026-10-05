import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Database,
  UploadCloud,
  Search,
  ArrowRight,
  Rows3,
  Columns3,
  Layers,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import EmptyState from '../components/EmptyState.jsx'
import StatusBadge from '../components/StatusBadge.jsx'

import { listLocalDatasets } from '../utils/batchStore.js'
import { formatNumber } from '../utils/format.js'

export default function MyDatasets() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  // listLocalDatasets is synchronous and reads from localStorage.
  // It's the only list of datasets we have — there is no server-side
  // GET /datasets endpoint in the current API surface.
  const all = useMemo(() => listLocalDatasets(), [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return all
    return all.filter((d) =>
      (d.name || '').toLowerCase().includes(q),
    )
  }, [all, query])

  const openDataset = (d) => {
    const qs = d.session_id ? `?session=${d.session_id}` : ''
    navigate(`/datasets/${d.id}/profile${qs}`)
  }

  return (
    <>
      <PageHeader
        title="My Datasets"
        subtitle="All datasets you have uploaded in this browser."
        actions={
          <button
            className="dx-btn-primary"
            onClick={() => navigate('/upload')}
          >
            <UploadCloud size={14} /> Upload dataset
          </button>
        }
      />

      {all.length > 0 && (
        <div className="mb-5 flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search datasets…"
              className="dx-input pl-8"
            />
          </div>
          <span className="text-xs text-ink-500">
            {filtered.length} of {all.length}
          </span>
        </div>
      )}

      {all.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No datasets yet"
          description="Upload your first dataset to begin the Datrixa workflow. Datasets are listed here as you add them."
          action={
            <button
              className="dx-btn-primary mt-2"
              onClick={() => navigate('/upload')}
            >
              <UploadCloud size={14} /> Upload dataset
            </button>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No matches"
          description={`Nothing matches "${query}". Try a different term.`}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((d) => {
            const isMulti = d.session_id
            return (
              <button
                key={d.id}
                type="button"
                onClick={() => openDataset(d)}
                className="dx-card group flex w-full flex-col gap-3 p-5 text-left transition hover:border-brand-300 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                      <Database size={16} />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink-900">
                        {d.name || `Dataset ${d.id}`}
                      </p>
                      <p className="mt-0.5 truncate font-mono text-[10px] text-ink-400">
                        ID {d.id}
                        {d.session_id ? ` · session ${d.session_id}` : ''}
                      </p>
                    </div>
                  </div>
                  {isMulti && (
                    <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-ink-100 px-2 py-0.5 text-[10px] font-medium text-ink-600">
                      <Layers size={10} />
                      Batch
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-500">
                  {d.rows != null && (
                    <span className="inline-flex items-center gap-1.5">
                      <Rows3 size={12} /> {formatNumber(d.rows)} rows
                    </span>
                  )}
                  {d.columns != null && (
                    <span className="inline-flex items-center gap-1.5">
                      <Columns3 size={12} /> {d.columns} cols
                    </span>
                  )}
                  {d.created_at && (
                    <span>
                      · {new Date(d.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-end text-xs font-medium text-brand-600 opacity-0 transition group-hover:opacity-100">
                  Open profile <ArrowRight size={12} />
                </div>
              </button>
            )
          })}
        </div>
      )}

      <div className="mt-8 rounded-lg border border-ink-200 bg-ink-50/60 px-4 py-3 text-[11px] text-ink-500">
        <strong className="text-ink-700">Note:</strong> the current backend
        API does not expose a datasets list endpoint. This page reads the
        upload batches you have performed in this browser. Clearing browser
        data will reset this list.
      </div>
    </>
  )
}