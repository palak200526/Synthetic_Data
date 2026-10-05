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
  Sparkles,
  Save,
  Loader2,
  RefreshCw,
  Wand2,
  Info,
  ChevronDown,
  Check,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import DataTable from '../components/DataTable.jsx'
import ErrorState from '../components/ErrorState.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Toast from '../components/Toast.jsx'

import { datasetApi, normalizeDatasetProfile } from '../api/datasetApi.js'
import { llmApi, extractAnalysis, VALID_ACTIONS } from '../api/llmApi.js'
import {
  configurationApi,
  extractConfigurations,
} from '../api/configurationApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { loadBatch, getLastSessionId } from '../utils/batchStore.js'

const ACTION_LABELS = {
  keep: 'Keep',
  remove: 'Remove',
  new_id: 'New ID',
  generalize: 'Generalize',
  derived: 'Derived',
  llm: 'LLM Text',
}

const ACTION_STYLES = {
  keep: 'text-emerald-700 bg-emerald-50 ring-emerald-200',
  remove: 'text-rose-700 bg-rose-50 ring-rose-200',
  new_id: 'text-brand-700 bg-brand-50 ring-brand-200',
  generalize: 'text-amber-700 bg-amber-50 ring-amber-200',
  derived: 'text-violet-700 bg-violet-50 ring-violet-200',
  llm: 'text-sky-700 bg-sky-50 ring-sky-200',
}

function normalizeColumnType(dtype) {
  if (!dtype) return 'string'
  const d = String(dtype).toLowerCase()
  if (/^int/.test(d)) return 'integer'
  if (/float|double|decimal|numeric/.test(d)) return 'numeric'
  if (/bool/.test(d)) return 'boolean'
  if (/datetime|timestamp/.test(d)) return 'datetime'
  if (/^date/.test(d)) return 'date'
  if (/str|object|category/.test(d)) return 'string'
  return d
}

// Backend rule: 'new_id' requires is_identifier = true.
function coerceIdentifier(action, isIdentifier) {
  if (action === 'new_id') return true
  return isIdentifier
}

function ActionPill({ action, muted }) {
  if (!action) {
    return <span className="text-[11px] text-ink-400">—</span>
  }
  const style = ACTION_STYLES[action] || ACTION_STYLES.keep
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset',
        style,
        muted ? 'opacity-60' : '',
      ].join(' ')}
    >
      {ACTION_LABELS[action] || action}
    </span>
  )
}

const TEXT_NAME_HINTS = [
  'text',
  'content',
  'body',
  'tweet',
  'caption',
  'post',
  'feedback',
  'comment',
  'review',
  'description',
  'complaint',
  'remark',
  'reason',
  'message',
  'note',
  'summary',
  'narrative',
]

function suggestAction(columnName, columnType) {
  const name = String(columnName || '').toLowerCase().trim()
  const type = String(columnType || '').toLowerCase()
  if (
    (type === 'string' || type === 'object' || type === 'category') &&
    TEXT_NAME_HINTS.some((hint) => name.includes(hint))
  ) {
    return {
      action: 'llm',
      reason: 'Free-form text column. Recommended for LLM generation.',
    }
  }
  if (
    name.endsWith('_id') ||
    name === 'id' ||
    name.endsWith(' id') ||
    name.endsWith('_key') ||
    name.endsWith(' key') ||
    name === 'uuid' ||
    name === 'guid' ||
    name === 'pk'
  ) {
    return {
      action: 'new_id',
      reason: 'Looks like an identifier column. Regenerate unique IDs.',
    }
  }
  if (name.startsWith('unnamed') || name === 'index') {
    return {
      action: 'remove',
      reason: 'Index or empty column.',
    }
  }
  return {
    action: 'keep',
    reason: 'Standard feature column. Model with generative distribution.',
  }
}

