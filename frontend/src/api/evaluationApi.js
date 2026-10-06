import apiClient from './client.js'

// Confirmed contract:
//   POST /evaluation { result_id: number }
//   → { status, message, data: { result_id, dataset_id,
//       evaluation: { metric, overall_score, evaluated_columns,
//         total_common_columns,
//         columns: { <name>: { column_type, status, category_count,
//                              metrics, score } } } } }

export const evaluationApi = {
  run: (resultId) =>
    apiClient.post(
      '/evaluation',
      { result_id: Number(resultId) },
      { timeout: 10 * 60 * 1000 },
    ),
}

export function normalizeEvaluation(raw) {
  if (!raw || typeof raw !== 'object') return null

  const d = raw.data && typeof raw.data === 'object' ? raw.data : raw
  const ev = d.evaluation && typeof d.evaluation === 'object' ? d.evaluation : d

  const rawCols =
    ev.columns && typeof ev.columns === 'object' && !Array.isArray(ev.columns)
      ? ev.columns
      : {}

  const columns = Object.entries(rawCols).map(([name, c]) => ({
    name,
    columnType: c?.column_type ?? null,
    status: c?.status ?? null,
    reason: c?.reason ?? null,
    categoryCount:
      typeof c?.category_count === 'number' ? c.category_count : null,
    metrics:
      c?.metrics && typeof c.metrics === 'object' ? { ...c.metrics } : {},
    score: typeof c?.score === 'number' ? c.score : null,
    raw: c,
  }))

  return {
    status: raw.status ?? null,
    message: raw.message ?? null,

    resultId: d.result_id ?? null,
    datasetId: d.dataset_id ?? null,

    metric: ev.metric ?? null,
    overallScore:
      typeof ev.overall_score === 'number' ? ev.overall_score : null,
    evaluatedColumns:
      typeof ev.evaluated_columns === 'number' ? ev.evaluated_columns : null,
    excludedColumns:
      typeof ev.excluded_columns === 'number' ? ev.excluded_columns : null,
    totalCommonColumns:
      typeof ev.total_common_columns === 'number'
        ? ev.total_common_columns
        : null,

    columns,
    raw,
  }
}

// ─────────────────────────────────────────────────────────────
// Category extraction
//
// The backend may return:
//   (a) a flat evaluation (metric: 'statistical_similarity')
//   (b) a composite with per-category keys
// Both are handled. Missing categories return null — no values
// are invented.
// ─────────────────────────────────────────────────────────────

export const CATEGORY_KEYS = [
  {
    key: 'statistical_similarity',
    label: 'Statistical Similarity',
    aliases: ['statistical', 'statistical_similarity', 'similarity'],
  },
  {
    key: 'data_quality',
    label: 'Data Quality',
    aliases: ['data_quality', 'quality', 'correlation_covariance', 'correlation'],
  },
  {
    key: 'ml_utility',
    label: 'ML Utility',
    aliases: ['ml_utility', 'utility', 'machine_learning_utility'],
  },
  {
    key: 'privacy',
    label: 'Privacy',
    aliases: ['privacy', 'privacy_metrics'],
  },
  {
    key: 'relationship_integrity',
    label: 'Relationship Integrity',
    aliases: [
      'relationship_integrity',
      'referential_integrity',
      'relationships',
      'integrity',
    ],
  },
]

function columnsFromMap(map) {
  if (!map || typeof map !== 'object' || Array.isArray(map)) return []
  return Object.entries(map).map(([name, c]) => ({
    name,
    columnType: c?.column_type ?? c?.columnType ?? null,
    status: c?.status ?? null,
    reason: c?.reason ?? null,
    categoryCount:
      typeof c?.category_count === 'number'
        ? c.category_count
        : typeof c?.categoryCount === 'number'
        ? c.categoryCount
        : null,
    metrics:
      c?.metrics && typeof c.metrics === 'object' ? { ...c.metrics } : {},
    score: typeof c?.score === 'number' ? c.score : null,
    raw: c,
  }))
}

function pickNumber(...vals) {
  for (const v of vals) {
    if (typeof v === 'number' && Number.isFinite(v)) return v
  }
  return null
}

function pickString(...vals) {
  for (const v of vals) {
    if (typeof v === 'string' && v.length) return v
  }
  return null
}

