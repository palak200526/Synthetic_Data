const KEY_PREFIX = 'datrixa.batch.'
const LAST_KEY = 'datrixa.batch.last'

export function saveBatch(sessionId, batch) {
  if (sessionId == null) return
  try {
    localStorage.setItem(KEY_PREFIX + sessionId, JSON.stringify(batch))
    localStorage.setItem(LAST_KEY, String(sessionId))
  } catch {
    /* storage full or disabled — non-fatal */
  }
}

export function loadBatch(sessionId) {
  if (sessionId == null) return []
  try {
    const raw = localStorage.getItem(KEY_PREFIX + sessionId)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function getLastSessionId() {
  try {
    return localStorage.getItem(LAST_KEY)
  } catch {
    return null
  }
}

export function clearBatch(sessionId) {
  try {
    localStorage.removeItem(KEY_PREFIX + sessionId)
    if (localStorage.getItem(LAST_KEY) === String(sessionId)) {
      localStorage.removeItem(LAST_KEY)
    }
  } catch {
    /* noop */
  }
}

export function clearAllBatches() {
  try {
    const keys = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith(KEY_PREFIX)) keys.push(k)
    }
    for (const k of keys) localStorage.removeItem(k)
    localStorage.removeItem(LAST_KEY)
  } catch {
    /* noop */
  }
}

function latestUploadMs(datasets) {
  let best = null
  for (const d of datasets || []) {
    const t = d?.uploadDate || d?.upload_date
    if (!t) continue
    const ms = Date.parse(t)
    if (!Number.isNaN(ms) && (best == null || ms > best)) best = ms
  }
  return best
}

/**
 * All batches stored in this browser, newest first.
 * Returns [{ sessionId, datasets: [...] }].
 */
export function listAllBatches() {
  const out = []
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key || !key.startsWith(KEY_PREFIX)) continue

      const sessionId = key.slice(KEY_PREFIX.length)
      const raw = localStorage.getItem(key)
      if (!raw) continue

      let datasets
      try {
        datasets = JSON.parse(raw)
      } catch {
        continue
      }
      if (!Array.isArray(datasets) || datasets.length === 0) continue

      const sorted = [...datasets].sort(
        (a, b) => (Number(a?.id) || 0) - (Number(b?.id) || 0),
      )
      out.push({ sessionId, datasets: sorted })
    }
  } catch {
    return []
  }

  out.sort((a, b) => {
    const da = latestUploadMs(a.datasets)
    const db = latestUploadMs(b.datasets)
    if (da != null && db != null) return db - da
    if (da != null) return -1
    if (db != null) return 1
    return Number(b.sessionId || 0) - Number(a.sessionId || 0)
  })

  return out
}

/**
 * Flat list of every dataset the user has uploaded in this browser,
 * newest first. Each entry is shaped like what the /dashboard
 * endpoint returns, so it can be merged into "recent datasets".
 */
export function listLocalDatasets() {
  const batches = listAllBatches()
  const flat = []
  for (const b of batches) {
    for (const d of b.datasets) {
      if (d?.id == null) continue
      flat.push({
        id: d.id,
        dataset_id: d.id,
        name: d.fileName || `Dataset ${d.id}`,
        filename: d.fileName || null,
        stored_file_name: d.storedFileName || null,
        rows: d.rows ?? null,
        columns: d.columns ?? null,
        created_at: d.uploadDate || null,
        uploaded_at: d.uploadDate || null,
        session_id: b.sessionId,
        source: 'local',
      })
    }
  }
  return flat
}