function rowFromProfile(name, dtypeMap) {
  const columnType = normalizeColumnType(dtypeMap[name])
  const suggested = suggestAction(name, columnType)
  const isId = coerceIdentifier(suggested.action, suggested.action === 'new_id')
  return {
    columnName: name,
    columnType,
    isIdentifier: isId,
    action: suggested.action,
    rule: null,
    reason: suggested.reason,
    llmAction: suggested.action,
    llmIdentifier: isId,
    savedAction: null,
    savedIdentifier: null,
  }
}

function buildRowsFromAnalysis(analysis, profileColumnOrder, dtypeMap) {
  const byName = new Map(analysis.map((a) => [a.columnName, a]))

  const ordered = []
  for (const name of profileColumnOrder) {
    const a = byName.get(name)
    if (a) {
      ordered.push(a)
      byName.delete(name)
    } else {
      const fallback = rowFromProfile(name, dtypeMap)
      ordered.push({
        columnName: name,
        isIdentifier: fallback.isIdentifier,
        action: fallback.action,
        reason: fallback.reason,
      })
    }
  }
  for (const a of byName.values()) ordered.push(a)

  let corrected = 0
  const rows = ordered.map((a) => {
    const isId = coerceIdentifier(a.action, a.isIdentifier)
    if (isId !== a.isIdentifier) corrected++
    return {
      columnName: a.columnName,
      columnType: normalizeColumnType(dtypeMap[a.columnName]),
      isIdentifier: isId,
      action: a.action,
      rule: null,
      reason: a.reason,
      llmAction: a.action,
      llmIdentifier: a.isIdentifier,
      savedAction: null,
      savedIdentifier: null,
    }
  })

  return { rows, corrected }
}

