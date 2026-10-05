import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import {
  ArrowLeft,
  ChevronDown,
  Database,
  Rows3,
  Columns3,
  FileSpreadsheet,
  Calendar,
  Sparkles,
  RefreshCw,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import DataTable from '../components/DataTable.jsx'
import InfoGrid from '../components/InfoGrid.jsx'
import ErrorState from '../components/ErrorState.jsx'
import LoadingState from '../components/LoadingState.jsx'

import { datasetApi, normalizeDatasetProfile } from '../api/datasetApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber, formatPercent } from '../utils/format.js'
import { loadBatch, getLastSessionId } from '../utils/batchStore.js'

function dtypeLabel(dtype) {
  if (!dtype) return '—'
  const d = String(dtype).toLowerCase()
  if (/int/.test(d)) return 'integer'
  if (/float|double|decimal|numeric/.test(d)) return 'float'
  if (/bool/.test(d)) return 'boolean'
  if (/datetime|timestamp|date/.test(d)) return 'datetime'
  if (/object|string|category/.test(d)) return 'string'
  return dtype
}

export default function Profile() {
  const { datasetId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

  // session id can come from the URL (?session=92) or from the last
  // upload performed in this browser. URL wins so direct links work.
  const sessionId = searchParams.get('session') || getLastSessionId()

  const batch = useMemo(() => {
    const list = loadBatch(sessionId)
    // Also fold in anything passed via navigation state (legacy path).
    const stateBatch = location.state?.batch
    if (Array.isArray(stateBatch) && stateBatch.length && list.length === 0) {
      return stateBatch
    }
    return list
  }, [sessionId, location.state])

  const batchEntry = useMemo(
    () => batch.find((b) => String(b.id) === String(datasetId)) || null,
    [batch, datasetId],
  )

  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await datasetApi.profile(datasetId)
      const normalized = normalizeDatasetProfile(res.data) || {}

      // Merge metadata from the upload batch when the profile endpoint
      // doesn't return it (row count, filename, upload date).
      if (batchEntry) {
        if (!normalized.name) normalized.name = batchEntry.fileName
        if (normalized.rows == null) normalized.rows = batchEntry.rows
        if (normalized.columnsCount == null)
          normalized.columnsCount = batchEntry.columns
        if (!normalized.createdAt)
          normalized.createdAt = batchEntry.uploadDate
        if (!normalized.fileType && batchEntry.fileName) {
          normalized.fileType = batchEntry.fileName
            .split('.')
            .pop()
            .toLowerCase()
        }
      }
      setProfile(normalized)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [datasetId, batchEntry])

  useEffect(() => {
    load()
  }, [load])

  const handleSelect = (e) => {
    const nextId = e.target.value
    if (!nextId || String(nextId) === String(datasetId)) return
    const qs = sessionId ? `?session=${sessionId}` : ''
    navigate(`/datasets/${nextId}/profile${qs}`, { replace: true })
  }

  const numericColumns = (profile?.columns || []).filter((c) => c.numeric)
  const categoricalColumns = (profile?.columns || []).filter(
    (c) => c.topValues && c.topValues.length > 0,
  )
  const columnRows = (profile?.columns || []).map((c) => ({
    ...c,
    key: c.name,
  }))

  const displayName =
    profile?.name ||
    batchEntry?.fileName ||
    (batch.length > 1 ? 'Dataset profile' : 'Dataset profile')

  return (
    <>
      <PageHeader
        title={displayName}
        subtitle={
          profile?.datasetId
            ? `Dataset ID · ${profile.datasetId}`
            : 'Column-level statistics and profiling.'
        }
        breadcrumb={
          <button
            onClick={() => navigate('/dashboard')}
            className="inline-flex items-center gap-1 hover:text-ink-700"
          >
            <ArrowLeft size={12} /> Dashboard
          </button>
        }
        actions={
          <>
            <button
              onClick={load}
              className="dx-btn-outline"
              disabled={loading}
            >
              <RefreshCw
                size={14}
                className={loading ? 'animate-spin' : ''}
              />
              Refresh
            </button>
            <button
            onClick={() =>
                navigate(
                `/datasets/${datasetId}/columns${
                    sessionId ? `?session=${sessionId}` : ''
                }`,
                )
            }
            className="dx-btn-primary"
            disabled={loading || !profile}
            >
            <Sparkles size={14} /> Column analysis
            </button>
          </>
        }
      />

      {batch.length > 1 && (
        <div className="mb-5 dx-card px-4 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <label
                htmlFor="dataset-switcher"
                className="block text-[11px] font-semibold uppercase tracking-wide text-ink-500"
              >
                Uploaded in this batch ({batch.length})
              </label>
              <p className="mt-0.5 text-[11px] text-ink-400">
                Select a file to view its profile.
              </p>
            </div>

            <div className="relative w-full sm:w-80">
              <select
                id="dataset-switcher"
                value={datasetId}
                onChange={handleSelect}
                className="dx-input appearance-none pr-9 cursor-pointer"
              >
                {batch.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.fileName || `Dataset ${b.id}`}
                    {b.rows != null ? ` — ${b.rows.toLocaleString()} rows` : ''}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400"
              />
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {batch.map((b) => {
              const active = String(b.id) === String(datasetId)
              return (
                <button
                  key={b.id}
                  onClick={() => {
                    if (active) return
                    const qs = sessionId ? `?session=${sessionId}` : ''
                    navigate(`/datasets/${b.id}/profile${qs}`, {
                      replace: true,
                    })
                  }}
                  className={[
                    'rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset transition',
                    active
                      ? 'bg-brand-50 text-brand-700 ring-brand-200'
                      : 'bg-white text-ink-600 ring-ink-200 hover:bg-ink-50',
                  ].join(' ')}
                  title={b.fileName || `Dataset ${b.id}`}
                >
                  {b.fileName || `#${b.id}`}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {loading && !error && (
        <div className="dx-card">
          <LoadingState label="Loading dataset profile…" />
        </div>
      )}

      {!loading && !error && profile && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Rows3}
              label="Rows"
              value={profile.rows != null ? formatNumber(profile.rows) : null}
              accent="brand"
            />
            <StatCard
              icon={Columns3}
              label="Columns"
              value={
                profile.columnsCount != null
                  ? formatNumber(profile.columnsCount)
                  : null
              }
              accent="ink"
            />
            <StatCard
              icon={FileSpreadsheet}
              label="File type"
              value={
                profile.fileType ? String(profile.fileType).toUpperCase() : null
              }
              accent="ink"
            />
            <StatCard
              icon={Calendar}
              label="Uploaded"
              value={
                profile.createdAt
                  ? new Date(profile.createdAt).toLocaleDateString()
                  : null
              }
              accent="ink"
            />
          </div>

          <div className="mt-8">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">Columns</h2>
            <DataTable
              data={columnRows}
              emptyTitle="No column information"
              emptyDescription="The backend did not return per-column profiles."
              columns={[
                {
                  key: 'name',
                  header: 'Column',
                  render: (r) => (
                    <span className="font-medium text-ink-900">{r.name}</span>
                  ),
                },
                {
                  key: 'dtype',
                  header: 'Type',
                  render: (r) => (
                    <span className="inline-flex items-center rounded-md bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-700">
                      {dtypeLabel(r.dtype)}
                    </span>
                  ),
                },
                {
                  key: 'missing',
                  header: 'Missing',
                  render: (r) =>
                    r.missing == null && r.missingPct == null
                      ? '—'
                      : `${formatNumber(r.missing)} (${
                          r.missingPct != null
                            ? formatPercent(r.missingPct)
                            : '—'
                        })`,
                },
                {
                  key: 'unique',
                  header: 'Unique',
                  render: (r) => formatNumber(r.unique),
                },
                {
                  key: 'uniqueRatio',
                  header: 'Unique ratio',
                  render: (r) => formatPercent(r.uniqueRatio),
                },
                {
                  key: 'samples',
                  header: 'Sample values',
                  render: (r) => {
                    if (!r.samples || r.samples.length === 0) return '—'
                    return (
                      <span className="font-mono text-[11px] text-ink-600">
                        {r.samples.slice(0, 3).map((s) => String(s)).join(', ')}
                        {r.samples.length > 3 ? ' …' : ''}
                      </span>
                    )
                  },
                },
              ]}
            />
          </div>

          {numericColumns.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-sm font-semibold text-ink-900">
                Numeric statistics
              </h2>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {numericColumns.map((c) => (
                  <div key={c.name} className="dx-card p-5">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-sm font-semibold text-ink-900">
                        {c.name}
                      </p>
                      <span className="inline-flex items-center rounded-md bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-700">
                        {dtypeLabel(c.dtype)}
                      </span>
                    </div>
                    <InfoGrid
                      items={[
                        { label: 'Mean', value: c.numeric.mean ?? '—' },
                        { label: 'Std', value: c.numeric.std ?? '—' },
                        { label: 'Min', value: c.numeric.min ?? '—' },
                        { label: 'Q1', value: c.numeric.q1 ?? '—' },
                        { label: 'Median', value: c.numeric.median ?? '—' },
                        { label: 'Q3', value: c.numeric.q3 ?? '—' },
                        { label: 'Max', value: c.numeric.max ?? '—' },
                      ].map((i) => ({
                        ...i,
                        value:
                          typeof i.value === 'number'
                            ? Number(i.value).toLocaleString(undefined, {
                                maximumFractionDigits: 4,
                              })
                            : i.value,
                      }))}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {categoricalColumns.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-sm font-semibold text-ink-900">
                Categorical information
              </h2>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {categoricalColumns.map((c) => (
                  <div key={c.name} className="dx-card p-5">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-sm font-semibold text-ink-900">
                        {c.name}
                      </p>
                      <span className="text-[11px] text-ink-500">
                        {formatNumber(c.unique)} unique
                      </span>
                    </div>
                    <ul className="space-y-1.5">
                      {c.topValues.slice(0, 6).map((v, i) => (
                        <li
                          key={`${v.value}-${i}`}
                          className="flex items-center justify-between gap-3 rounded-md bg-ink-50 px-2.5 py-1.5 text-xs"
                        >
                          <span className="truncate font-mono text-ink-700">
                            {String(v.value)}
                          </span>
                          {v.count != null && (
                            <span className="shrink-0 text-ink-500">
                              {formatNumber(v.count)}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!profile.columns?.length && (
            <div className="mt-8 rounded-xl border border-dashed border-ink-300 bg-ink-50 p-6 text-center">
              <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-full bg-ink-100 text-ink-500">
                <Database size={18} />
              </div>
              <p className="text-sm font-semibold text-ink-900">
                No column-level profile returned
              </p>
              <p className="mx-auto mt-1 max-w-md text-xs text-ink-500">
                The dataset was uploaded, but the profile response did not
                include per-column data. Inspect{' '}
                <code className="font-mono">GET /profile/{datasetId}</code> in
                the network tab.
              </p>
              <Link
                to="/dashboard"
                className="dx-btn-outline mt-4 inline-flex"
              >
                <ArrowLeft size={12} /> Back to dashboard
              </Link>
            </div>
          )}
        </>
      )}
    </>
  )
}