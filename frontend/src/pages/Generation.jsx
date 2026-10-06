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
  Cpu,
  PlayCircle,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
  Braces,
  Zap,
  Layers,
  Plus,
  Download,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import InfoGrid from '../components/InfoGrid.jsx'
import ErrorState from '../components/ErrorState.jsx'
import EmptyState from '../components/EmptyState.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import Toast from '../components/Toast.jsx'
import CreateGroupDialog from '../components/CreateGroupDialog.jsx'

import { datasetApi, normalizeDatasetProfile } from '../api/datasetApi.js'
import {
  configurationApi,
  extractConfigurations,
} from '../api/configurationApi.js'
import {
  generationApi,
  normalizeGenerationResult,
  MODELS,
  MODEL_PARAMS,
  LLM_TEXT_PARAMS,
  getModelById,
} from '../api/generationApi.js'
import apiClient from '../api/client.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber } from '../utils/format.js'
import { loadBatch, getLastSessionId } from '../utils/batchStore.js'
import { loadLocalGroups } from '../api/groupApi.js'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function waitForGenerationJob(jobId, onProgress) {
  for (;;) {
    const statusRes = await generationApi.getStatus(jobId)
    const payload = statusRes.data || {}
    const status = payload.status
    if (payload.progress) onProgress(payload.progress)
    if (status === 'SUCCESS') return payload.result || payload
    if (status === 'FAILURE') {
      throw new Error(payload.error || 'Generation failed')
    }
    await sleep(2500)
  }
}