function buildSectionFromCategoryObject(cat, fallbackLabel, fallbackKey) {
  if (!cat || typeof cat !== 'object') return null

  const score = pickNumber(
    cat.overall_score,
    cat.score,
    cat.overallScore,
  )

  // Per-column detail
  let columns = []
  if (cat.columns) {
    columns = Array.isArray(cat.columns)
      ? cat.columns.map((c) => ({
          name: c?.column_name ?? c?.name ?? '—',
          columnType: c?.column_type ?? c?.columnType ?? null,
          status: c?.status ?? null,
          categoryCount: c?.category_count ?? c?.categoryCount ?? null,
          metrics:
            c?.metrics && typeof c.metrics === 'object' ? { ...c.metrics } : {},
          score: typeof c?.score === 'number' ? c.score : null,
          raw: c,
        }))
      : columnsFromMap(cat.columns)
  }

  // Free-form metrics — anything not columns/score
  const reserved = new Set([
    'columns',
    'overall_score',
    'score',
    'overallScore',
    'metric',
    'metrics',
  ])
  const extraMetrics = []
  const metricsSrc =
    cat.metrics && typeof cat.metrics === 'object' ? cat.metrics : cat
  for (const [k, v] of Object.entries(metricsSrc)) {
    if (reserved.has(k)) continue
    if (v == null) continue
    if (typeof v === 'object') continue
    extraMetrics.push({ label: k, value: v })
  }

  return {
    key: fallbackKey,
    label: pickString(cat.label, cat.metric, fallbackLabel),
    metricKey: pickString(cat.metric) || fallbackKey,
    score,
    evaluatedColumns:
      pickNumber(cat.evaluated_columns, cat.evaluatedColumns) ??
      (columns.length || null),
    totalCommonColumns:
      pickNumber(cat.total_common_columns, cat.totalCommonColumns) ?? null,
    columns,
    extraMetrics,
    raw: cat,
  }
}

/**
 * Turn a raw evaluation (from POST /evaluation) or an aggregated
 * dashboard payload into a map of available category sections.
 */
export function extractCategorySections(raw) {
  const out = {
    statistical_similarity: null,
    data_quality: null,
    ml_utility: null,
    privacy: null,
    relationship_integrity: null,
  }
  if (!raw || typeof raw !== 'object') return out

  const d = raw.data && typeof raw.data === 'object' ? raw.data : raw
  const ev =
    (d.evaluation && typeof d.evaluation === 'object' && d.evaluation) ||
    (d.metrics && typeof d.metrics === 'object' && d.metrics) ||
    (d.results && typeof d.results === 'object' && d.results) ||
    d

  if (!ev || typeof ev !== 'object') return out

  // Case (b): composite with category keys
  let anyComposite = false
  for (const cat of CATEGORY_KEYS) {
    for (const alias of cat.aliases) {
      if (ev[alias] && typeof ev[alias] === 'object') {
        const s = buildSectionFromCategoryObject(ev[alias], cat.label, cat.key)
        if (s) {
          out[cat.key] = s
          anyComposite = true
        }
        break
      }
    }
  }

  if (anyComposite) return out

  // Case (a): flat evaluation with a `metric` field
  const metricName = pickString(ev.metric, ev.metric_name)
  if (metricName) {
    const matched = CATEGORY_KEYS.find((c) =>
      c.aliases.includes(metricName.toLowerCase()),
    )
    const key = matched?.key || 'statistical_similarity'
    const label = matched?.label || 'Statistical Similarity'
    out[key] = buildSectionFromCategoryObject(ev, label, key)
  } else {
    // Unknown but column-rich — treat as statistical similarity
    if (ev.columns || ev.overall_score != null) {
      out.statistical_similarity = buildSectionFromCategoryObject(
        ev,
        'Statistical Similarity',
        'statistical_similarity',
      )
    }
  }

  return out
}

/**
 * Normalize the payload returned by GET /dashboard.
 * Returns an aggregate view: latest evaluation + history + stats.
 */
export function normalizeDashboardPayload(raw) {
  if (!raw || typeof raw !== 'object') {
    return {
      stats: {},
      latestEvaluation: null,
      history: [],
      categories: extractCategorySections({}),
    }
  }

  const d = raw.data && typeof raw.data === 'object' ? raw.data : raw

  const num = (...keys) => {
    for (const k of keys) {
      if (typeof d[k] === 'number') return d[k]
    }
    return null
  }

  const arr = (...keys) => {
    for (const k of keys) {
      if (Array.isArray(d[k])) return d[k]
    }
    return []
  }

  // Latest evaluation — try several keys
  const latest =
    d.latest_evaluation ||
    d.latestEvaluation ||
    d.last_evaluation ||
    (Array.isArray(d.evaluations) && d.evaluations.length
      ? d.evaluations[0]
      : null) ||
    (d.evaluation && typeof d.evaluation === 'object' ? d.evaluation : null) ||
    null

  const history = arr(
    'evaluations',
    'recent_evaluations',
    'history',
    'runs',
    'results',
  )

  const stats = {
    totalEvaluations: num(
      'total_evaluations',
      'evaluations_count',
      'evaluation_count',
    ),
    totalDatasets: num('total_datasets', 'datasets_count', 'dataset_count'),
    totalGenerations: num(
      'total_generations',
      'generations_count',
      'generation_count',
    ),
    averageScore: num('average_score', 'avg_score', 'overall_score'),
  }

  return {
    stats,
    latestEvaluation: latest,
    history,
    categories: extractCategorySections(
      latest ? { data: { evaluation: latest } } : {},
    ),
    raw,
  }
}