export default function ColumnAnalysis() {
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

  const [dtypeMap, setDtypeMap] = useState({})
  const [profileColumnOrder, setProfileColumnOrder] = useState([])
  const [rows, setRows] = useState([])

  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [progress, setProgress] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState(null)

  const dirty = useMemo(
    () =>
      rows.some(
        (r) =>
          r.action !== r.savedAction ||
          r.isIdentifier !== r.savedIdentifier,
      ),
    [rows],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [profileRes, configsRes] = await Promise.allSettled([
        datasetApi.profile(datasetId),
        configurationApi.get(datasetId),
      ])

      let dmap = {}
      let order = []

      if (profileRes.status === 'fulfilled') {
        const normalized = normalizeDatasetProfile(profileRes.value.data)
        for (const c of normalized?.columns || []) {
          dmap[c.name] = c.dtype
          order.push(c.name)
        }
      }

      setDtypeMap(dmap)
      setProfileColumnOrder(order)

      let saved = []
      if (configsRes.status === 'fulfilled') {
        saved = extractConfigurations(configsRes.value.data)
      }

      if (saved.length > 0) {
        const sorted = [...saved].sort((a, b) => {
          const ia = order.indexOf(a.columnName)
          const ib = order.indexOf(b.columnName)
          if (ia === -1 && ib === -1) return 0
          if (ia === -1) return 1
          if (ib === -1) return -1
          return ia - ib
        })

        setRows(
          sorted.map((c) => {
            const isId = coerceIdentifier(c.action, c.isIdentifier)
            const suggested = suggestAction(
              c.columnName,
              c.columnType || dmap[c.columnName],
            )
            return {
              columnName: c.columnName,
              columnType:
                c.columnType || normalizeColumnType(dmap[c.columnName]),
              isIdentifier: isId,
              action: c.action,
              rule: c.rule ?? null,
              reason: suggested.reason,
              llmAction: suggested.action,
              llmIdentifier: isId,
              savedAction: c.action,
              savedIdentifier: isId,
            }
          }),
        )
      } else {
        setRows(order.map((name) => rowFromProfile(name, dmap)))
      }

      if (profileRes.status === 'rejected' && saved.length === 0) {
        setError(getErrorMessage(profileRes.reason))
      } else if (profileRes.status === 'rejected') {
        setToast({
          type: 'info',
          title: 'Profile not loaded',
          message:
            'Showing saved configuration. Column types may fall back to "string".',
        })
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [datasetId])

  useEffect(() => {
    load()
  }, [load])

  const handleAnalyze = async () => {
    setError('')
    setAnalyzing(true)
    setProgress(null)

    try {
      const startRes = await llmApi.analyzeColumns(datasetId)
      const jobId = startRes.data?.job_id

      // Synchronous response (no job_id)
      if (!jobId || typeof llmApi.getAnalysisStatus !== 'function') {
        const analysis = extractAnalysis(startRes.data)
        if (analysis.length === 0) {
          setError('LLM analysis returned no columns.')
          setAnalyzing(false)
          return
        }
        const { rows: newRows, corrected } = buildRowsFromAnalysis(
          analysis,
          profileColumnOrder,
          dtypeMap,
        )
        setRows(newRows)
        setAnalyzing(false)
        setToast({
          type: 'success',
          title: 'Analysis complete',
          message:
            corrected > 0
              ? `${newRows.length} columns analyzed. Auto-marked ${corrected} column${
                  corrected === 1 ? '' : 's'
                } as identifier for the "new_id" action.`
              : `${newRows.length} columns analyzed. Review and save.`,
        })
        return
      }

      // Background job
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await llmApi.getAnalysisStatus(jobId)
          const { status, progress: prog, result, error: errMsg } =
            statusRes.data

          if (prog) setProgress(prog)

          if (status === 'SUCCESS') {
            clearInterval(pollInterval)
            const analysis = extractAnalysis(result)
            const { rows: newRows, corrected } = buildRowsFromAnalysis(
              analysis,
              profileColumnOrder,
              dtypeMap,
            )
            setRows(newRows)
            setAnalyzing(false)
            setProgress(null)
            setToast({
              type: 'success',
              title: 'Analysis complete',
              message:
                corrected > 0
                  ? `${newRows.length} columns analyzed. Auto-marked ${corrected} column${
                      corrected === 1 ? '' : 's'
                    } as identifier for the "new_id" action.`
                  : `${newRows.length} columns analyzed. Review and save.`,
            })
          } else if (status === 'FAILURE') {
            clearInterval(pollInterval)
            setAnalyzing(false)
            setProgress(null)
            setError(errMsg || 'Analysis failed on the server.')
          }
        } catch (err) {
          clearInterval(pollInterval)
          setAnalyzing(false)
          setProgress(null)
          setError(getErrorMessage(err))
        }
      }, 3000)
    } catch (err) {
      setAnalyzing(false)
      setProgress(null)
      setError(getErrorMessage(err))
    }
  }

  const handleSave = async () => {
    if (rows.length === 0) return
    setError('')
    setSaving(true)
    try {
      const res = await configurationApi.save(datasetId, rows)
      const count = Array.isArray(res.data?.data)
        ? res.data.data.length
        : rows.length

      setRows((prev) =>
        prev.map((r) => ({
          ...r,
          savedAction: r.action,
          savedIdentifier: r.isIdentifier,
        })),
      )
      setToast({
        type: 'success',
        title: 'Configuration saved',
        message: `${count} column configuration${
          count === 1 ? '' : 's'
        } persisted.`,
      })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  // Changing action auto-flips identifier for new_id.
  const changeAction = (columnName, nextAction) => {
    setRows((prev) =>
      prev.map((r) =>
        r.columnName === columnName
          ? {
              ...r,
              action: nextAction,
              isIdentifier: coerceIdentifier(nextAction, r.isIdentifier),
            }
          : r,
      ),
    )
  }

  const toggleIdentifier = (columnName) => {
    setRows((prev) =>
      prev.map((r) =>
        r.columnName === columnName
          ? { ...r, isIdentifier: !r.isIdentifier }
          : r,
      ),
    )
  }

  const goto = (path) => {
    const qs = sessionId ? `?session=${sessionId}` : ''
    navigate(`${path}${qs}`)
  }

  const busy = analyzing || saving
  const anySaved = rows.some((r) => r.savedAction !== null)

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
        title="Column analysis & configuration"
        subtitle="LLM recommends an action per column. Review, adjust, and save."
        breadcrumb={
          <button
            onClick={() => goto(`/datasets/${datasetId}/profile`)}
            className="inline-flex items-center gap-1 hover:text-ink-700"
          >
            <ArrowLeft size={12} /> Dataset profile
          </button>
        }
        actions={
          <>
            <button
              type="button"
              className="dx-btn-outline"
              onClick={handleAnalyze}
              disabled={busy || loading}
            >
              {analyzing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : rows.length > 0 ? (
                <RefreshCw size={14} />
              ) : (
                <Wand2 size={14} />
              )}
              {analyzing
                ? 'Analyzing…'
                : rows.length > 0
                ? 'Re-analyze'
                : 'Analyze columns'}
            </button>

            <button
              type="button"
              className="dx-btn-primary"
              onClick={handleSave}
              disabled={busy || loading || rows.length === 0 || !dirty}
              title={
                !dirty
                  ? anySaved
                    ? 'Everything is already saved'
                    : 'Run analysis first'
                  : 'Save column configuration'
              }
            >
              {saving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              {saving ? 'Saving…' : 'Save configuration'}
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
                Select a file to configure its columns.
              </p>
            </div>

            <div className="relative w-full sm:w-80">
              <select
                id="dataset-switcher"
                value={datasetId}
                onChange={(e) => {
                  const nextId = e.target.value
                  if (!nextId || String(nextId) === String(datasetId)) return
                  if (
                    dirty &&
                    !window.confirm(
                      'Discard unsaved changes and switch files?',
                    )
                  ) {
                    return
                  }
                  const qs = sessionId ? `?session=${sessionId}` : ''
                  navigate(`/datasets/${nextId}/columns${qs}`, {
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

          <div className="mt-3 flex flex-wrap gap-1.5">
            {batch.map((b) => {
              const active = String(b.id) === String(datasetId)
              return (
                <button
                  key={b.id}
                  onClick={() => {
                    if (active) return
                    if (
                      dirty &&
                      !window.confirm(
                        'Discard unsaved changes and switch files?',
                      )
                    ) {
                      return
                    }
                    const qs = sessionId ? `?session=${sessionId}` : ''
                    navigate(`/datasets/${b.id}/columns${qs}`, {
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

      {batch.length <= 1 && (
        <div className="mb-5 rounded-lg border border-ink-200 bg-ink-50/60 px-4 py-3 text-xs text-ink-500">
          Working on{' '}
          <span className="font-medium text-ink-700">
            {batchEntry?.fileName || `dataset ${datasetId}`}
          </span>
          .
        </div>
      )}

      {analyzing && progress && (
        <div className="mb-5 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
          <div className="flex items-center justify-between text-xs text-brand-800">
            <span className="font-medium">
              {progress.stage === 'profiling' && 'Building column profiles…'}
              {progress.stage === 'llm_analysis' &&
                `Analyzing batch ${progress.current_batch} of ${progress.total_batches}`}
              {!progress.stage && 'Analyzing columns…'}
            </span>
            <span className="font-mono">{progress.percent ?? 0}%</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
            <div
              className="h-full rounded-full bg-brand-500 transition-all duration-500"
              style={{ width: `${progress.percent || 0}%` }}
            />
          </div>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {loading && !error && (
        <div className="dx-card">
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-ink-500">
            <Loader2 size={16} className="animate-spin" />
            Loading configuration…
          </div>
        </div>
      )}

      {!loading && !error && rows.length === 0 && (
        <EmptyState
          icon={Sparkles}
          title="No configuration yet"
          description="Run the LLM analysis to get per-column recommendations, or open this page after a previous save. String/text columns can be set to LLM Text."
          action={
            <button
              onClick={handleAnalyze}
              className="dx-btn-primary mt-2"
              disabled={analyzing}
            >
              {analyzing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Wand2 size={14} />
              )}
              {analyzing ? 'Analyzing…' : 'Analyze columns with LLM'}
            </button>
          }
        />
      )}

      {!loading && !error && rows.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-ink-500">
            <span>
              {rows.length} column{rows.length === 1 ? '' : 's'}
            </span>
            {anySaved && !dirty && (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
                Saved
              </span>
            )}
            {dirty && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                Unsaved changes
              </span>
            )}
          </div>

          <DataTable
            data={rows}
            getRowKey={(r) => r.columnName}
            emptyTitle="No columns"
            columns={[
              {
                key: 'columnName',
                header: 'Column',
                render: (r) => (
                  <span className="font-medium text-ink-900">
                    {r.columnName}
                  </span>
                ),
              },
              {
                key: 'columnType',
                header: 'Data type',
                render: (r) => (
                  <span className="inline-flex items-center rounded-md bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-700">
                    {r.columnType}
                  </span>
                ),
              },
              {
                key: 'isIdentifier',
                header: 'Identifier',
                render: (r) => (
                  <button
                    type="button"
                    onClick={() => toggleIdentifier(r.columnName)}
                    disabled={busy || r.action === 'new_id'}
                    className={[
                      'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset transition',
                      r.isIdentifier
                        ? 'bg-brand-50 text-brand-700 ring-brand-200 hover:bg-brand-100'
                        : 'bg-ink-100 text-ink-500 ring-ink-200 hover:bg-ink-200',
                      r.action === 'new_id'
                        ? 'cursor-not-allowed opacity-90'
                        : '',
                    ].join(' ')}
                    title={
                      r.action === 'new_id'
                        ? 'Required for the "new_id" action'
                        : 'Click to toggle identifier'
                    }
                  >
                    {r.isIdentifier ? (
                      <>
                        <Check size={11} /> Yes
                      </>
                    ) : (
                      'No'
                    )}
                  </button>
                ),
              },
              {
                key: 'recommended',
                header: 'LLM recommendation',
                render: (r) => (
                  <ActionPill
                    action={r.llmAction || r.action}
                    muted={
                      r.savedAction !== null &&
                      r.action !== (r.llmAction || r.action)
                    }
                  />
                ),
              },
              {
                key: 'action',
                header: 'Action',
                render: (r) => (
                  <select
                    value={r.action}
                    disabled={busy}
                    onChange={(e) =>
                      changeAction(r.columnName, e.target.value)
                    }
                    className="dx-input py-1.5 text-xs min-w-[130px]"
                  >
                    {VALID_ACTIONS.map((a) => (
                      <option key={a} value={a}>
                        {ACTION_LABELS[a] || a}
                      </option>
                    ))}
                  </select>
                ),
              },
              {
                key: 'reason',
                header: 'Reason',
                render: (r) =>
                  r.reason ? (
                    <span className="text-xs text-ink-600" title={r.reason}>
                      {r.reason}
                    </span>
                  ) : (
                    <span className="text-xs text-ink-400">—</span>
                  ),
              },
            ]}
          />

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2 text-[11px] text-ink-500">
              <Info size={14} className="mt-0.5 shrink-0" />
              <span>
                Actions: <strong>keep</strong> preserves the column,{' '}
                <strong>remove</strong> drops it, <strong>new_id</strong>{' '}
                regenerates identifiers (requires Identifier = Yes),{' '}
                <strong>generalize</strong> reduces detail,{' '}
                <strong>derived</strong> creates a computed column,{' '}
                <strong>llm</strong> generates new free-form text with the
                local Ollama model (not copied from source).
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                className="dx-btn-outline"
                onClick={() => goto(`/datasets/${datasetId}/preprocess`)}
                disabled={busy || dirty}
                title={
                  dirty
                    ? 'Save your changes before continuing'
                    : 'Continue to preprocessing'
                }
              >
                Preprocessing <ArrowRight size={12} />
              </button>

              <button
                type="button"
                className="dx-btn-primary"
                onClick={handleSave}
                disabled={busy || !dirty}
              >
                {saving ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Save size={14} />
                )}
                {saving ? 'Saving…' : 'Save configuration'}
              </button>
            </div>
          </div>
        </>
      )}
    </>
  )
}