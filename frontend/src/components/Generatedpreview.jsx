import { useEffect, useState } from 'react'
import { Loader2, Table2 } from 'lucide-react'

import { generationApi } from '../api/generationApi.js'
import { getErrorMessage } from '../utils/errors.js'

const formatCell = (v) => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? String(v) : String(Number(v.toFixed(4)))
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  return String(v)
}

/**
 * Shows the first rows of a generated dataset.
 * targets: [{ resultId, label }]  (one entry for single-table runs,
 * one per table for multi-table runs).
 */
export default function GeneratedPreview({ targets = [] }) {
  const valid = targets.filter((t) => t && t.resultId != null)
  const [activeId, setActiveId] = useState(valid[0]?.resultId ?? null)
  const [limit, setLimit] = useState(10)
  const [state, setState] = useState({ loading: false, error: '', data: null })

  const validKey = valid.map((t) => t.resultId).join(',')

  // Reset the selected table when a new generation result arrives.
  useEffect(() => {
    setActiveId(valid[0]?.resultId ?? null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validKey])

  useEffect(() => {
    if (activeId == null) return undefined
    let cancelled = false
    setState({ loading: true, error: '', data: null })
    generationApi
      .preview(activeId, limit)
      .then((res) => {
        if (!cancelled) setState({ loading: false, error: '', data: res.data })
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ loading: false, error: getErrorMessage(err), data: null })
        }
      })
    return () => {
      cancelled = true
    }
  }, [activeId, limit])

  if (valid.length === 0) return null

  const { loading, error, data } = state
  const columns = data?.columns || []
  const rows = data?.rows || []

  return (
    <div className="mt-5 border-t border-ink-100 pt-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Table2 size={14} className="text-ink-500" />
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
            Sample of generated data
          </p>
        </div>

        <div className="flex items-center gap-2">
          {valid.length > 1 && (
            <select
              className="rounded-md border border-ink-200 bg-white px-2 py-1 text-xs text-ink-700"
              value={activeId ?? ''}
              onChange={(e) => setActiveId(Number(e.target.value))}
              aria-label="Choose generated table"
            >
              {valid.map((t) => (
                <option key={t.resultId} value={t.resultId}>
                  {t.label || `Result ${t.resultId}`}
                </option>
              ))}
            </select>
          )}
          <select
            className="rounded-md border border-ink-200 bg-white px-2 py-1 text-xs text-ink-700"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            aria-label="Number of sample rows"
          >
            {[5, 10, 25, 50].map((n) => (
              <option key={n} value={n}>
                {n} rows
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-2 rounded-lg border border-ink-200 py-8 text-xs text-ink-500">
          <Loader2 size={14} className="animate-spin" /> Loading sample rows…
        </div>
      )}

      {!loading && error && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Could not load the sample: {error}
        </p>
      )}

      {!loading && !error && data && (
        <>
          <div className="overflow-hidden rounded-lg border border-ink-200">
            <div className="max-h-96 overflow-auto">
              <table className="w-full whitespace-nowrap text-xs">
                <thead className="sticky top-0 bg-ink-50">
                  <tr className="border-b border-ink-200">
                    <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-ink-400">
                      #
                    </th>
                    {columns.map((c) => (
                      <th
                        key={c}
                        className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-500"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr
                      key={i}
                      className="border-b border-ink-100 last:border-b-0 hover:bg-ink-50/60"
                    >
                      <td className="px-3 py-2 font-mono text-[10px] text-ink-400">
                        {i + 1}
                      </td>
                      {columns.map((c) => (
                        <td
                          key={c}
                          className="max-w-[260px] truncate px-3 py-2 font-mono text-ink-800"
                          title={String(row[c] ?? '')}
                        >
                          {formatCell(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="mt-2 text-[11px] text-ink-500">
            Showing the first {data.shown} row{data.shown === 1 ? '' : 's'}
            {data.total_rows != null
              ? ` of ${Number(data.total_rows).toLocaleString()}`
              : ''}
            . Download the dataset for the full file.
          </p>
        </>
      )}
    </div>
  )
}