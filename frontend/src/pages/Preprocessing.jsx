import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Loader2,
  Wrench,
  PlayCircle,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import InfoGrid from '../components/InfoGrid.jsx'
import ErrorState from '../components/ErrorState.jsx'
import EmptyState from '../components/EmptyState.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import Toast from '../components/Toast.jsx'

import { datasetApi, normalizeDatasetProfile, normalizePreprocessResult } from '../api/datasetApi.js'
import { configurationApi, extractConfigurations } from '../api/configurationApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber } from '../utils/format.js'
import { loadBatch, getLastSessionId } from '../utils/batchStore.js'

export default function Preprocessing() {
  const { datasetId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session') || getLastSessionId()

  const [batch, setBatch] = useState(() => loadBatch(sessionId))
  useEffect(() => {
    setBatch(loadBatch(sessionId))
  }, [sessionId])

  const batchEntry = useMemo(() => {
    if (!Array.isArray(batch)) return null
    return batch.find((b) => String(b?.id) === String(datasetId)) || null
  }, [batch, datasetId])

  // ── readiness snapshot (profile + saved configs) ─────────────
  const [profile, setProfile] = useState(null)
  const [configCount, setConfigCount] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // ── preprocess request state ─────────────────────────────────
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState('')
  const [result, setResult] = useState(null)
  const [toast, setToast] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [profileRes, configRes] = await Promise.allSettled([
        datasetApi.profile(datasetId),
        configurationApi.get(datasetId),
      ])

      if (profileRes.status === 'fulfilled') {
        const norm = normalizeDatasetProfile(profileRes.value.data) || {}
        if (batchEntry) {
          if (!norm.name) norm.name = batchEntry.fileName
          if (norm.rows == null) norm.rows = batchEntry.rows
          if (norm.columnsCount == null)
            norm.columnsCount = batchEntry.columns
          if (!norm.createdAt) norm.createdAt = batchEntry.uploadDate
        }
        setProfile(norm)
      } else {
        setProfile(null)
      }

      if (configRes.status === 'fulfilled') {
        setConfigCount(extractConfigurations(configRes.value.data).length)
      } else {
        setConfigCount(null)
      }

      if (profileRes.status === 'rejected' && configRes.status === 'rejected') {
        setLoadError(
          getErrorMessage(profileRes.reason || configRes.reason),
        )
      }
    } finally {
      setLoading(false)
    }
  }, [datasetId, batchEntry])

  useEffect(() => {
    load()
  }, [load])

  const handleRun = async () => {
    setRunError('')
    setResult(null)
    setRunning(true)
    try {
      const res = await datasetApi.preprocess(datasetId)
      const normalized = normalizePreprocessResult(res.data)
      setResult(normalized)
      setToast({
        type: 'success',
        title: 'Preprocessing complete',
        message: normalized?.message || 'The dataset has been preprocessed.',
      })
    } catch (err) {
      setRunError(getErrorMessage(err))
    } finally {
      setRunning(false)
    }
  }

  const goto = (path) => {
    const qs = sessionId ? `?session=${sessionId}` : ''
    navigate(`${path}${qs}`)
  }

  const configReady = configCount != null && configCount > 0

  return (
    <>
      <Toast
        open={!!toast}
        type={toast?.type || 'success'}
        title={toast?.title}
        message={toast?.message}
        onClose={() => setToast(null)}
      />

      <PageHeader
        title="Preprocessing"
        subtitle="Apply the saved column configuration to the dataset."
        breadcrumb={
          <button
            onClick={() => goto(`/datasets/${datasetId}/columns`)}
            className="inline-flex items-center gap-1 hover:text-ink-700"
          >
            <ArrowLeft size={12} /> Column configuration
          </button>
        }
        actions={
          <button
            type="button"
            className="dx-btn-primary"
            onClick={handleRun}
            disabled={running || loading || !configReady}
            title={
              !configReady
                ? 'Save a column configuration first'
                : 'Run preprocessing'
            }
          >
            {running ? (
              <Loader2 size={14} className="animate-spin" />
            ) : result ? (
              <RefreshCw size={14} />
            ) : (
              <PlayCircle size={14} />
            )}
            {running
              ? 'Preprocessing…'
              : result
              ? 'Re-run preprocessing'
              : 'Run preprocessing'}
          </button>
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
                Select a file to preprocess.
              </p>
            </div>
            <div className="relative w-full sm:w-80">
              <select
                id="dataset-switcher"
                value={datasetId}
                onChange={(e) => {
                  const nextId = e.target.value
                  if (!nextId || String(nextId) === String(datasetId)) return
                  const qs = sessionId ? `?session=${sessionId}` : ''
                  navigate(`/datasets/${nextId}/preprocess${qs}`, {
                    replace: true,
                  })
                }}
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
        </div>
      )}

      {loadError && <ErrorState message={loadError} onRetry={load} />}

      {loading && !loadError && (
        <div className="dx-card">
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-ink-500">
            <Loader2 size={16} className="animate-spin" />
            Loading dataset context…
          </div>
        </div>
      )}

      {!loading && !loadError && (
        <>
          {/* ── Summary of what will be preprocessed ───────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Wrench}
              label="Dataset"
              value={
                profile?.name ||
                batchEntry?.fileName ||
                `#${datasetId}`
              }
              accent="brand"
            />
            <StatCard
              icon={Wrench}
              label="Rows"
              value={profile?.rows != null ? formatNumber(profile.rows) : null}
              accent="ink"
            />
            <StatCard
              icon={Wrench}
              label="Columns"
              value={
                profile?.columnsCount != null
                  ? formatNumber(profile.columnsCount)
                  : null
              }
              accent="ink"
            />
            <StatCard
              icon={Wrench}
              label="Configured columns"
              value={configCount != null ? formatNumber(configCount) : null}
              hint={
                !configReady
                  ? 'No configuration saved yet'
                  : undefined
              }
              accent={configReady ? 'emerald' : 'amber'}
            />
          </div>

          {!configReady && (
            <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-start gap-3">
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-700">
                  <AlertTriangle size={16} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-amber-900">
                    Column configuration required
                  </p>
                  <p className="mt-0.5 text-xs text-amber-800">
                    Preprocessing applies the saved column configuration. Run
                    the LLM analysis and save it first.
                  </p>
                  <button
                    className="dx-btn-outline mt-3 text-xs"
                    onClick={() => goto(`/datasets/${datasetId}/columns`)}
                  >
                    <ArrowLeft size={12} /> Go to column configuration
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── Run state / results ───────────────────────────── */}
          <div className="mt-6">
            {running && (
              <div className="dx-card p-6">
                <div className="flex items-center gap-3">
                  <Loader2 size={18} className="animate-spin text-brand-600" />
                  <div>
                    <p className="text-sm font-semibold text-ink-900">
                      Preprocessing in progress…
                    </p>
                    <p className="text-xs text-ink-500">
                      The backend is applying the column configuration. This
                      can take a minute on large datasets.
                    </p>
                  </div>
                </div>
                <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                  <div className="h-full w-1/3 animate-pulse rounded-full bg-brand-500" />
                </div>
              </div>
            )}

            {!running && runError && (
              <ErrorState
                title="Preprocessing failed"
                message={runError}
                onRetry={handleRun}
              />
            )}

            {!running && !runError && !result && configReady && (
              <EmptyState
                icon={Wrench}
                title="Ready to preprocess"
                description="The column configuration is saved. Run preprocessing to apply it to the dataset."
                action={
                  <button
                    className="dx-btn-primary mt-2"
                    onClick={handleRun}
                  >
                    <PlayCircle size={14} /> Run preprocessing
                  </button>
                }
              />
            )}

            {!running && !runError && result && (
              <div className="space-y-4">
                <div className="dx-card p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="grid h-9 w-9 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
                        <CheckCircle2 size={18} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-ink-900">
                          {result.message || 'Preprocessing complete'}
                        </p>
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-ink-500">
                          {result.status && (
                            <StatusBadge status={result.status} />
                          )}
                          {result.finishedAt && (
                            <span>
                              ·{' '}
                              {new Date(result.finishedAt).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <button
                      className="dx-btn-primary"
                      onClick={() =>
                        goto(`/datasets/${datasetId}/generate`)
                      }
                    >
                      Continue to generation <ArrowRight size={12} />
                    </button>
                  </div>

                  {(result.rowsBefore != null ||
                    result.rowsAfter != null ||
                    result.columnsBefore != null ||
                    result.columnsAfter != null) && (
                    <div className="mt-5 border-t border-ink-100 pt-5">
                      <InfoGrid
                        items={[
                          {
                            label: 'Rows before',
                            value:
                              result.rowsBefore != null
                                ? formatNumber(result.rowsBefore)
                                : null,
                          },
                          {
                            label: 'Rows after',
                            value:
                              result.rowsAfter != null
                                ? formatNumber(result.rowsAfter)
                                : null,
                          },
                          {
                            label: 'Columns before',
                            value:
                              result.columnsBefore != null
                                ? formatNumber(result.columnsBefore)
                                : null,
                          },
                          {
                            label: 'Columns after',
                            value:
                              result.columnsAfter != null
                                ? formatNumber(result.columnsAfter)
                                : null,
                          },
                          {
                            label: 'Processed dataset ID',
                            value: result.processedDatasetId,
                          },
                        ]}
                      />
                    </div>
                  )}
                </div>

                {Array.isArray(result.removedColumns) &&
                  result.removedColumns.length > 0 && (
                    <div className="dx-card p-5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                        Removed columns
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {result.removedColumns.map((c) => (
                          <span
                            key={c}
                            className="rounded-md bg-rose-50 px-2 py-0.5 font-mono text-[11px] text-rose-700 ring-1 ring-inset ring-rose-200"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                {Array.isArray(result.addedColumns) &&
                  result.addedColumns.length > 0 && (
                    <div className="dx-card p-5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                        Added columns
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {result.addedColumns.map((c) => (
                          <span
                            key={c}
                            className="rounded-md bg-emerald-50 px-2 py-0.5 font-mono text-[11px] text-emerald-700 ring-1 ring-inset ring-emerald-200"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                {Array.isArray(result.transformations) &&
                  result.transformations.length > 0 && (
                    <div className="dx-card p-5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                        Transformations applied
                      </p>
                      <ul className="mt-2 space-y-1.5 text-xs text-ink-700">
                        {result.transformations.map((t, i) => (
                          <li key={i} className="flex gap-2">
                            <span className="text-ink-400">·</span>
                            <span>
                              {typeof t === 'string'
                                ? t
                                : t?.message ||
                                  t?.description ||
                                  JSON.stringify(t)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                {Array.isArray(result.warnings) &&
                  result.warnings.length > 0 && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
                      <div className="flex items-start gap-3">
                        <AlertTriangle
                          size={16}
                          className="mt-0.5 shrink-0 text-amber-700"
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-amber-900">
                            Validation messages
                          </p>
                          <ul className="mt-2 space-y-1.5 text-xs text-amber-800">
                            {result.warnings.map((w, i) => (
                              <li key={i}>
                                {typeof w === 'string'
                                  ? w
                                  : w?.message ||
                                    w?.detail ||
                                    JSON.stringify(w)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                {Array.isArray(result.errors) &&
                  result.errors.length > 0 && (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-5">
                      <div className="flex items-start gap-3">
                        <AlertTriangle
                          size={16}
                          className="mt-0.5 shrink-0 text-rose-700"
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-rose-900">
                            Errors
                          </p>
                          <ul className="mt-2 space-y-1.5 text-xs text-rose-800">
                            {result.errors.map((e, i) => (
                              <li key={i}>
                                {typeof e === 'string'
                                  ? e
                                  : e?.message ||
                                    e?.detail ||
                                    JSON.stringify(e)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}
              </div>
            )}
          </div>

          {/* ── Sidebar: what happens next ────────────────────── */}
          <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2"></div>
            <aside className="space-y-4">
              <div className="dx-card p-5">
                <div className="flex items-center gap-2 text-brand-600">
                  <Info size={16} />
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    About preprocessing
                  </span>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-ink-600">
                  <li>· Applied per dataset using the saved configuration.</li>
                  <li>
                    · <strong>keep</strong> / <strong>remove</strong> /{' '}
                    <strong>new_id</strong> / <strong>generalize</strong> /{' '}
                    <strong>derived</strong> are enforced by the backend.
                  </li>
                  <li>· No transformations run in the browser.</li>
                </ul>
              </div>
            </aside>
          </div>
        </>
      )}
    </>
  )
}