export default function Generation() {
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

  // ── context (profile + saved config) ──────────────────────────
  const [profile, setProfile] = useState(null)
  const [configCount, setConfigCount] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // ── selection ─────────────────────────────────────────────────
  const [modelId, setModelId] = useState('gaussian_copula')
  const [multiTable, setMultiTable] = useState(false)
  const [groups, setGroups] = useState(() => loadLocalGroups())
  const [groupId, setGroupId] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)

  // Per-model parameter form: { [key]: value }
  const [paramValues, setParamValues] = useState({})
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [paramsError, setParamsError] = useState('')

  // ── run state ─────────────────────────────────────────────────
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState('')
  const [result, setResult] = useState(null)
  const [toast, setToast] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [progress, setProgress] = useState(null)

  // Reset per-dataset state when the file changes.
  useEffect(() => {
    setResult(null)
    setRunError('')
    setToast(null)
    setParamValues({})
    setParamsError('')
    setShowAdvanced(false)
    setMultiTable(false)
    setGroupId('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId])

  // Clear stale results when the user switches mode or changes group.
  useEffect(() => {
    setResult(null)
    setRunError('')
  }, [multiTable, groupId])

  // Refresh groups when dialog closes or mode toggles
  useEffect(() => {
    setGroups(loadLocalGroups())
  }, [dialogOpen, multiTable])

  // Reset param values when the model changes
  useEffect(() => {
    setParamValues({})
    setParamsError('')
  }, [modelId])

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

      if (
        profileRes.status === 'rejected' &&
        configRes.status === 'rejected'
      ) {
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

  // Build parameters object from the form. Empty fields are skipped.
  const buildParameters = () => {
    const out = {}
    const fields = [...(MODEL_PARAMS[modelId] || []), ...LLM_TEXT_PARAMS]
    for (const f of fields) {
      const raw = paramValues[f.key]
      if (raw === undefined || raw === null || raw === '') continue

      if (f.type === 'number') {
        const n = Number(raw)
        if (Number.isNaN(n)) {
          return { error: `"${f.label}" must be a number.` }
        }
        out[f.key] = n
      } else if (f.type === 'boolean') {
        out[f.key] = raw === true || raw === 'true'
      } else {
        out[f.key] = raw
      }
    }
    return { value: Object.keys(out).length ? out : null }
  }

  const handleRun = async () => {
    setRunError('')
    setResult(null)
    setParamsError('')

    const { value: parameters, error: pErr } = buildParameters()
    if (pErr) {
      setParamsError(pErr)
      setShowAdvanced(true)
      return
    }

    const selectedModel = getModelById(modelId)
    if (!selectedModel) {
      setRunError('Please select a generation model.')
      return
    }

    if (multiTable) {
      const gid = Number(groupId)
      if (!groupId || Number.isNaN(gid) || gid <= 0) {
        setRunError('Select a dataset group for multi-table generation.')
        return
      }
    }

    setRunning(true)
    setProgress(null)
    try {
      const res = multiTable
        ? await generationApi.generateMultiTable({
            groupId: Number(groupId),
            modelName: selectedModel.backendName,
            parameters,
          })
        : await generationApi.generate({
            datasetId,
            modelName: selectedModel.backendName,
            parameters,
          })

      let payload = res.data
      const jobId = payload?.job_id
      if (jobId && (payload.status === 'queued' || payload.status === 'PENDING')) {
        payload = await waitForGenerationJob(jobId, setProgress)
      }

      const normalized = normalizeGenerationResult(payload)
      setResult(normalized)
      setToast({
        type: 'success',
        title: 'Generation complete',
        message:
          normalized?.message ||
          'Synthetic dataset generated successfully.',
      })
    } catch (err) {
      setRunError(getErrorMessage(err))
    } finally {
      setRunning(false)
      setProgress(null)
    }
  }

  const handleGenerateIds = async () => {
    setRunError('')
    setRunning(true)
    try {
      const res = await generationApi.generateIds(datasetId)
      setToast({
        type: 'success',
        title: 'IDs generated',
        message:
          res?.data?.message || 'ID columns generated successfully.',
      })
    } catch (err) {
      setRunError(getErrorMessage(err))
    } finally {
      setRunning(false)
    }
  }

  // ── single-file download ──────────────────────────────────────
  const handleDownload = async () => {
    if (!result) return

    const sourceId = datasetId
    const syntheticId = result.syntheticDatasetId
    const runId = result.runId

    const attempts = []
    if (sourceId != null && runId != null) {
      attempts.push({
        dataset_id: Number(sourceId),
        run_id: Number(runId),
        type: 'dataset',
      })
    }
    if (sourceId != null) {
      attempts.push({ dataset_id: Number(sourceId), type: 'dataset' })
    }
    if (syntheticId != null && runId != null) {
      attempts.push({
        dataset_id: Number(syntheticId),
        run_id: Number(runId),
        type: 'dataset',
      })
    }
    if (syntheticId != null) {
      attempts.push({ dataset_id: Number(syntheticId), type: 'dataset' })
    }
    if (runId != null) {
      attempts.push({ run_id: Number(runId), type: 'dataset' })
    }

    if (attempts.length === 0) {
      setToast({
        type: 'error',
        title: 'Download unavailable',
        message: 'No dataset or run ID available to download.',
      })
      return
    }

    setDownloading(true)
    let lastErrMsg = 'Download failed.'

    for (const params of attempts) {
      try {
        const res = await apiClient.get('/download', {
          params,
          responseType: 'blob',
          timeout: 5 * 60 * 1000,
        })

        const ct = res.headers?.['content-type'] || ''

        if (ct.includes('application/json')) {
          const text = await res.data.text()
          let parsed = null
          try {
            parsed = JSON.parse(text)
          } catch {
            /* not JSON */
          }
          if (
            parsed &&
            typeof parsed === 'object' &&
            (parsed.detail || parsed.error || parsed.status === 'error')
          ) {
            if (Array.isArray(parsed.detail)) {
              lastErrMsg = parsed.detail
                .map((d) => d.msg || d.message || JSON.stringify(d))
                .join(' • ')
            } else {
              lastErrMsg =
                parsed.detail || parsed.message || parsed.error || lastErrMsg
            }
            continue
          }
        }

        const disposition = res.headers?.['content-disposition'] || ''
        let fileName = null
        const utf8 = /filename\*=UTF-8''([^;\r\n]+)/i.exec(disposition)
        if (utf8 && utf8[1]) {
          try {
            fileName = decodeURIComponent(utf8[1].trim())
          } catch {
            fileName = utf8[1].trim()
          }
        }
        if (!fileName) {
          const plain = /filename="?([^";\r\n]+)"?/i.exec(disposition)
          if (plain && plain[1]) fileName = plain[1].trim()
        }
        if (!fileName) {
          fileName =
            result.fileName ||
            `synthetic_dataset_${syntheticId || sourceId}.csv`
        }

        const blob = new Blob([res.data], {
          type: ct || 'application/octet-stream',
        })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = fileName
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)

        setToast({
          type: 'success',
          title: 'Download started',
          message: fileName,
        })
        setDownloading(false)
        return
      } catch (err) {
        const status = err?.response?.status
        lastErrMsg = getErrorMessage(err)
        if (status && ![400, 404, 422].includes(status)) break
      }
    }

    setDownloading(false)
    setToast({
      type: 'error',
      title: 'Download failed',
      message: lastErrMsg,
    })
  }

  // ── per-file download (multi-table) ───────────────────────────
  const downloadOne = async (target) => {
    const sourceId = datasetId
    const runId = result?.runId

    // Prefer the per-dataset id if the backend returned one, else the
    // source dataset id + run id as disambiguator.
    const attempts = []
    if (target?.datasetId != null) {
      attempts.push({ dataset_id: Number(target.datasetId), type: 'dataset' })
    }
    if (sourceId != null && runId != null) {
      attempts.push({
        dataset_id: Number(sourceId),
        run_id: Number(runId),
        type: 'dataset',
      })
    }
    if (sourceId != null) {
      attempts.push({ dataset_id: Number(sourceId), type: 'dataset' })
    }

    let lastErr = null
    for (const params of attempts) {
      try {
        const res = await apiClient.get('/download', {
          params,
          responseType: 'blob',
          timeout: 5 * 60 * 1000,
        })

        const ct = res.headers?.['content-type'] || ''
        if (ct.includes('application/json')) {
          const text = await res.data.text()
          let msg = null
          try {
            const parsed = JSON.parse(text)
            if (
              parsed &&
              (parsed.detail || parsed.error || parsed.status === 'error')
            ) {
              msg =
                parsed.detail ||
                parsed.message ||
                (Array.isArray(parsed.detail)
                  ? parsed.detail.map((d) => d.msg).join(' • ')
                  : 'Download failed.')
            }
          } catch {
            /* not JSON */
          }
          if (msg) {
            lastErr = new Error(msg)
            continue
          }
        }

        const disposition = res.headers?.['content-disposition'] || ''
        const match = /filename\*?=(?:UTF-8'')?"?([^";\r\n]+)"?/i.exec(
          disposition,
        )
        const fileName =
          (match && decodeURIComponent(match[1])) ||
          target.fileName ||
          `synthetic_${target.datasetId || 'dataset'}.csv`

        const blob = new Blob([res.data], {
          type: ct || 'application/octet-stream',
        })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = fileName
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        return fileName
      } catch (err) {
        lastErr = err
        const status = err?.response?.status
        if (status && ![400, 404, 422].includes(status)) break
      }
    }
    throw lastErr || new Error('Download failed')
  }

  const handleDownloadAll = async () => {
    if (!result?.datasets?.length) return
    setDownloading(true)
    const failures = []
    let ok = 0

    for (const d of result.datasets) {
      try {
        await downloadOne(d)
        ok++
      } catch (err) {
        failures.push({
          name: d.fileName || `dataset ${d.datasetId}`,
          message: getErrorMessage(err),
        })
      }
    }

    setDownloading(false)
    if (failures.length === 0) {
      setToast({
        type: 'success',
        title: 'Download complete',
        message: `${ok} file${ok === 1 ? '' : 's'} saved.`,
      })
    } else {
      setToast({
        type: 'error',
        title: `Downloaded ${ok}, failed ${failures.length}`,
        message: failures.map((f) => f.name).join(', '),
      })
    }
  }

  const goto = (path) => {
    const qs = sessionId ? `?session=${sessionId}` : ''
    navigate(`${path}${qs}`)
  }

  const selectedModel = getModelById(modelId)
  const configReady = configCount != null && configCount > 0
  const busy = running || loading

  const noRelationships =
    multiTable && /no relationship/i.test(runError || '')

  const paramsForModel = [
    ...(MODEL_PARAMS[modelId] || []),
    ...LLM_TEXT_PARAMS,
  ]
  const hasMultiDatasets =
    Array.isArray(result?.datasets) && result.datasets.length > 1

  return (
    <>
      <Toast
        open={!!toast}
        type={toast?.type || 'success'}
        title={toast?.title}
        message={toast?.message}
        onClose={() => setToast(null)}
      />

      <CreateGroupDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={(created) => {
          if (created?.group_id != null) setGroupId(String(created.group_id))
          setGroups(loadLocalGroups())
        }}
      />

      <PageHeader
        title="Synthetic data generation"
        subtitle="Choose a model and generate a synthetic version of the prepared dataset."
        breadcrumb={
          <button
            onClick={() => goto(`/datasets/${datasetId}/preprocess`)}
            className="inline-flex items-center gap-1 hover:text-ink-700"
          >
            <ArrowLeft size={12} /> Preprocessing
          </button>
        }
        actions={
          <>
            <button
              type="button"
              className="dx-btn-outline"
              onClick={handleGenerateIds}
              disabled={busy}
              title="Calls POST /generation/ids/{dataset_id}"
            >
              <Zap size={14} /> Generate IDs
            </button>
            <button
              type="button"
              className="dx-btn-primary"
              onClick={handleRun}
              disabled={busy || !configReady}
              title={
                !configReady
                  ? 'Save a column configuration first'
                  : 'Run generation'
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
                ? 'Generating…'
                : result
                ? 'Re-generate'
                : 'Generate'}
            </button>
          </>
        }
      />

      {batch.length > 1 && !multiTable && (
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
                Select a file to generate from.
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
                  navigate(`/datasets/${nextId}/generate${qs}`, {
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
          {/* ── Context stats ─────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Cpu}
              label="Dataset"
              value={
                profile?.name || batchEntry?.fileName || `#${datasetId}`
              }
              accent="brand"
            />
            <StatCard
              icon={Cpu}
              label="Rows"
              value={profile?.rows != null ? formatNumber(profile.rows) : null}
              accent="ink"
            />
            <StatCard
              icon={Cpu}
              label="Columns"
              value={
                profile?.columnsCount != null
                  ? formatNumber(profile.columnsCount)
                  : null
              }
              accent="ink"
            />
            <StatCard
              icon={Cpu}
              label="Configured columns"
              value={configCount != null ? formatNumber(configCount) : null}
              hint={!configReady ? 'No configuration saved yet' : undefined}
              accent={configReady ? 'emerald' : 'amber'}
            />
          </div>

          {!configReady && (
            <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-start gap-3">
                <AlertTriangle
                  size={16}
                  className="mt-0.5 shrink-0 text-amber-700"
                />
                <div>
                  <p className="text-sm font-semibold text-amber-900">
                    Column configuration required
                  </p>
                  <p className="mt-0.5 text-xs text-amber-800">
                    Generation uses the saved configuration. Run the LLM
                    analysis and save it first.
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

          {/* ── Mode toggle ──────────────────────────────────── */}
          {configReady && (
            <div className="mt-6 flex flex-wrap items-center gap-3 text-xs">
              <span className="text-ink-500">Mode:</span>
              <div className="inline-flex rounded-lg border border-ink-200 bg-white p-0.5">
                <button
                  type="button"
                  onClick={() => setMultiTable(false)}
                  disabled={busy}
                  className={[
                    'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium transition',
                    !multiTable
                      ? 'bg-brand-50 text-brand-700'
                      : 'text-ink-500 hover:bg-ink-50',
                  ].join(' ')}
                >
                  <Cpu size={12} /> Single dataset
                </button>
                <button
                  type="button"
                  onClick={() => setMultiTable(true)}
                  disabled={busy}
                  className={[
                    'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium transition',
                    multiTable
                      ? 'bg-brand-50 text-brand-700'
                      : 'text-ink-500 hover:bg-ink-50',
                  ].join(' ')}
                >
                  <Layers size={12} /> Multi-table
                </button>
              </div>
              {multiTable && (
                <span className="text-ink-500">
                  Preserves configured relationships between tables.
                </span>
              )}
            </div>
          )}

          {/* ── Group dropdown (multi-table only) ────────────── */}
          {configReady && multiTable && (
            <div className="mt-4 dx-card p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <label
                    htmlFor="group-id"
                    className="block text-xs font-semibold uppercase tracking-wide text-ink-500"
                  >
                    Dataset group
                  </label>
                  <p className="mt-0.5 text-[11px] text-ink-400">
                    All related tables must belong to the same group.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setDialogOpen(true)}
                  disabled={busy}
                  className="dx-btn-outline text-xs"
                >
                  <Plus size={12} /> Create group
                </button>
              </div>

              {groups.length === 0 ? (
                <div className="mt-3 rounded-lg border border-dashed border-ink-300 bg-ink-50 px-4 py-3 text-xs text-ink-500">
                  No groups yet. Click <strong>Create group</strong> above,
                  then re-upload your tables with that group selected.
                </div>
              ) : (
                <div className="relative mt-3 max-w-md">
                  <select
                    id="group-id"
                    value={groupId}
                    onChange={(e) => setGroupId(e.target.value)}
                    disabled={busy}
                    className="dx-input appearance-none pr-9 cursor-pointer"
                  >
                    <option value="">Select a group…</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name} (#{g.id})
                        {g.domainType ? ` · ${g.domainType}` : ''}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={14}
                    className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400"
                  />
                </div>
              )}
            </div>
          )}

          {/* ── Model picker ──────────────────────────────────── */}
          {configReady && (
            <div className="mt-6">
              <h2 className="mb-3 text-sm font-semibold text-ink-900">
                Generation model
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {MODELS.map((m) => {
                  const active = m.id === modelId
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setModelId(m.id)}
                      disabled={busy}
                      className={[
                        'flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition',
                        active
                          ? 'border-brand-400 bg-brand-50/40 ring-2 ring-brand-500/20'
                          : 'border-ink-200 bg-white hover:border-brand-300 hover:bg-ink-50/40',
                      ].join(' ')}
                    >
                      <div className="flex w-full items-center justify-between">
                        <span className="text-sm font-semibold text-ink-900">
                          {m.label}
                        </span>
                        <span
                          className={[
                            'rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset',
                            m.speed === 'Fast'
                              ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                              : 'bg-amber-50 text-amber-700 ring-amber-200',
                          ].join(' ')}
                        >
                          {m.speed}
                        </span>
                      </div>
                      <p className="text-xs text-ink-500">{m.description}</p>
                      <p className="text-[11px] text-ink-400">
                        Best for: {m.bestFor}
                      </p>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* ── Advanced parameters (form, per-model) ─────────── */}
          {configReady && paramsForModel.length > 0 && (
            <div className="mt-6 dx-card overflow-hidden">
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className="flex w-full items-center justify-between px-5 py-3 text-left hover:bg-ink-50/60"
              >
                <span className="inline-flex items-center gap-2 text-sm font-medium text-ink-900">
                  <Braces size={14} className="text-ink-400" />
                  Advanced parameters ({selectedModel?.label})
                </span>
                <ChevronDown
                  size={14}
                  className={[
                    'text-ink-400 transition-transform',
                    showAdvanced ? 'rotate-180' : '',
                  ].join(' ')}
                />
              </button>

              {showAdvanced && (
                <div className="border-t border-ink-100 px-5 py-4">
                  <p className="mb-4 text-xs text-ink-500">
                    All fields are optional. Leave blank to use the model's
                    defaults. Only filled fields are sent to the backend.
                  </p>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {paramsForModel.map((f) => (
                      <label key={f.key} className="block">
                        <span className="mb-1.5 block text-xs font-medium text-ink-700">
                          {f.label}
                        </span>

                        {f.type === 'select' ? (
                          <select
                            value={paramValues[f.key] ?? ''}
                            onChange={(e) =>
                              setParamValues((p) => ({
                                ...p,
                                [f.key]: e.target.value,
                              }))
                            }
                            disabled={busy}
                            className="dx-input"
                          >
                            <option value="">— default —</option>
                            {f.options.map((o) => (
                              <option key={o} value={o}>
                                {o}
                              </option>
                            ))}
                          </select>
                        ) : f.type === 'boolean' ? (
                          <select
                            value={paramValues[f.key] ?? ''}
                            onChange={(e) =>
                              setParamValues((p) => ({
                                ...p,
                                [f.key]: e.target.value,
                              }))
                            }
                            disabled={busy}
                            className="dx-input"
                          >
                            <option value="">— default —</option>
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        ) : (
                          <input
                            type="number"
                            min={f.min}
                            step={f.step}
                            value={paramValues[f.key] ?? ''}
                            onChange={(e) =>
                              setParamValues((p) => ({
                                ...p,
                                [f.key]: e.target.value,
                              }))
                            }
                            disabled={busy}
                            placeholder="—"
                            className="dx-input"
                          />
                        )}
                      </label>
                    ))}
                  </div>

                  {paramsError && (
                    <p className="mt-3 text-[11px] text-rose-600">
                      {paramsError}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── Run state / results ───────────────────────────── */}
          <div className="mt-6">
            {running && (
              <div className="dx-card p-6">
                <div className="flex items-center gap-3">
                  <Loader2
                    size={18}
                    className="animate-spin text-brand-600"
                  />
                  <div>
                    <p className="text-sm font-semibold text-ink-900">
                      Generating synthetic data…
                    </p>
                    <p className="text-xs text-ink-500">
                      {progress?.stage === 'llm_text'
                        ? `Local Ollama is filling text column ${
                            progress.column || ''
                          } (${progress.generated ?? 0}/${
                            progress.requested ?? '?'
                          }).`
                        : `${selectedModel?.label} is training on ${
                            profile?.rows != null
                              ? formatNumber(profile.rows)
                              : 'the dataset'
                          } rows. Text columns use the local Ollama model in batches.`}
                    </p>
                  </div>
                </div>
                <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(8, Number(progress?.percent) || 12),
                      )}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {/* No-relationships panel (multi-table only) */}
            {!running && noRelationships && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
                <div className="flex items-start gap-3">
                  <AlertTriangle
                    size={16}
                    className="mt-0.5 shrink-0 text-amber-700"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-amber-900">
                      No relationships defined for this group
                    </p>
                    <p className="mt-0.5 text-xs text-amber-800">
                      Multi-table generation needs at least one parent-child
                      relationship between the tables in the group. Define
                      relationships first, or generate each table
                      independently in single-table mode.
                    </p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="dx-btn-outline text-xs"
                        onClick={() => {
                          setMultiTable(false)
                          setRunError('')
                        }}
                      >
                        <Cpu size={12} /> Switch to single-table mode
                      </button>
                      <button
                        type="button"
                        className="dx-btn-outline text-xs"
                        onClick={() => goto('/relationships')}
                      >
                        <Layers size={12} /> Go to Relationships
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Generic errors (not the no-relationships case) */}
            {!running && runError && !noRelationships && (
              <ErrorState
                title="Generation failed"
                message={runError}
                onRetry={handleRun}
              />
            )}

            {!running && !runError && !result && configReady && (
              <EmptyState
                icon={Cpu}
                title="Ready to generate"
                description={`${selectedModel?.label} will produce a synthetic version of this dataset.`}
                action={
                  <button className="dx-btn-primary mt-2" onClick={handleRun}>
                    <PlayCircle size={14} /> Generate synthetic data
                  </button>
                }
              />
            )}

            {!running && !runError && result && (
              <div className="dx-card p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="grid h-9 w-9 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
                      <CheckCircle2 size={18} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-ink-900">
                        {result.message || 'Synthetic dataset generated'}
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-ink-500">
                        {result.status && (
                          <StatusBadge status={result.status} />
                        )}
                        {result.model && <span>· {result.model}</span>}
                        {result.finishedAt && (
                          <span>
                            · {new Date(result.finishedAt).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {hasMultiDatasets ? (
                      <button
                        className="dx-btn-outline"
                        onClick={handleDownloadAll}
                        disabled={downloading}
                        title="Download every generated dataset"
                      >
                        {downloading ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Download size={14} />
                        )}
                        {downloading
                          ? 'Downloading…'
                          : `Download all (${result.datasets.length})`}
                      </button>
                    ) : (
                      <button
                        className="dx-btn-outline"
                        onClick={handleDownload}
                        disabled={
                          downloading ||
                          (result.syntheticDatasetId == null &&
                            !result.filePath)
                        }
                        title="Download the generated dataset"
                      >
                        {downloading ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Download size={14} />
                        )}
                        {downloading ? 'Downloading…' : 'Download'}
                      </button>
                    )}

                    {result.syntheticDatasetId != null && (
                      <button
                        className="dx-btn-outline"
                        onClick={() =>
                          goto(
                            `/datasets/${result.syntheticDatasetId}/profile`,
                          )
                        }
                        title="Open the generated dataset's profile"
                      >
                        View profile
                      </button>
                    )}

                    <button
                    className="dx-btn-primary"
                    onClick={() => {
                      const qs = new URLSearchParams()
                      if (result?.resultId != null) qs.set('result_id', String(result.resultId))
                      if (sessionId) qs.set('session', String(sessionId))
                      const tail = qs.toString() ? `?${qs}` : ''
                      navigate(`/datasets/${datasetId}/evaluate${tail}`)
                    }}
                  >
                    Continue to evaluation <ArrowRight size={12} />
                  </button>
                  </div>
                </div>

                <div className="mt-5 border-t border-ink-100 pt-5">
                  <InfoGrid
                    items={[
                      {
                        label: 'Synthetic dataset ID',
                        value: result.syntheticDatasetId,
                      },
                      {
                        label: 'Rows generated',
                        value:
                          result.rows != null
                            ? formatNumber(result.rows)
                            : null,
                      },
                      {
                        label: 'Columns',
                        value:
                          result.columns != null
                            ? formatNumber(result.columns)
                            : null,
                      },
                      {
                        label: 'Duration',
                        value:
                          result.duration != null
                            ? `${Number(result.duration).toFixed(1)}s`
                            : null,
                      },
                      {
                        label: 'Output file',
                        value: result.fileName || result.filePath,
                      },
                      {
                        label: 'Multi-table',
                        value:
                          result.isMultiTable != null
                            ? result.isMultiTable
                              ? 'Yes'
                              : 'No'
                            : null,
                      },
                    ]}
                  />
                </div>

                {/* Per-file list for multi-table results */}
                {Array.isArray(result.datasets) &&
                  result.datasets.length > 0 && (
                    <div className="mt-5 border-t border-ink-100 pt-5">
                      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
                        Generated datasets ({result.datasets.length})
                      </p>
                      <ul className="space-y-2">
                        {result.datasets.map((d) => (
                          <li
                            key={d.datasetId || d.fileName}
                            className="flex items-center justify-between gap-3 rounded-lg border border-ink-200 bg-ink-50/60 px-3 py-2 text-xs"
                          >
                            <div className="min-w-0">
                              <p className="truncate font-medium text-ink-800">
                                {d.fileName || `Dataset ${d.datasetId}`}
                              </p>
                              <p className="mt-0.5 text-[11px] text-ink-500">
                                {d.rows != null
                                  ? `${d.rows.toLocaleString()} rows · `
                                  : ''}
                                {d.columns != null
                                  ? `${d.columns} cols · `
                                  : ''}
                                ID {d.datasetId}
                              </p>
                            </div>
                            <button
                              type="button"
                              className="dx-btn-outline shrink-0 text-xs"
                              onClick={async () => {
                                try {
                                  setDownloading(true)
                                  await downloadOne(d)
                                } catch (err) {
                                  setToast({
                                    type: 'error',
                                    title: 'Download failed',
                                    message: getErrorMessage(err),
                                  })
                                } finally {
                                  setDownloading(false)
                                }
                              }}
                              disabled={downloading}
                            >
                              <Download size={12} /> Download
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                {result.raw && (
                  <details className="mt-4">
                    <summary className="cursor-pointer text-[11px] font-medium text-ink-500 hover:text-ink-700">
                      Raw response
                    </summary>
                    <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-ink-900 p-3 text-[11px] leading-relaxed text-ink-100">
                      {JSON.stringify(result.raw, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>

          {/* ── About panel ───────────────────────────────────── */}
          <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2"></div>
            <aside className="space-y-4">
              <div className="dx-card p-5">
                <div className="flex items-center gap-2 text-brand-600">
                  <Info size={16} />
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    About generation
                  </span>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-ink-600">
                  <li>· Training runs entirely on the backend.</li>
                  <li>· Uses the preprocessed dataset and saved configuration.</li>
                  <li>· Multi-table requires a dataset group with relationships.</li>
                  <li>· Advanced parameters are optional per model.</li>
                  <li>
                    · <code className="font-mono">Generate IDs</code> calls{' '}
                    <code className="font-mono">
                      POST /generation/ids/{datasetId}
                    </code>
                    .
                  </li>
                </ul>
              </div>
            </aside>
          </div>
        </>
      )}
    </>
  )
}