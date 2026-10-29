import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { generationApi } from '../api/generationApi.js'
import { useAuth } from './AuthContext.jsx'

/**
 * Global generation tracker ("the lift controller").
 *
 * One place owns the polling of /generation/status/{job_id}, so progress
 * keeps updating on every page, survives navigation and browser refreshes,
 * and any component (header pill, stage ladder, Generation page) can read it.
 *
 *   const { job, isActive, start, dismiss } = useGenerationTracker()
 *
 * job = {
 *   jobId, datasetId, modelLabel, sessionId, startedAt (ms),
 *   status: 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'FAILURE',
 *   progress: { stage, stage_label, stage_index, stage_total, stages,
 *               percent, stage_percent, message, attempt, max_attempts, ... },
 *   result, error, finishedAt, waitingHint
 * }
 *
 * Only one generation job is tracked at a time.
 */

const STORAGE_KEY = 'dx:activeJob'

const POLL_MS = 2000
const POLL_HIDDEN_MS = 6000
const MAX_BACKOFF_MS = 30000
// A job that never leaves PENDING usually means no Celery worker is running.
const WAITING_HINT_MS = 90 * 1000

const ACTIVE_STATES = new Set(['PENDING', 'PROGRESS'])

const GenerationTrackerContext = createContext(null)

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeStored(job) {
  try {
    if (job) localStorage.setItem(STORAGE_KEY, JSON.stringify(job))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage full or disabled — tracking still works in memory */
  }
}

