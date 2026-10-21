import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  History,
  Play,
  RotateCcw,
  Trash2,
  Pause,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  Search,
  ExternalLink,
  Cpu,
  Layers,
  Database,
  Calendar,
  Download,
  AlertCircle,
  X,
  FileText,
  Sliders,
  ChevronRight,
  Loader2,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Toast from '../components/Toast.jsx'
import { generationApi } from '../api/generationApi.js'
import { useGenerationTracker } from '../context/GenerationTrackerContext.jsx'
import { formatNumber } from '../utils/format.js'
import { getErrorMessage } from '../utils/errors.js'

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
function formatDateTime(value) {
  const d = parseServerDate(value)
  return d ? d.toLocaleString() : '—'
}
function formatTime(value) {
  const d = parseServerDate(value)
  return d ? d.toLocaleTimeString() : '—'
}

function isMultiTableJob(job) {
  const fileName = String(job?.file_name || '').toLowerCase()
  const modelName = String(job?.model_name || '').toLowerCase()
  const stage = String(job?.stage || '').toLowerCase()
  return fileName.includes('multi-table group') || modelName.includes('_group_') || stage.includes('multi-table')
}

export default function GenerationHistory() {
  const navigate = useNavigate()
  const tracker = useGenerationTracker()

  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('all') // 'all' | 'running' | 'incomplete' | 'completed' | 'failed'
  const [searchQuery, setSearchQuery] = useState('')
  const [toast, setToast] = useState(null)
  const [actionInProgress, setActionInProgress] = useState({})

  // Jobs the user asked to pause. Pause is cooperative: the worker only stops
  // between batches, so the job stays "running" for a while. We remember the
  // request (also across page navigation) to show "Pausing…" until the backend
  // confirms. { [jobId]: requestedAtMs }
  const [pausingJobs, setPausingJobs] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('dx:pausingJobs') || '{}') || {}
    } catch {
      return {}
    }
  })
  useEffect(() => {
    try {
      sessionStorage.setItem('dx:pausingJobs', JSON.stringify(pausingJobs))
    } catch {
      /* ignore */
    }
  }, [pausingJobs])
  const [, forceTick] = useState(0)

  // Modal states
  const [errorModalJob, setErrorModalJob] = useState(null)
  const [confirmDiscardJob, setConfirmDiscardJob] = useState(null)

  const fetchJobs = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true)
      setError('')
      const res = await generationApi.listJobs({ limit: 150 })
      setJobs(res?.data?.jobs || [])
    } catch (err) {
      if (!silent) setError(getErrorMessage(err))
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  // Periodic poll if any job is currently running or pending
  useEffect(() => {
    const hasRunning = jobs.some(
      (j) => j.status?.toLowerCase() === 'running' || j.status?.toLowerCase() === 'pending',
    )
    if (!hasRunning) return undefined

    const timer = setInterval(() => {
      fetchJobs(true)
    }, 3000)

    return () => clearInterval(timer)
  }, [jobs, fetchJobs])

  useEffect(() => {
    const ids = Object.keys(pausingJobs)
    if (ids.length === 0 || jobs.length === 0) return
    const byId = new Map(jobs.map((j) => [j.job_id, j]))
    const done = []
    for (const id of ids) {
      const j = byId.get(id)
      const st = (j?.status || '').toLowerCase()
      if (!j || (st !== 'running' && st !== 'pending')) {
        done.push(id)
        if (st === 'paused') {
          setToast({
            type: 'success',
            title: 'Generation Paused',
            message: `${j.file_name} paused at ${formatNumber(j.generated_rows || 0)} rows. Use Resume to continue.`,
          })
        }
      }
    }
    if (done.length) {
      setPausingJobs((prev) => {
        const next = { ...prev }
        done.forEach((id) => delete next[id])
        return next
      })
    }
  }, [jobs]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-render every few seconds while pausing so the "still waiting" hint appears.
  useEffect(() => {
    if (Object.keys(pausingJobs).length === 0) return undefined
    const t = setInterval(() => forceTick((n) => n + 1), 5000)
    return () => clearInterval(t)
  }, [pausingJobs])

  const setBusy = (id, busy) => {
    setActionInProgress((prev) => ({ ...prev, [id]: busy }))
  }

  // ── Actions ───────────────────────────────────────────────────

  const handleResume = async (job) => {
    setBusy(job.job_id, true)
    try {
      await generationApi.resumeJob(job.job_id)
      tracker.attach({
        jobId: job.job_id,
        datasetId: job.dataset_id,
        modelLabel: job.model_name,
      })
      setToast({
        type: 'success',
        title: 'Generation Resumed',
        message: `Resuming generation for ${job.file_name} from checkpoint.`,
      })
      await fetchJobs(true)
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Resume Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setBusy(job.job_id, false)
    }
  }

  const handlePause = async (job) => {
    if (pausingJobs[job.job_id]) return
    setBusy(job.job_id, true)
    try {
      // If the global tracker is following this job, go through it so the
      // Generation page also shows "Pausing…".
      if (tracker.job?.jobId === job.job_id) {
        const res = await tracker.pause(job.job_id)
        if (!res?.ok) throw new Error(res?.error || 'Could not pause this job.')
      } else {
        await generationApi.pauseJob(job.job_id)
      }
      setPausingJobs((prev) => ({ ...prev, [job.job_id]: Date.now() }))
      setToast({
        type: 'info',
        title: 'Pausing…',
        message: `${job.file_name} will stop after the current batch and save a checkpoint.`,
      })
      await fetchJobs(true)
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Pause Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setBusy(job.job_id, false)
    }
  }

  const handleRestart = async (job) => {
    const confirmed = window.confirm(
      `Restart generation for "${job.file_name}" from row 0?\n\nThis will clear the current batch checkpoint and start generation from the beginning.`,
    )
    if (!confirmed) return

    setBusy(job.job_id, true)
    try {
      await generationApi.restartJob(job.job_id)
      tracker.attach({
        jobId: job.job_id,
        datasetId: job.dataset_id,
        modelLabel: job.model_name,
      })
      setToast({
        type: 'info',
        title: 'Generation Restarted',
        message: `Restarted from row 0 for ${job.file_name}.`,
      })
      await fetchJobs(true)
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Restart Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setBusy(job.job_id, false)
    }
  }

  const executeDiscard = async (job) => {
    setConfirmDiscardJob(null)
    setBusy(job.job_id, true)
    try {
      await generationApi.discardJob(job.job_id)
      setToast({
        type: 'info',
        title: 'Job Discarded',
        message: `Cleaned up checkpoints and removed job record for ${job.file_name}.`,
      })
      await fetchJobs(true)
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Discard Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setBusy(job.job_id, false)
    }
  }

  const handleDownload = async (job) => {
    if (!job.result_id) {
      setToast({
        type: 'error',
        title: 'Download Unavailable',
        message: 'No result ID found for this completed generation job.',
      })
      return
    }
    setBusy(job.job_id, true)
    try {
      if (isMultiTableJob(job)) {
        await generationApi.downloadMultiTableDataset(job.result_id)
        setToast({
          type: 'success',
          title: 'Download Complete',
          message: `Downloaded all generated tables for ${job.file_name || 'this multi-table group'} as a ZIP file.`,
        })
      } else {
        await generationApi.downloadDataset(job.result_id, job.file_name || 'synthetic_dataset.csv')
        setToast({
          type: 'success',
          title: 'Download Complete',
          message: `Saved ${job.file_name || 'dataset'}.`,
        })
      }
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Download Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setBusy(job.job_id, false)
    }
  }

  // Open the Generation page for this job so the user can watch it live.
  const openLiveProgress = (job) => {
    tracker.attach({
      jobId: job.job_id,
      datasetId: job.dataset_id,
      modelLabel: job.model_name,
      startedAt: parseServerDate(job.created_at)?.getTime(),
    })
    navigate(`/datasets/${job.dataset_id}/generate?job_id=${job.job_id}`)
  }

  // ── Segregation into 4 required categories ───────────────────

  const categorized = useMemo(() => {
    const inProgress = []
    const pausedInterrupted = []
    const completed = []
    const failed = []

    const q = searchQuery.toLowerCase().trim()
    const matchesSearch = (j) =>
      !q ||
      j.file_name?.toLowerCase().includes(q) ||
      j.model_name?.toLowerCase().includes(q) ||
      j.job_id?.toLowerCase().includes(q)

    for (const j of jobs) {
      if (!matchesSearch(j)) continue
      const status = (j.status || '').toLowerCase()
      if (status === 'running' || status === 'pending') {
        inProgress.push(j)
      } else if (status === 'paused' || status === 'interrupted') {
        pausedInterrupted.push(j)
      } else if (status === 'completed') {
        completed.push(j)
      } else {
        // 'failed' or 'cancelled'
        failed.push(j)
      }
    }

    return { inProgress, pausedInterrupted, completed, failed }
  }, [jobs, searchQuery])

  const totalCount = jobs.length
  const inProgressCount = categorized.inProgress.length
  const incompleteCount = categorized.pausedInterrupted.length
  const completedCount = categorized.completed.length
  const failedCount = categorized.failed.length

  // Render Job Card Component
  const renderJobCard = (job, category) => {
    const statusKey = (job.status || 'pending').toLowerCase()
    const isRunning = statusKey === 'running' || statusKey === 'pending'
    const isPaused = statusKey === 'paused'
    const isInterrupted = statusKey === 'interrupted'
    const isCompleted = statusKey === 'completed'
    const isFailed = statusKey === 'failed'
    const isCancelled = statusKey === 'cancelled'

    const busy = !!actionInProgress[job.job_id]
    const pauseRequestedAt = pausingJobs[job.job_id]
    const isPausing = isRunning && !!pauseRequestedAt
    const pausingFor = isPausing ? Math.floor((Date.now() - pauseRequestedAt) / 1000) : 0
    const pct = Math.min(100, Math.max(0, Number(job.progress_percent || 0)))

    // Check if tracker is currently actively running this same job
    const isCurrentlyTrackedRunning =
      tracker.isActive && tracker.job?.jobId === job.job_id && isRunning

    return (
      <div
        key={job.job_id}
        onClick={isRunning ? () => openLiveProgress(job) : undefined}
        onKeyDown={
          isRunning
            ? (e) => {
                if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault()
                  openLiveProgress(job)
                }
              }
            : undefined
        }
        role={isRunning ? 'link' : undefined}
        tabIndex={isRunning ? 0 : undefined}
        title={isRunning ? 'Open live generation progress' : undefined}
        className={[
          'rounded-xl border bg-white p-5 shadow-xs transition-all',
          isRunning
            ? 'cursor-pointer border-brand-300 ring-2 ring-brand-100 bg-brand-50/10 hover:ring-brand-200 hover:shadow-md'
            : isPaused || isInterrupted
              ? 'border-amber-300 bg-amber-50/20'
              : isFailed
                ? 'border-rose-200 bg-rose-50/10'
                : 'border-ink-200',
        ].join(' ')}
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {/* Main Info */}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-sm text-ink-900">
                {job.file_name}
              </span>
              <StatusBadge status={job.status} />
              <span className="rounded bg-ink-100 px-2 py-0.5 font-mono text-[11px] text-ink-600">
                {job.model_name?.toUpperCase()}
              </span>
              {job.llm_model && (
                <span className="rounded bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                  LLM: {job.llm_model}
                </span>
              )}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-500">
              <span className="font-mono text-[11px]">ID: {job.job_id.slice(0, 8)}</span>
              <span>Dataset ID: {job.dataset_id}</span>
              {job.created_at && (
                <span>Started: {formatDateTime(job.created_at)}</span>
              )}
              {job.last_checkpoint_at && (
                <span className="text-amber-800 font-medium">
                  Last Saved Checkpoint: {formatTime(job.last_checkpoint_at)}
                </span>
              )}
            </div>

            {/* Progress details */}
            <div className="mt-3.5">
              <div className="flex items-center justify-between text-xs font-medium text-ink-700">
                <span>
                  Generated:{' '}
                  <strong className="text-ink-900 font-semibold">
                    {formatNumber(job.generated_rows || 0)}
                  </strong>{' '}
                  / {formatNumber(job.total_rows || 0)} rows
                  {job.remaining_rows > 0 && (
                    <span className="ml-1.5 font-normal text-ink-500">
                      ({formatNumber(job.remaining_rows)} remaining)
                    </span>
                  )}
                  {job.total_batches > 0 && (
                    <span className="ml-2 rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-600">
                      Batch {job.current_batch} of {job.total_batches}
                    </span>
                  )}
                </span>
                <span className="font-bold text-ink-900">{pct}%</span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-ink-100">
                <div
                  className={[
                    'h-full transition-all duration-300',
                    isCompleted
                      ? 'bg-emerald-500'
                      : isPaused || isInterrupted
                        ? 'bg-amber-500'
                        : isFailed
                          ? 'bg-rose-500'
                          : 'bg-brand-600',
                  ].join(' ')}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>

            {/* Stage message / error snippet */}
            {job.stage_message && (
              <p className="mt-2 text-xs text-ink-600">
                <span className="font-medium text-ink-700">Status:</span> {job.stage_message}
              </p>
            )}
            {isPausing && (
              <p className="mt-2 flex items-start gap-1.5 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                <Loader2 size={12} className="mt-0.5 shrink-0 animate-spin" />
                <span>
                  Pause requested — stops after the current batch and saves a checkpoint.
                  {pausingFor >= 60 &&
                    ' Still finishing the current step: pause is only applied between batches, so model training or text-column writing must complete first.'}
                </span>
              </p>
            )}
            {job.error_message && (
              <div className="mt-2 flex items-center justify-between rounded bg-rose-50 p-2 text-xs font-medium text-rose-700">
                <span className="truncate max-w-xl">Error: {job.error_message}</span>
                <button
                  className="ml-2 font-semibold underline text-rose-800 hover:text-rose-900 shrink-0"
                  onClick={() => setErrorModalJob(job)}
                >
                  View Error Details
                </button>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div
            className="flex flex-wrap items-center gap-2 lg:flex-nowrap shrink-0"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Incomplete / Paused / Interrupted Buttons */}
            {(isPaused || isInterrupted) && (
              <>
                <button
                  className="dx-btn-primary"
                  disabled={busy || isCurrentlyTrackedRunning}
                  onClick={() => handleResume(job)}
                  title="Continue generation from last saved checkpoint"
                >
                  <Play size={13} className="fill-current" /> ▶ Resume Generation
                </button>
                <button
                  className="dx-btn-secondary"
                  disabled={busy}
                  onClick={() => handleRestart(job)}
                  title="Confirm and restart generation from row 0"
                >
                  <RotateCcw size={13} /> ↻ Restart from Beginning
                </button>
                <button
                  className="dx-btn-ghost text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                  disabled={busy}
                  onClick={() => setConfirmDiscardJob(job)}
                  title="Discard incomplete job and delete checkpoints"
                >
                  <Trash2 size={13} /> ✕ Discard Job
                </button>
              </>
            )}

            {/* In Progress Buttons */}
            {isRunning && (
              <>
                <button
                  className="dx-btn-primary"
                  onClick={() => openLiveProgress(job)}
                  title="Open the Generation page and watch this job live"
                >
                  <ExternalLink size={13} /> View Live Progress
                </button>
                <button
                  className="dx-btn-secondary whitespace-nowrap border-amber-300 bg-amber-50/50 text-amber-900 hover:bg-amber-100 disabled:opacity-70"
                  disabled={busy || isPausing}
                  onClick={() => handlePause(job)}
                  title={
                    isPausing
                      ? 'Pause requested — waiting for the current batch to finish'
                      : 'Pause active generation and save checkpoint'
                  }
                >
                  {busy || isPausing ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Pause size={13} />
                  )}
                  {isPausing ? 'Pausing…' : 'Pause'}
                </button>
                <button
                  className="dx-btn-ghost text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                  disabled={busy}
                  onClick={() => setConfirmDiscardJob(job)}
                  title="Cancel and discard running generation"
                >
                  <XCircle size={13} /> Cancel & Discard
                </button>
              </>
            )}

            {/* Completed Buttons */}
            {isCompleted && (
              <>
                {job.result_id && (
                  <button
                    className="dx-btn-secondary"
                    onClick={() =>
                      navigate(
                        `/datasets/${job.dataset_id}/evaluate?result_id=${job.result_id}`,
                      )
                    }
                    title="View evaluation metrics and statistical analysis"
                  >
                    <ExternalLink size={13} /> View Results
                  </button>
                )}
                {job.result_id && (
                  <button
                    className="dx-btn-primary"
                    disabled={busy}
                    onClick={() => handleDownload(job)}
                    title={isMultiTableJob(job) ? 'Download every generated table in this group as one ZIP file' : 'Download generated synthetic dataset CSV'}
                  >
                    <Download size={13} /> {isMultiTableJob(job) ? 'Download All Tables' : 'Download Dataset'}
                  </button>
                )}
                <button
                  className="dx-btn-ghost text-ink-400 hover:text-rose-600"
                  disabled={busy}
                  onClick={() => setConfirmDiscardJob(job)}
                  title="Delete job history"
                >
                  <Trash2 size={13} />
                </button>
              </>
            )}

            {/* Failed Buttons */}
            {(isFailed || isCancelled) && (
              <>
                <button
                  className="dx-btn-secondary"
                  disabled={busy}
                  onClick={() => handleRestart(job)}
                  title="Retry generation from the beginning"
                >
                  <RotateCcw size={13} /> Retry / Restart
                </button>
                {job.error_message && (
                  <button
                    className="dx-btn-ghost text-ink-700 hover:bg-ink-100"
                    onClick={() => setErrorModalJob(job)}
                    title="View error information"
                  >
                    <AlertCircle size={13} /> View Error
                  </button>
                )}
                <button
                  className="dx-btn-ghost text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                  disabled={busy}
                  onClick={() => setConfirmDiscardJob(job)}
                  title="Discard job record"
                >
                  <Trash2 size={13} /> Discard
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Generation History & Checkpoints"
        subtitle="Manage persistent synthetic data generation runs. Monitor progress, safely pause active runs, and resume interrupted jobs directly from saved checkpoints."
        actions={
          <button
            className="dx-btn-secondary"
            onClick={() => fetchJobs(false)}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh Runs
          </button>
        }
      />

      {toast && (
        <Toast
          open
          type={toast.type}
          title={toast.title}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      {/* Top Stat Cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="In Progress"
          value={formatNumber(inProgressCount)}
          hint="Active running / queued"
        />
        <StatCard
          label="Paused / Interrupted"
          value={formatNumber(incompleteCount)}
          hint="Ready to resume from checkpoint"
        />
        <StatCard
          label="Completed"
          value={formatNumber(completedCount)}
          hint="Datasets generated"
        />
        <StatCard
          label="Failed / Cancelled"
          value={formatNumber(failedCount)}
          hint="Requires retry or discard"
        />
      </div>

      {/* Navigation Filter Tabs & Search */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1 rounded-lg bg-ink-100 p-1">
          {[
            { id: 'all', label: `All Sections (${totalCount})` },
            { id: 'incomplete', label: `Paused / Interrupted (${incompleteCount})` },
            { id: 'running', label: `In Progress (${inProgressCount})` },
            { id: 'completed', label: `Completed (${completedCount})` },
            { id: 'failed', label: `Failed (${failedCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={[
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                activeTab === tab.id
                  ? 'bg-white text-ink-900 shadow-xs'
                  : 'text-ink-600 hover:text-ink-900',
              ].join(' ')}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative max-w-xs flex-1">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search filename or model…"
            className="dx-input pl-8"
          />
        </div>
      </div>

      {/* Content Rendering by Category */}
      {totalCount === 0 && !loading ? (
        <EmptyState
          icon={History}
          title="No generation jobs found"
          description="You haven't run any synthetic data generation jobs yet. Start a generation to track batch checkpoints and resumption."
          action={
            <button
              className="dx-btn-primary mt-2"
              onClick={() => navigate('/datasets')}
            >
              <Cpu size={14} /> Go to Datasets
            </button>
          }
        />
      ) : (
        <div className="space-y-8">
          {/* 1. IN PROGRESS SECTION */}
          {(activeTab === 'all' || activeTab === 'running') && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-brand-600 animate-pulse" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-ink-900">
                    In Progress ({categorized.inProgress.length})
                  </h2>
                </div>
                <span className="text-xs text-ink-500">Live batch generation actively executing</span>
              </div>

              {categorized.inProgress.length === 0 ? (
                <div className="rounded-lg border border-dashed border-ink-200 bg-white p-6 text-center text-xs text-ink-500">
                  No generation jobs currently in progress.
                </div>
              ) : (
                <div className="space-y-3">
                  {categorized.inProgress.map((j) => renderJobCard(j, 'running'))}
                </div>
              )}
            </section>
          )}

          {/* 2. PAUSED / INTERRUPTED SECTION */}
          {(activeTab === 'all' || activeTab === 'incomplete') && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-ink-900">
                    Paused / Interrupted ({categorized.pausedInterrupted.length})
                  </h2>
                </div>
                <span className="text-xs text-amber-800 font-medium">
                  Checkpoints saved — click Resume Generation to continue without duplicating work
                </span>
              </div>

              {categorized.pausedInterrupted.length === 0 ? (
                <div className="rounded-lg border border-dashed border-ink-200 bg-white p-6 text-center text-xs text-ink-500">
                  No paused or interrupted generation jobs. All jobs are either complete or running.
                </div>
              ) : (
                <div className="space-y-3">
                  {categorized.pausedInterrupted.map((j) =>
                    renderJobCard(j, 'incomplete'),
                  )}
                </div>
              )}
            </section>
          )}

          {/* 3. COMPLETED SECTION */}
          {(activeTab === 'all' || activeTab === 'completed') && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-ink-900">
                    Completed ({categorized.completed.length})
                  </h2>
                </div>
                <span className="text-xs text-ink-500">
                  Ready to view evaluation metrics and download generated datasets
                </span>
              </div>

              {categorized.completed.length === 0 ? (
                <div className="rounded-lg border border-dashed border-ink-200 bg-white p-6 text-center text-xs text-ink-500">
                  No completed generation jobs yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {categorized.completed.map((j) => renderJobCard(j, 'completed'))}
                </div>
              )}
            </section>
          )}

          {/* 4. FAILED SECTION */}
          {(activeTab === 'all' || activeTab === 'failed') && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-ink-900">
                    Failed & Cancelled ({categorized.failed.length})
                  </h2>
                </div>
                <span className="text-xs text-ink-500">
                  Inspect failure reasons, retry, or discard job records
                </span>
              </div>

              {categorized.failed.length === 0 ? (
                <div className="rounded-lg border border-dashed border-ink-200 bg-white p-6 text-center text-xs text-ink-500">
                  No failed or cancelled generation jobs.
                </div>
              ) : (
                <div className="space-y-3">
                  {categorized.failed.map((j) => renderJobCard(j, 'failed'))}
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {/* Confirmation Discard Modal */}
      {confirmDiscardJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-100 text-rose-600">
                <Trash2 size={20} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-ink-900">
                  Discard Generation Job?
                </h3>
                <p className="text-xs text-ink-500">
                  This action cannot be undone.
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-lg bg-ink-50 p-3 text-xs text-ink-700">
              <p>
                <strong>File:</strong> {confirmDiscardJob.file_name}
              </p>
              <p className="mt-1">
                <strong>Progress:</strong> {confirmDiscardJob.generated_rows || 0} /{' '}
                {confirmDiscardJob.total_rows || 0} rows ({confirmDiscardJob.progress_percent || 0}%)
              </p>
              <p className="mt-2 text-rose-700">
                Discarding will permanently delete saved batch checkpoints and cancel any active background process.
              </p>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                className="dx-btn-secondary"
                onClick={() => setConfirmDiscardJob(null)}
              >
                Keep Job
              </button>
              <button
                className="dx-btn-primary bg-rose-600 hover:bg-rose-700"
                onClick={() => executeDiscard(confirmDiscardJob)}
              >
                Yes, Discard Job
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Error Details Modal */}
      {errorModalJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-100 text-rose-600">
                  <AlertCircle size={18} />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-ink-900">
                    Generation Failure Details
                  </h3>
                  <p className="text-xs text-ink-500">
                    Job ID: {errorModalJob.job_id}
                  </p>
                </div>
              </div>
              <button
                className="text-ink-400 hover:text-ink-700"
                onClick={() => setErrorModalJob(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <div className="rounded-lg bg-ink-50 p-3 text-xs text-ink-700">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-ink-400">File:</span>{' '}
                    <strong>{errorModalJob.file_name}</strong>
                  </div>
                  <div>
                    <span className="text-ink-400">Algorithm:</span>{' '}
                    <strong>{errorModalJob.model_name?.toUpperCase()}</strong>
                  </div>
                  <div>
                    <span className="text-ink-400">Rows Saved:</span>{' '}
                    <strong>{errorModalJob.generated_rows || 0} rows</strong>
                  </div>
                  <div>
                    <span className="text-ink-400">Stage:</span>{' '}
                    <strong>{errorModalJob.stage || 'unknown'}</strong>
                  </div>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-ink-700">
                  Error Details:
                </label>
                <div className="mt-1 max-h-48 overflow-y-auto rounded-lg border border-rose-200 bg-rose-50 p-3 font-mono text-xs text-rose-800">
                  {errorModalJob.error_message || 'No additional error details recorded.'}
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                className="dx-btn-secondary"
                onClick={() => setErrorModalJob(null)}
              >
                Close
              </button>
              <button
                className="dx-btn-primary"
                onClick={() => {
                  setErrorModalJob(null)
                  handleRestart(errorModalJob)
                }}
              >
                <RotateCcw size={13} /> Retry from Beginning
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}