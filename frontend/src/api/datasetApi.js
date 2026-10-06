import apiClient from './client.js'

// ─────────────────────────────────────────────────────────────
// Confirmed backend contract:
//   POST /upload             multipart/form-data
//                            fields: files (array, required)
//                                    group_id?, domain_type?
//   GET  /profile/{id}       dataset_id is an INTEGER
//   POST /preprocess/{id}    body TBD (sent as empty)
// ─────────────────────────────────────────────────────────────

const FILE_FIELD = 'files'

export const SUPPORTED_EXTENSIONS = ['csv', 'xlsx', 'xls']
export const ACCEPT_ATTR = '.csv,.xlsx,.xls,text/csv'

export function isSupportedFile(file) {
  if (!file?.name) return false
  const ext = file.name.split('.').pop()?.toLowerCase()
  return SUPPORTED_EXTENSIONS.includes(ext)
}

// ─────────────────────────────────────────────────────────────
// Upload response helpers
// ─────────────────────────────────────────────────────────────

export function extractDatasetIds(data) {
  if (!data || typeof data !== 'object') return []
  const out = []

  if (Array.isArray(data.datasets)) {
    for (const d of data.datasets) {
      const id = d?.dataset_id ?? d?.datasetId ?? d?.id
      if (id != null) out.push(id)
    }
  }
  if (out.length) return out

  const candidates = [data, data.data, data.dataset, data.result].filter(Boolean)
  for (const c of candidates) {
    const id = c.dataset_id ?? c.datasetId ?? c.id
    if (id != null) out.push(id)
  }
  return out
}

export function extractDatasetId(data) {
  return extractDatasetIds(data)[0] ?? null
}

export function extractUploadMeta(data) {
  if (!data || typeof data !== 'object') return null
  const first = Array.isArray(data.datasets) ? data.datasets[0] : null
  if (!first) return null
  return {
    sessionId: data.session_id ?? null,
    datasetId: first.dataset_id ?? null,
    fileName: first.file_name ?? null,
    storedFileName: first.stored_file_name ?? null,
    uploadDate: first.upload_date ?? null,
    rows: first?.data?.rows ?? null,
    columns: first?.data?.columns ?? null,
    columnNames: Array.isArray(first?.data?.column_names)
      ? first.data.column_names
      : [],
  }
}

// ─────────────────────────────────────────────────────────────
// Profile normalizer — matches the CONFIRMED response shape
// ─────────────────────────────────────────────────────────────

const toNum = (v) => {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) {
    return Number(v)
  }
  return null
}

function normalizeColumn(c, index) {
  if (!c || typeof c !== 'object') return null

  const name = c.column_name || c.name || `column_${index}`
  const dtype = c.dtype || null

  const samples = Array.isArray(c.sample_values)
    ? c.sample_values
    : Array.isArray(c.samples)
    ? c.samples
    : []

  // Numeric statistics may be on the column, or live in the top-level
  // numerical_statistics map. We normalize both into `numeric`.
  let numeric = null
  const s = c.statistics
  if (s && typeof s === 'object') {
    numeric = {
      mean: toNum(s.mean),
      std: toNum(s.std),
      min: toNum(s.min),
      max: toNum(s.max),
      median: toNum(s.median),
      q1: toNum(s['25%']),
      q3: toNum(s['75%']),
    }
  }

  return {
    name,
    dtype,
    missing: null, // filled from data.missing_values[]
    missingPct: null,
    unique: toNum(c.unique_count),
    uniqueRatio: toNum(c.unique_ratio),
    samples,
    numeric:
      numeric && Object.values(numeric).some((v) => v != null) ? numeric : null,
    topValues: null, // filled from data.categorical_frequencies
    classification: c.classification || null,
    rowCount: toNum(c.row_count),
  }
}

