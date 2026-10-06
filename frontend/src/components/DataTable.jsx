import EmptyState from './EmptyState.jsx'
import LoadingState from './LoadingState.jsx'

export default function DataTable({
  columns = [],
  data = [],
  loading = false,
  emptyTitle = 'No rows',
  emptyDescription,
  getRowKey = (row, i) => row?.id ?? row?._id ?? i,
  onRowClick,
}) {
  if (loading) return <LoadingState />
  if (!data || data.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />
  }

  return (
    <div className="overflow-hidden rounded-xl border border-ink-200 bg-white">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink-200 bg-ink-50/60 text-left">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500"
                  style={c.width ? { width: c.width } : undefined}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={getRowKey(row, i)}
                className={[
                  'border-b border-ink-100 last:border-b-0',
                  onRowClick ? 'cursor-pointer hover:bg-ink-50' : '',
                ].join(' ')}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className="px-4 py-3 align-middle text-ink-700"
                  >
                    {c.render ? c.render(row, i) : row[c.key] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}