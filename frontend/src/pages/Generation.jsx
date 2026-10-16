import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  Loader2,
  Cpu,
  PlayCircle,
  Play,
  Pause,
  RotateCcw,
  Trash2,
  History,
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
  Sparkles,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import InfoGrid from '../components/InfoGrid.jsx'
import ErrorState from '../components/ErrorState.jsx'
import EmptyState from '../components/EmptyState.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import Toast from '../components/Toast.jsx'
import CreateGroupDialog from '../components/CreateGroupDialog.jsx'
import GeneratedPreview from '../components/GeneratedPreview.jsx'
import AlgorithmPicker, {
  recommendAlgorithm,
} from '../components/AlgorithmPicker.jsx'
import AlgorithmParameterPanel from '../components/AlgorithmParameterPanel.jsx'

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
import { useGenerationTracker } from '../context/GenerationTrackerContext.jsx'
import { loadBatch, getLastSessionId } from '../utils/batchStore.js'
import { loadLocalGroups } from '../api/groupApi.js'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// Backend sends Postgres TIMESTAMPs without a timezone ("2026-10-13T05:19:57").
// They are UTC, but `new Date()` would read them as local time — so mark them
// as UTC before converting to the viewer's local timezone.
function parseServerDate(value) {
  if (!value) return null
  let v = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(v) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(v)) {
    v = v.replace(' ', 'T') + 'Z'
  }
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? null : d
}
function formatTime(value) {
  const d = parseServerDate(value)
  return d ? d.toLocaleTimeString() : '—'
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
  const [algoStats, setAlgoStats] = useState(null)
  const modelTouchedRef = useRef(false)
  const [multiTable, setMultiTable] = useState(
    () => searchParams.get('mode') === 'multi',
  )
  const [groups, setGroups] = useState(() => loadLocalGroups())
  const [groupId, setGroupId] = useState(
    () => searchParams.get('group_id') || '',
  )
  const [dialogOpen, setDialogOpen] = useState(false)

  // Per-model parameter form: { [key]: value }
  const [paramValues, setParamValues] = useState({})
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [paramsError, setParamsError] = useState('')
  const [hasLlmColumns, setHasLlmColumns] = useState(false)
  const [lastAppliedParameters, setLastAppliedParameters] = useState(null)

  // ── run state ─────────────────────────────────────────────────
  // localRunning covers requests the page awaits itself (multi-table,
  // queueing, ID generation). Background jobs are owned by the tracker.
  const [localRunning, setRunning] = useState(false)
  const [runError, setRunError] = useState('')
  const [result, setResult] = useState(null)
  const [toast, setToast] = useState(null)
  const [downloading, setDownloading] = useState(false)

  // ── global generation tracker ─────────────────────────────────
  const tracker = useGenerationTracker()
  const trackedJob = tracker.job
  const trackerRunning =
    tracker.isActive && String(trackedJob?.datasetId) === String(datasetId)
  const otherJobRunning = tracker.isActive && !trackerRunning
  const running = localRunning || trackerRunning
  const progress = trackerRunning ? trackedJob?.progress || null : null
  const handledJobRef = useRef(null)

  // Deep link from Job History: /datasets/:id/generate?job_id=...
  // Make sure the tracker is following that job (covers refresh, other
  // browsers and cleared localStorage), then scroll to the live panel.
  const linkedJobId = searchParams.get('job_id')
  const liveCardRef = useRef(null)
  useEffect(() => {
    if (!linkedJobId) return
    tracker.attach({
      jobId: linkedJobId,
      datasetId,
      sessionId: searchParams.get('session'),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedJobId, datasetId])

  const scrolledToLiveRef = useRef(null)
  useEffect(() => {
    if (!linkedJobId || !trackerRunning) return
    if (scrolledToLiveRef.current === linkedJobId) return
    if (!liveCardRef.current) return
    scrolledToLiveRef.current = linkedJobId
    liveCardRef.current.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  }, [linkedJobId, trackerRunning, loading])

  // ── active / incomplete jobs (persistent resume) ──────────────
  const [activeJobs, setActiveJobs] = useState([])
  const [loadingActiveJobs, setLoadingActiveJobs] = useState(false)

  const loadActiveJobs = useCallback(async () => {
    try {
      setLoadingActiveJobs(true)
      const res = await generationApi.listActiveJobs()
      setActiveJobs(res?.data?.jobs || [])
    } catch {
      // ignore
    } finally {
      setLoadingActiveJobs(false)
    }
  }, [])

  useEffect(() => {
    loadActiveJobs()
  }, [loadActiveJobs, datasetId])

  // Refresh the list whenever the followed job starts / finishes / pauses.
  useEffect(() => {
    loadActiveJobs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracker.job?.jobId, tracker.job?.status])

  // Jobs the tracker is already showing live below are not "incomplete".
  // Jobs that are running (but not followed here) get "View Live Progress"
  // instead of Resume — the backend rejects resuming a running job.
  const isRunningStatus = (st) => {
    const v = String(st || '').toLowerCase()
    return v === 'running' || v === 'pending'
  }
  const visibleActiveJobs = activeJobs.filter(
    (j) => !(tracker.isActive && trackedJob?.jobId === j.job_id),
  )
  const resumableCount = visibleActiveJobs.filter(
    (j) => !isRunningStatus(j.status),
  ).length

  const handleViewLiveJob = (job) => {
    tracker.attach({
      jobId: job.job_id,
      datasetId: job.dataset_id,
      modelLabel: job.model_name,
    })
    navigate(`/datasets/${job.dataset_id}/generate?job_id=${job.job_id}`)
  }

  const handleResumeIncompleteJob = async (job) => {
    try {
      await generationApi.resumeJob(job.job_id)
      tracker.attach({
        jobId: job.job_id,
        datasetId: job.dataset_id,
        modelLabel: job.model_name,
        sessionId,
      })
      setToast({
        type: 'success',
        title: 'Job Resumed',
        message: `Resuming generation for ${job.file_name} from checkpoint.`,
      })
      loadActiveJobs()
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Resume Failed',
        message: getErrorMessage(err),
      })
    }
  }

  const handleRestartIncompleteJob = async (job) => {
    if (
      !window.confirm(
        `Restart generation for "${job.file_name}" from row 0? Saved batch progress will be reset.`,
      )
    ) {
      return
    }
    try {
      await generationApi.restartJob(job.job_id)
      tracker.attach({
        jobId: job.job_id,
        datasetId: job.dataset_id,
        modelLabel: job.model_name,
        sessionId,
      })
      setToast({
        type: 'info',
        title: 'Job Restarted',
        message: `Restarted generation from row 0 for ${job.file_name}.`,
      })
      loadActiveJobs()
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Restart Failed',
        message: getErrorMessage(err),
      })
    }
  }

  const handleDiscardIncompleteJob = async (job) => {
    if (
      !window.confirm(
        `Discard generation job for "${job.file_name}"? This removes checkpoints for this run.`,
      )
    ) {
      return
    }
    try {
      await generationApi.discardJob(job.job_id)
      setToast({
        type: 'info',
        title: 'Job Discarded',
        message: `Discarded incomplete job for ${job.file_name}.`,
      })
      loadActiveJobs()
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Discard Failed',
        message: getErrorMessage(err),
      })
    }
  }

  // Reset per-dataset state when the file changes.
  useEffect(() => {
    modelTouchedRef.current = false
    setResult(null)
    setRunError('')
    setToast(null)
    setParamValues({})
    setParamsError('')
    setShowAdvanced(false)
    setMultiTable(searchParams.get('mode') === 'multi')
    setGroupId(searchParams.get('group_id') || '')
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

  // Speed per algorithm (measured from past runs, else estimates)
  useEffect(() => {
    let alive = true
    generationApi
      .algorithmStats()
      .then((res) => {
        if (alive) setAlgoStats(res?.data?.models || null)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  // Pre-select the recommended algorithm until the user picks one themselves
  useEffect(() => {
    if (!profile || modelTouchedRef.current) return
    setModelId(recommendAlgorithm(profile).id)
  }, [profile])

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
        const configs = extractConfigurations(configRes.value.data)
        setConfigCount(configs.length)
        setHasLlmColumns(
          configs.some((c) => String(c?.action || '').toLowerCase() === 'llm'),
        )
      } else {
        setConfigCount(null)
        setHasLlmColumns(false)
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

    setLastAppliedParameters(parameters)

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

      const payload = res.data
      const jobId = payload?.job_id
      if (jobId && (payload.status === 'queued' || payload.status === 'PENDING')) {
        // Hand the job to the global tracker; it keeps polling on every
        // page and the effect below shows the result when it finishes.
        const accepted = tracker.start({
          jobId,
          datasetId,
          modelLabel: selectedModel.label,
          sessionId,
        })
        if (!accepted) {
          setRunError('Another generation is already running.')
        }
        return
      }

      // Synchronous response (multi-table or background=false).
      processResult(payload)
    } catch (err) {
      setRunError(getErrorMessage(err))
    } finally {
      setRunning(false)
    }
  }

  // Turn a finished generation payload into the on-page result.
  const processResult = (payload) => {
    const normalized = normalizeGenerationResult(payload)
    setResult(normalized)

    // Persist generation result for session evaluation fallback
    if (normalized) {
      try {
        const files =
          Array.isArray(normalized.datasets) && normalized.datasets.length > 0
            ? normalized.datasets
            : normalized.resultId != null
              ? [
                  {
                    datasetId: normalized.syntheticDatasetId || datasetId,
                    resultId: normalized.resultId,
                    fileName: normalized.fileName || normalized.filePath || `dataset_${datasetId}`,
                  },
                ]
              : []
        if (files.length > 0) {
          if (sessionId) {
            localStorage.setItem(
              `dx:sessionGenerations:${sessionId}`,
              JSON.stringify(files),
            )
          }
          localStorage.setItem(
            'dx:lastGeneration',
            JSON.stringify({
              sessionId: sessionId ? String(sessionId) : null,
              datasetId: String(datasetId),
              resultId: String(files[0]?.resultId),
              files,
            }),
          )
        }
      } catch {
        /* storage unavailable */
      }
    }

    setToast({
      type: 'success',
      title: 'Generation complete',
      message:
        normalized?.message ||
        'Synthetic dataset generated successfully.',
    })
  }

  // When the tracked job for THIS dataset finishes (even if the user was on
  // another page meanwhile), show its result or error once, then release it.
  useEffect(() => {
    const job = tracker.job
    if (!job || String(job.datasetId) !== String(datasetId)) return
    if (job.status !== 'SUCCESS' && job.status !== 'FAILURE') return
    if (handledJobRef.current === job.jobId) return
    handledJobRef.current = job.jobId

    if (job.status === 'SUCCESS') processResult(job.result)
    else setRunError(job.error || 'Generation failed')

    tracker.dismiss(job.jobId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracker.job, datasetId])


  // Pause: the worker stops after the current batch and saves a checkpoint.
  const handlePauseGeneration = async () => {
    const res = await tracker.pause()
    if (res?.ok) {
      setToast({
        type: 'info',
        title: 'Pausing…',
        message:
          'Generation will stop after the current batch and save its progress.',
      })
    } else {
      setToast({
        type: 'error',
        title: 'Pause Failed',
        message: String(res?.error || 'Could not pause this job.'),
      })
    }
  }

  // When the backend confirms PAUSED, release the tracker and refresh the
  // "Resume Incomplete Generation" list so the Resume button appears.
  const pausedHandledRef = useRef(null)
  useEffect(() => {
    const job = tracker.job
    if (!job || String(job.datasetId) !== String(datasetId)) return
    if (job.status === 'PENDING' || job.status === 'PROGRESS') {
      pausedHandledRef.current = null
      return
    }
    if (job.status !== 'PAUSED') return
    if (pausedHandledRef.current === job.jobId) return
    pausedHandledRef.current = job.jobId

    setToast({
      type: 'success',
      title: 'Generation Paused',
      message: 'Progress is saved. Use Resume below to continue.',
    })
    loadActiveJobs()
    tracker.dismiss(job.jobId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracker.job, datasetId])

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
    if (target?.resultId != null) {
      attempts.push({ result_id: Number(target.resultId), type: 'dataset' })
    }
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
    const list = Array.isArray(result?.datasets) ? result.datasets : []
    if (list.length === 0) {
      setToast({
        type: 'error',
        title: 'Download failed',
        message: 'No generated tables available for download.',
      })
      return
    }
    setDownloading(true)
    try {
      for (const d of list) {
        await downloadOne(d)
        // small gap so the browser doesn't block multiple downloads
        await sleep(400)
      }
      setToast({
        type: 'success',
        title: 'Download started',
        message: 'All generated datasets are being downloaded.',
      })
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Download failed',
        message: getErrorMessage(err),
      })
    } finally {
      setDownloading(false)
    }
  }

  // Build a URL that brings the user straight back to multi-table mode
  const multiReturnUrl = () => {
    const qs = new URLSearchParams()
    qs.set('mode', 'multi')
    if (groupId) qs.set('group_id', String(groupId))
    if (sessionId) qs.set('session', String(sessionId))
    return `/datasets/${datasetId}/generate?${qs.toString()}`
  }

  const goToRelationships = () => {
    const qs = new URLSearchParams()
    if (groupId) qs.set('group_id', String(groupId))
    qs.set('return_to', multiReturnUrl())
    navigate(`/relationships?${qs.toString()}`)
  }

  const goto = (path) => {
    const qs = sessionId ? `?session=${sessionId}` : ''
    navigate(`${path}${qs}`)
  }

  const selectedModel = getModelById(modelId)
  const configReady = configCount != null && configCount > 0
  const busy = running || loading || otherJobRunning

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

      {/* Resume Incomplete Generation Section */}
      {visibleActiveJobs.length > 0 && (
        <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50/40 p-5 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-800">
                <AlertTriangle size={18} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-ink-900">
                  {resumableCount > 0
                    ? 'Resume Incomplete Generation'
                    : 'Generation In Progress'}{' '}
                  ({visibleActiveJobs.length}{' '}
                  {visibleActiveJobs.length === 1 ? 'Job' : 'Jobs'})
                </h3>
                <p className="text-xs text-ink-600">
                  Unfinished runs with saved batch checkpoints. Resume from
                  the last saved batch without regenerating completed rows,
                  or restart from the beginning.
                </p>
              </div>
            </div>
            <Link
              to="/generations"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-700 hover:text-brand-800"
            >
              <History size={13} /> View All Runs
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {visibleActiveJobs.map((job) => {
              const jobIsRunning = isRunningStatus(job.status)
              const isCurrent = String(job.dataset_id) === String(datasetId)
              const pct = Math.min(
                100,
                Math.max(0, Number(job.progress_percent || 0)),
              )
              return (
                <div
                  key={job.job_id}
                  className={[
                    'flex flex-col gap-3 rounded-lg border bg-white p-3.5 sm:flex-row sm:items-center sm:justify-between shadow-xs',
                    isCurrent
                      ? 'border-amber-400 ring-1 ring-amber-300'
                      : 'border-ink-200',
                  ].join(' ')}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-ink-900">
                        {job.file_name}
                      </span>
                      {isCurrent && (
                        <span className="rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-semibold text-brand-800">
                          Current File
                        </span>
                      )}
                      <StatusBadge status={job.status} />
                      <span className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-600">
                        {job.model_name?.toUpperCase()}
                      </span>
                      {job.llm_model && (
                        <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-700">
                          {job.llm_model}
                        </span>
                      )}
                    </div>

                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 text-[11px] text-ink-500">
                      <span>
                        Generated:{' '}
                        <strong className="text-ink-700">
                          {formatNumber(job.generated_rows || 0)}
                        </strong>{' '}
                        / {formatNumber(job.total_rows || 0)} rows ({pct}%)
                      </span>
                      {job.remaining_rows > 0 && (
                        <span>
                          Remaining: {formatNumber(job.remaining_rows)} rows
                        </span>
                      )}
                      {job.total_batches > 0 && (
                        <span>
                          Batch: {job.current_batch} / {job.total_batches}
                        </span>
                      )}
                      {job.last_checkpoint_at && (
                        <span>
                          Checkpoint:{' '}
                          {formatTime(job.last_checkpoint_at)}
                        </span>
                      )}
                    </div>

                    <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-ink-100">
                      <div
                        className="h-full bg-amber-500 transition-all duration-300"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {jobIsRunning ? (
                      <button
                        className="dx-btn-primary px-2.5 py-1 text-xs"
                        onClick={() => handleViewLiveJob(job)}
                        title="This job is already running — watch its live progress"
                      >
                        <ExternalLink size={12} /> View Live Progress
                      </button>
                    ) : (
                      <>
                        <button
                          className="dx-btn-primary px-2.5 py-1 text-xs"
                          onClick={() => handleResumeIncompleteJob(job)}
                          title="Resume from last checkpoint"
                        >
                          <Play size={12} /> Resume
                        </button>
                        <button
                          className="dx-btn-secondary px-2.5 py-1 text-xs"
                          onClick={() => handleRestartIncompleteJob(job)}
                          title="Restart from beginning"
                        >
                          <RotateCcw size={12} /> Restart
                        </button>
                        <button
                          className="dx-btn-ghost px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                          onClick={() => handleDiscardIncompleteJob(job)}
                          title="Discard job"
                        >
                          <Trash2 size={13} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

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

          {/* ── Algorithm picker (recommendation, time/100 rows, details) ── */}
          {configReady && (
            <AlgorithmPicker
              modelId={modelId}
              onSelect={(id) => {
                modelTouchedRef.current = true
                setModelId(id)
              }}
              disabled={busy}
              profile={profile}
              algoStats={algoStats}
            />
          )}

          {/* ── Algorithm-Specific Parameter Panel with Interactive Guidance ── */}
          {configReady && (
            <AlgorithmParameterPanel
              modelId={modelId}
              paramValues={paramValues}
              onChange={(newVals) => {
                setParamValues(newVals)
                setParamsError('')
              }}
              disabled={busy}
            />
          )}

          {/* ── Local LLM Text Parameters (shown only if LLM columns configured) ── */}
          {configReady && hasLlmColumns && (
            <div className="mt-4 dx-card p-4.5 border border-ink-200">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-brand-600" />
                <h4 className="text-xs font-semibold text-ink-900">
                  Local LLM Text Generation Parameters (Ollama)
                </h4>
              </div>
              <p className="text-xs text-ink-500 mb-3">
                Detected columns configured with "LLM". Configure batching and timeout parameters for Ollama.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {LLM_TEXT_PARAMS.map((f) => (
                  <label key={f.key} className="block">
                    <span className="text-[11px] font-medium text-ink-700">{f.label}</span>
                    <input
                      type="number"
                      min={f.min}
                      value={paramValues[f.key] ?? ''}
                      onChange={(e) => setParamValues((p) => ({ ...p, [f.key]: e.target.value }))}
                      disabled={busy}
                      placeholder="— default —"
                      className="dx-input text-xs mt-1"
                    />
                    <span className="mt-0.5 block text-[10px] text-ink-500">{f.help}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {paramsError && (
            <p className="mt-2 text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg p-2.5">
              {paramsError}
            </p>
          )}

          {/* ── Run state / results ───────────────────────────── */}
          <div className="mt-6">
            {otherJobRunning && (
              <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-ink-700">
                Another generation is running
                {trackedJob?.modelLabel ? ` (${trackedJob.modelLabel})` : ''}
                {trackedJob?.progress?.percent != null
                  ? ` — ${trackedJob.progress.percent}% done`
                  : ''}
                .{' '}
                <Link
                  to={`/datasets/${trackedJob?.datasetId}/generate`}
                  className="font-semibold text-brand-700 hover:underline"
                >
                  View it
                </Link>
              </div>
            )}

            {running && (
              <div className="dx-card p-6" ref={liveCardRef}>
                <div className="flex items-center gap-3">
                  <Loader2
                    size={18}
                    className="animate-spin text-brand-600"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink-900">
                      {progress?.stage_label
                        ? `Floor ${progress.stage_index} of ${progress.stage_total} · ${progress.stage_label}`
                        : 'Generating synthetic data…'}
                    </p>
                    <p className="text-xs text-ink-500">
                      {progress?.message
                        ? progress.message
                        : trackerRunning
                          ? 'Queued — waiting for the worker to start…'
                          : `${selectedModel?.label} is training on ${
                              profile?.rows != null
                                ? formatNumber(profile.rows)
                                : 'the dataset'
                            } rows. Text columns use the local Ollama model in batches.`}
                      {progress?.max_attempts > 1 && progress?.attempt > 1
                        ? ` · Retry ${progress.attempt} of ${progress.max_attempts} (some rows failed your validation rules)`
                        : ''}
                    </p>
                  </div>
                  {trackerRunning && progress?.percent != null && (
                    <span className="text-sm font-semibold tabular-nums text-ink-700">
                      {progress.percent}%
                    </span>
                  )}
                  {trackerRunning && (
                    <button
                      type="button"
                      className="dx-btn-secondary px-3 py-1.5 text-xs"
                      onClick={handlePauseGeneration}
                      disabled={trackedJob?.pausing || trackedJob?.status !== 'PROGRESS'}
                      title={
                        trackedJob?.status !== 'PROGRESS'
                          ? 'Available once the worker has started'
                          : 'Stop after the current batch and save progress'
                      }
                    >
                      {trackedJob?.pausing ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Pause size={12} />
                      )}
                      {trackedJob?.pausing ? 'Pausing…' : 'Pause'}
                    </button>
                  )}
                </div>

                <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-all duration-500"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(
                          trackerRunning ? 3 : 8,
                          Number(progress?.percent) || (trackerRunning ? 0 : 12),
                        ),
                      )}%`,
                    }}
                  />
                </div>

                {progress?.stages?.length > 0 && (
                  <ol className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5">
                    {progress.stages.map((stage, i) => {
                      const n = i + 1
                      const done = n < progress.stage_index
                      const current = n === progress.stage_index
                      return (
                        <li
                          key={stage.key}
                          className={`flex items-center gap-1.5 text-xs ${
                            current
                              ? 'font-semibold text-brand-700'
                              : done
                                ? 'text-ink-600'
                                : 'text-ink-300'
                          }`}
                        >
                          {done ? (
                            <CheckCircle2 size={12} className="text-emerald-600" />
                          ) : (
                            <span
                              className={`inline-block h-2 w-2 rounded-full ${
                                current ? 'animate-pulse bg-brand-500' : 'bg-ink-200'
                              }`}
                            />
                          )}
                          {stage.label}
                        </li>
                      )
                    })}
                  </ol>
                )}

                {trackerRunning && tracker.connectionIssue && (
                  <p className="mt-3 text-xs text-amber-700">
                    Can’t reach the server right now — retrying. Your job keeps
                    running in the background.
                  </p>
                )}
                {trackerRunning && trackedJob?.waitingHint && (
                  <p className="mt-3 text-xs text-amber-700">
                    Still waiting for a worker. If this does not start, check
                    that the backend (and Celery, if you use it) is running.
                  </p>
                )}
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
                        onClick={goToRelationships}
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
                    {hasMultiDatasets || (multiTable && result.datasets?.length > 0) ? (
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
                        const list = Array.isArray(result?.datasets) ? result.datasets : []
                        const matching = list.find(
                          (d) => String(d.datasetId) === String(datasetId),
                        )
                        const chosen = matching || list[0]
                        const targetDatasetId = chosen?.datasetId || datasetId
                        const evalResultId = chosen?.resultId ?? result?.resultId

                        const qs = new URLSearchParams()
                        if (evalResultId != null) qs.set('result_id', String(evalResultId))
                        if (sessionId) qs.set('session', String(sessionId))
                        const tail = qs.toString() ? `?${qs}` : ''
                        navigate(`/datasets/${targetDatasetId}/evaluate${tail}`)
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

                {/* ── Applied Configuration & Post-Generation Metric Guide ── */}
                <div className="mt-5 rounded-xl border border-brand-200/80 bg-gradient-to-r from-brand-50/60 via-indigo-50/30 to-brand-50/40 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Sparkles size={15} className="text-brand-600" />
                      <h4 className="text-xs font-semibold text-ink-900">
                        Configuration Applied: {selectedModel?.label || modelId}
                      </h4>
                    </div>
                    {lastAppliedParameters && Object.keys(lastAppliedParameters).length > 0 ? (
                      <span className="rounded-md bg-white border border-brand-200 px-2 py-0.5 text-[11px] font-mono text-brand-800 shadow-2xs">
                        {Object.entries(lastAppliedParameters)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(', ')}
                      </span>
                    ) : (
                      <span className="rounded-md bg-white border border-ink-200 px-2 py-0.5 text-[11px] text-ink-600 shadow-2xs">
                        Recommended Baseline Defaults
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-ink-600 leading-relaxed">
                    Generation is complete! Proceed to <strong>Evaluation</strong> to review how these settings influenced real metrics:
                    Statistical Similarity (marginal shapes), Correlations (column dependencies), ML Utility (downstream model power),
                    Business-Rule Validity (dates & stock constraints), and Privacy Duplicates.
                  </p>
                </div>

                {/* Sample rows of the generated data */}
                <GeneratedPreview
                  targets={
                    Array.isArray(result.datasets) && result.datasets.length > 0
                      ? result.datasets.map((d) => ({
                          resultId: d.resultId,
                          label: d.fileName || `Dataset ${d.datasetId}`,
                        }))
                      : [
                          {
                            resultId: result.resultId,
                            label: result.fileName || 'Generated dataset',
                          },
                        ]
                  }
                />

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