export function normalizeDatasetProfile(raw) {
  if (!raw || typeof raw !== 'object') return null

  const data = raw.data && typeof raw.data === 'object' ? raw.data : raw

  const basic = data.basic || {}
  const columnsArr = Array.isArray(data.columns) ? data.columns : []
  const columns = columnsArr.map(normalizeColumn).filter(Boolean)

  // Merge missing-value info
  const missingList = Array.isArray(data.missing_values)
    ? data.missing_values
    : []
  const missingByName = new Map(missingList.map((m) => [m.column, m]))
  for (const c of columns) {
    const m = missingByName.get(c.name)
    if (m) {
      c.missing = toNum(m.missing_count)
      const pct = toNum(m.missing_percentage)
      c.missingPct = pct != null ? pct / 100 : null
    }
  }

  // Merge numerical_statistics (top-level)
  const numStats =
    data.numerical_statistics && typeof data.numerical_statistics === 'object'
      ? data.numerical_statistics
      : {}
  for (const c of columns) {
    const ns = numStats[c.name]
    if (!ns) continue
    c.numeric = {
      mean: toNum(ns.mean),
      std: toNum(ns.std),
      min: toNum(ns.min),
      max: toNum(ns.max),
      median: toNum(ns['50%']),
      q1: toNum(ns['25%']),
      q3: toNum(ns['75%']),
    }
  }

  // Merge categorical_frequencies (top-level)
  const catFreq =
    data.categorical_frequencies &&
    typeof data.categorical_frequencies === 'object'
      ? data.categorical_frequencies
      : {}
  for (const c of columns) {
    const cf = catFreq[c.name]
    if (!cf || typeof cf !== 'object') continue
    const entries = Object.entries(cf)
      .map(([value, count]) => ({ value, count: toNum(count) }))
      .sort((a, b) => (b.count ?? 0) - (a.count ?? 0))
    c.topValues = entries.length ? entries : null
  }

  return {
    datasetId: raw.dataset_id ?? data.dataset_id ?? null,
    profileId: raw.profile_id ?? data.profile_id ?? null,
    name: null, // profile endpoint does not return filename
    fileType: null,
    createdAt: null,
    rows: toNum(basic.row_count),
    columnsCount: toNum(basic.column_count) ?? columns.length ?? null,
    columns,
  }
}

// ─────────────────────────────────────────────────────────────
// Preprocessing
// ─────────────────────────────────────────────────────────────

export function buildPreprocessPayload(extra = {}) {
  return Object.keys(extra).length ? extra : null
}

export function normalizePreprocessResult(raw) {
  if (!raw || typeof raw !== 'object') return null
  const data = raw.data && typeof raw.data === 'object' ? raw.data : raw

  const pickNum = (...keys) => {
    for (const k of keys) {
      const n = toNum(data[k])
      if (n != null) return n
    }
    return null
  }

  const pickStr = (...keys) => {
    for (const k of keys) {
      const v = data[k]
      if (typeof v === 'string' && v.length) return v
    }
    return null
  }

  const pickArr = (...keys) => {
    for (const k of keys) {
      const v = data[k]
      if (Array.isArray(v)) return v
    }
    return []
  }

  return {
    status: pickStr('status') || (raw.status ?? null),
    message: pickStr('message') || (raw.message ?? null),
    datasetId: pickNum('dataset_id', 'datasetId') ?? raw.dataset_id ?? null,
    processedDatasetId: pickNum(
      'processed_dataset_id',
      'preprocessed_dataset_id',
      'output_dataset_id',
    ),
    rowsBefore: pickNum('rows_before', 'input_rows', 'original_rows'),
    rowsAfter: pickNum('rows_after', 'output_rows', 'processed_rows'),
    columnsBefore: pickNum(
      'columns_before',
      'input_columns',
      'original_columns',
    ),
    columnsAfter: pickNum(
      'columns_after',
      'output_columns',
      'processed_columns',
    ),
    warnings: pickArr('warnings', 'validation_messages'),
    errors: pickArr('errors', 'validation_errors'),
    removedColumns: pickArr('removed_columns', 'dropped_columns'),
    addedColumns: pickArr('added_columns', 'new_columns'),
    transformations: pickArr('transformations', 'operations', 'steps'),
    finishedAt: pickStr(
      'finished_at',
      'completed_at',
      'processed_at',
      'timestamp',
    ),
    raw,
  }
}

// ─────────────────────────────────────────────────────────────
// API client
// ─────────────────────────────────────────────────────────────

export const datasetApi = {
  upload: (input, { onProgress, signal, groupId, domainType } = {}) => {
    const files = Array.isArray(input) ? input : [input]
    const form = new FormData()
    for (const f of files) form.append(FILE_FIELD, f)
    if (groupId != null) form.append('group_id', String(groupId))
    if (domainType) form.append('domain_type', domainType)

    return apiClient.post('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 10 * 60 * 1000,
      onUploadProgress: onProgress
        ? (e) => {
            if (e.total) onProgress(Math.round((e.loaded * 100) / e.total))
          }
        : undefined,
      signal,
    })
  },

  profile: (datasetId) =>
    apiClient.get(`/profile/${datasetId}`, {
      timeout: 5 * 60 * 1000,
    }),

  preprocess: (datasetId, extra) =>
    apiClient.post(
      `/preprocess/${datasetId}`,
      buildPreprocessPayload(extra),
      { timeout: 10 * 60 * 1000 },
    ),

  list: () => apiClient.get('/datasets'),

  getColumns: (datasetId) => apiClient.get(`/datasets/${datasetId}/columns`),
}