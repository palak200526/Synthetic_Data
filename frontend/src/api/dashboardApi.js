import apiClient from './client.js'
import { listLocalDatasets } from '../utils/batchStore.js'

export const dashboardApi = {
  get: () => apiClient.get('/dashboard'),
}

/**
 * Normalize /dashboard without inventing any values.
 * Every missing field returns null / [] so the UI can render a
 * placeholder instead of a fake number.
 */
export function normalizeDashboard(raw) {
  const empty = {
    stats: {
      datasets: null,
      generations: null,
      evaluations: null,
      avgScore: null,
    },
    recentDatasets: [],
    recentGenerations: [],
    recentEvaluations: [],
  }

  if (!raw || typeof raw !== 'object') return empty

  const d = raw.data && typeof raw.data === 'object' ? raw.data : raw

  const num = (...keys) => {
    for (const k of keys) {
      const v = d[k]
      if (typeof v === 'number') return v
    }
    return null
  }

  const arr = (...keys) => {
    for (const k of keys) {
      const v = d[k]
      if (Array.isArray(v)) return v
    }
    return []
  }

  return {
    stats: {
      datasets:    num('total_datasets', 'datasets_count', 'dataset_count'),
      generations: num('total_generations', 'generations_count', 'generation_count'),
      evaluations: num('total_evaluations', 'evaluations_count', 'evaluation_count'),
      avgScore:    num('average_score', 'avg_score', 'overall_score'),
    },
    recentDatasets:    arr('recent_datasets', 'datasets', 'recentDatasets'),
    recentGenerations: arr('recent_generations', 'generations', 'recentGenerations'),
    recentEvaluations: arr('recent_evaluations', 'evaluations', 'recentEvaluations'),
  }
}

/**
 * Fold locally-known upload batches into the dashboard's recent
 * datasets list. This is what makes a multi-file upload show up on
 * the dashboard immediately, without needing a /datasets endpoint.
 *
 * Rules:
 *   - Backend entries win on id collision (they're assumed richer).
 *   - Local-only entries are appended.
 *   - Result is sorted newest-first.
 *   - Nothing is fabricated: only datasets the user actually
 *     uploaded in this browser are added.
 */
export function mergeLocalDatasets(normalized) {
  if (!normalized) return normalized

  const local = listLocalDatasets()
  if (local.length === 0) return normalized

  const byId = new Map()

  // Local first so backend can override.
  for (const d of local) {
    if (d?.id == null) continue
    byId.set(String(d.id), d)
  }

  for (const d of normalized.recentDatasets || []) {
    const id = d?.id ?? d?.dataset_id
    if (id == null) continue
    byId.set(String(id), { ...d, source: 'backend' })
  }

  const merged = Array.from(byId.values()).sort((a, b) => {
    const ta = Date.parse(a?.created_at || a?.uploaded_at || '')
    const tb = Date.parse(b?.created_at || b?.uploaded_at || '')
    const aOk = !Number.isNaN(ta)
    const bOk = !Number.isNaN(tb)
    if (aOk && bOk) return tb - ta
    if (aOk) return -1
    if (bOk) return 1
    const ia = Number(a?.id ?? a?.dataset_id ?? 0)
    const ib = Number(b?.id ?? b?.dataset_id ?? 0)
    return ib - ia
  })

  return {
    ...normalized,
    recentDatasets: merged,
  }
}