export function GenerationTrackerProvider({ children }) {
  const { token } = useAuth()

  const [job, setJob] = useState(() => (token ? readStored() : null))
  const [connectionIssue, setConnectionIssue] = useState(false)

  const jobId = job?.jobId ?? null
  const active = !!job && ACTIVE_STATES.has(job.status)

  // Latest job for callbacks that must decide synchronously (see start()).
  const jobRef = useRef(job)
  jobRef.current = job

  // Keep localStorage in sync so a refresh can resume tracking.
  useEffect(() => {
    writeStored(job)
  }, [job])

  // Signed out (or token rejected): forget everything.
  useEffect(() => {
    if (!token) {
      setJob(null)
      setConnectionIssue(false)
    }
  }, [token])

  const applyStatus = useCallback((id, payload) => {
    setJob((prev) => {
      if (!prev || prev.jobId !== id) return prev
      const state = payload.status

      if (state === 'SUCCESS') {
        const now = Date.now()
        const elapsedMs = Number(prev.elapsedMs || 0) + (prev.resumedAt ? Math.max(0, now - prev.resumedAt) : 0)
        const stageElapsedMs = Number(prev.stageElapsedMs || 0) + (prev.stageResumedAt ? Math.max(0, now - prev.stageResumedAt) : 0)
        const total = prev.progress?.stage_total
        return {
          ...prev,
          status: 'SUCCESS',
          result: payload.result || payload,
          error: null,
          elapsedMs,
          resumedAt: null,
          stageElapsedMs,
          stageResumedAt: null,
          waitingHint: false,
          finishedAt: now,
          progress: {
            ...(prev.progress || {}),
            percent: 100,
            stage_percent: 100,
            ...(total ? { stage_index: total } : {}),
          },
        }
      }

      if (state === 'FAILURE') {
        const now = Date.now()
        const elapsedMs = Number(prev.elapsedMs || 0) + (prev.resumedAt ? Math.max(0, now - prev.resumedAt) : 0)
        const stageElapsedMs = Number(prev.stageElapsedMs || 0) + (prev.stageResumedAt ? Math.max(0, now - prev.stageResumedAt) : 0)
        return {
          ...prev,
          status: 'FAILURE',
          error: payload.error || 'Generation failed',
          elapsedMs,
          resumedAt: null,
          stageElapsedMs,
          stageResumedAt: null,
          waitingHint: false,
          finishedAt: now,
        }
      }

      if (state === 'PAUSED') {
        const now = Date.now()
        const elapsedMs = Number(prev.elapsedMs || 0) + (prev.resumedAt ? Math.max(0, now - prev.resumedAt) : 0)
        const stageElapsedMs = Number(prev.stageElapsedMs || 0) + (prev.stageResumedAt ? Math.max(0, now - prev.stageResumedAt) : 0)
        return {
          ...prev,
          status: 'PAUSED',
          elapsedMs,
          resumedAt: null,
          stageElapsedMs,
          stageResumedAt: null,
          pausedAt: now,
          pausing: false,
          progress: payload.progress || prev.progress,
          waitingHint: false,
        }
      }

      if (state === 'INTERRUPTED') {
        return {
          ...prev,
          status: 'INTERRUPTED',
          progress: payload.progress || prev.progress,
          waitingHint: false,
        }
      }

      if (state === 'CANCELLED') {
        return {
          ...prev,
          status: 'CANCELLED',
          waitingHint: false,
        }
      }

      if (state === 'PROGRESS' && payload.progress) {
        const now = Date.now()
        const nextProgress = payload.progress
        const nextStageKey = String(
          nextProgress.stage ?? nextProgress.stage_label ?? nextProgress.stage_index ?? 'starting',
        )
        const previousStageKey = prev.stageKey ?? String(
          prev.progress?.stage ?? prev.progress?.stage_label ?? prev.progress?.stage_index ?? 'starting',
        )
        const stageChanged = nextStageKey !== previousStageKey
        const stageElapsedMs = stageChanged ? 0 : Number(prev.stageElapsedMs || 0)
        return {
          ...prev,
          status: 'PROGRESS',
          // Overall active-time counter excludes pauses.
          resumedAt: prev.resumedAt || (prev.status === 'PAUSED' || !prev.resumedAt ? now : null),
          // Stage timer resets whenever the backend reports a new stage and excludes pauses.
          stageKey: nextStageKey,
          stageElapsedMs,
          stageResumedAt: prev.status === 'PAUSED' || stageChanged || !prev.stageResumedAt ? now : prev.stageResumedAt,
          progress: nextProgress,
          waitingHint: false,
        }
      }

      // PENDING (or PROGRESS without details yet)
      const status = prev.status === 'PROGRESS' ? 'PROGRESS' : 'PENDING'
      const waitingHint =
        status === 'PENDING' &&
        Date.now() - (prev.startedAt || Date.now()) > WAITING_HINT_MS

      // Nothing changed -> keep the same object (no re-render / storage write).
      if (prev.status === status && !!prev.waitingHint === waitingHint) {
        return prev
      }
      return { ...prev, status, waitingHint }
    })
  }, [])

  // The single polling loop. Restarts only when the job id or its
  // active/finished state changes — not on every progress update.
  useEffect(() => {
    if (!jobId || !active) return undefined

    let cancelled = false
    let timer = null
    let failures = 0

    const tick = async () => {
      try {
        const res = await generationApi.getStatus(jobId)
        if (cancelled) return
        failures = 0
        setConnectionIssue(false)

        const payload = res.data || {}
        applyStatus(jobId, payload)

        if (
          payload.status === 'SUCCESS' ||
          payload.status === 'FAILURE' ||
          payload.status === 'PAUSED' ||
          payload.status === 'INTERRUPTED' ||
          payload.status === 'CANCELLED'
        ) {
          return
        }
      } catch {
        if (cancelled) return
        failures += 1
        if (failures >= 3) setConnectionIssue(true)
      }

      const base = document.hidden ? POLL_HIDDEN_MS : POLL_MS
      const delay = failures
        ? Math.min(base * 2 ** failures, MAX_BACKOFF_MS)
        : base
      timer = setTimeout(tick, delay)
    }

    tick()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [jobId, active, applyStatus])

  /**
   * Begin tracking a freshly queued job.
   * Returns false if another job is still running.
   */
  const start = useCallback(
    ({ jobId: id, datasetId, modelLabel, sessionId }) => {
      if (!id) return false
      const current = jobRef.current
      if (current && ACTIVE_STATES.has(current.status)) return false

      setJob({
        jobId: id,
        datasetId: datasetId != null ? String(datasetId) : null,
        modelLabel: modelLabel || null,
        sessionId: sessionId != null ? String(sessionId) : null,
        startedAt: Date.now(),
        elapsedMs: 0,
        resumedAt: null,
        stageKey: null,
        stageElapsedMs: 0,
        stageResumedAt: null,
        pausedAt: null,
        status: 'PENDING',
        progress: null,
        result: null,
        error: null,
        waitingHint: false,
      })
      setConnectionIssue(false)
      return true
    },
    [],
  )

  /**
   * Follow a job that is already running on the backend (e.g. opened from
   * the Job History page, a deep link, or after localStorage was cleared).
   * Unlike start(), this replaces whatever job is currently tracked — the
   * previous one keeps running server-side, we just stop watching it.
   * No-op if this exact job is already being tracked.
   */
  const attach = useCallback(
    ({ jobId: id, datasetId, modelLabel, sessionId, startedAt }) => {
      if (!id) return false
      const current = jobRef.current
      if (current && current.jobId === id && ACTIVE_STATES.has(current.status)) {
        return true
      }

      const now = Date.now()
      const sameJob = current?.jobId === id
      setJob({
        ...(sameJob ? current : {}),
        jobId: id,
        datasetId: datasetId != null ? String(datasetId) : null,
        modelLabel: modelLabel || current?.modelLabel || null,
        sessionId: sessionId != null ? String(sessionId) : null,
        startedAt: sameJob ? current.startedAt : (startedAt || now),
        elapsedMs: sameJob ? Number(current.elapsedMs || 0) : 0,
        resumedAt: now,
        stageKey: sameJob ? current.stageKey ?? null : null,
        stageElapsedMs: sameJob ? Number(current.stageElapsedMs || 0) : 0,
        stageResumedAt: now,
        pausedAt: null,
        status: 'PENDING', // first poll corrects this to PROGRESS/SUCCESS/…
        progress: sameJob ? current.progress : null,
        result: null,
        error: null,
        waitingHint: false,
      })
      setConnectionIssue(false)
      return true
    },
    [],
  )

  /** Stop tracking / clear a finished job. */
  const dismiss = useCallback((id) => {
    setJob((prev) => {
      if (!prev) return prev
      if (id != null && prev.jobId !== id) return prev
      return null
    })
    setConnectionIssue(false)
  }, [])

  // Asks the backend to pause. The worker stops after its current batch and
  // saves a checkpoint, so we keep polling (status stays active, `pausing`
  // is true) until the backend itself reports PAUSED.
  // Returns { ok: boolean, error?: string } so the UI can show a message.
  const pause = useCallback(async (id) => {
    const targetId = id || jobRef.current?.jobId
    if (!targetId) return { ok: false, error: 'No job to pause.' }
    try {
      await generationApi.pauseJob(targetId)
      setJob((prev) =>
        prev && prev.jobId === targetId ? { ...prev, pausing: true } : prev,
      )
      return { ok: true }
    } catch (err) {
      return {
        ok: false,
        error:
          err?.response?.data?.detail ||
          err?.message ||
          'Could not pause this job.',
      }
    }
  }, [])

  const cancel = useCallback(async (id) => {
    const targetId = id || jobRef.current?.jobId
    if (!targetId) return
    try {
      await generationApi.cancelJob(targetId)
      setJob((prev) =>
        prev && prev.jobId === targetId ? { ...prev, status: 'CANCELLED' } : prev,
      )
    } catch {
      // ignore
    }
  }, [])

  const value = useMemo(
    () => ({
      job,
      isActive: active,
      isFinished: !!job && !active,
      connectionIssue,
      start,
      attach,
      dismiss,
      pause,
      cancel,
    }),
    [job, active, connectionIssue, start, attach, dismiss, pause, cancel],
  )

  return (
    <GenerationTrackerContext.Provider value={value}>
      {children}
    </GenerationTrackerContext.Provider>
  )
}

export function useGenerationTracker() {
  const ctx = useContext(GenerationTrackerContext)
  if (!ctx) {
    throw new Error(
      'useGenerationTracker must be used inside <GenerationTrackerProvider>',
    )
  }
  return ctx
}