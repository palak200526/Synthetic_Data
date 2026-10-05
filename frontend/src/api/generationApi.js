import apiClient from './client.js'

// ─────────────────────────────────────────────────────────────
// Confirmed from /docs:
//   POST /generation          { dataset_id, model_name, parameters? }
//   POST /generation/multi-table  { group_id, model_name, parameters? }
//   POST /generation/ids/{dataset_id}   (path param only)
//
// CONTRACT UNKNOWNS:
//   - The exact string the backend expects for model_name.
//     Edit `backendName` below if the backend rejects with 422.
//   - The response shape. normalizeGenerationResult() probes a
//     wide set of plausible keys and returns null when absent.
// ─────────────────────────────────────────────────────────────

export const MODELS = [
  {
    id: 'gaussian_copula',
    label: 'Gaussian Copula',
    // CONTRACT: adjust if backend expects e.g. "GaussianCopula" or "gaussian"
    backendName: 'gaussian_copula',
    description:
      'Fast statistical model. Preserves marginal distributions and linear correlations.',
    speed: 'Fast',
    bestFor: 'Numeric-heavy tabular data',
  },
  {
    id: 'ctgan',
    label: 'CTGAN',
    backendName: 'ctgan',
    description:
      'Deep generative adversarial model. Handles mixed categorical and numeric columns.',
    speed: 'Slow',
    bestFor: 'Mixed-type datasets',
  },
  {
    id: 'tvae',
    label: 'TVAE',
    backendName: 'tvae',
    description:
      'Variational autoencoder. Similar to CTGAN with different training behaviour.',
    speed: 'Slow',
    bestFor: 'Smaller datasets, denser distributions',
  },
]

export const MODEL_PARAMS = {
  gaussian_copula: [
    {
      key: 'default_distribution',
      label: 'Default distribution',
      type: 'select',
      options: [
        'beta',
        'gamma',
        'gaussian',
        'gaussian_kde',
        'truncnorm',
        'uniform',
      ],
    },
  ],
  ctgan: [
    { key: 'epochs', label: 'Epochs', type: 'number', min: 1, step: 1 },
    { key: 'batch_size', label: 'Batch size', type: 'number', min: 1, step: 1 },
    {
      key: 'discriminator_steps',
      label: 'Discriminator steps',
      type: 'number',
      min: 1,
      step: 1,
    },
    { key: 'log_frequency', label: 'Log frequency', type: 'boolean' },
  ],
  tvae: [
    { key: 'epochs', label: 'Epochs', type: 'number', min: 1, step: 1 },
    { key: 'batch_size', label: 'Batch size', type: 'number', min: 1, step: 1 },
    {
      key: 'loss_factor',
      label: 'Loss factor',
      type: 'number',
      min: 0,
      step: 0.1,
    },
  ],
}

export const LLM_TEXT_PARAMS = [
  {
    key: 'llm_text_batch_size',
    label: 'LLM text batch size',
    type: 'number',
    min: 1,
    step: 1,
  },
  {
    key: 'llm_text_timeout',
    label: 'LLM text timeout (seconds)',
    type: 'number',
    min: 1,
    step: 1,
  },
  {
    key: 'llm_text_max_retries',
    label: 'LLM text max retries',
    type: 'number',
    min: 1,
    step: 1,
  },
]

export function getModelById(id) {
  return MODELS.find((m) => m.id === id) || null
}

// ─────────────────────────────────────────────────────────────
// Response normalizer — probes many shapes, never invents
// ─────────────────────────────────────────────────────────────

const toNum = (v) => {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) {
    return Number(v)
  }
  return null
}

export function normalizeGenerationResult(raw) {
  if (!raw || typeof raw !== 'object') return null
  const data = raw.data && typeof raw.data === 'object' ? raw.data : raw

  const num = (...keys) => {
    for (const k of keys) {
      const n = toNum(data[k])
      if (n != null) return n
    }
    return null
  }
  const str = (...keys) => {
    for (const k of keys) {
      const v = data[k]
      if (typeof v === 'string' && v.length) return v
    }
    return null
  }
  const bool = (...keys) => {
    for (const k of keys) {
      const v = data[k]
      if (typeof v === 'boolean') return v
    }
    return null
  }

  return {
    status: str('status') || raw.status || null,
    message: str('message') || raw.message || null,

    runId: num('run_id', 'runId'),
    resultId: num('result_id', 'resultId'),

    syntheticDatasetId: num(
      'synthetic_dataset_id',
      'generated_dataset_id',
      'output_dataset_id',
      'result_dataset_id',
      'generated_id',
      'dataset_id',
    ),
    sourceDatasetId: num('source_dataset_id', 'input_dataset_id'),
    model: str('model', 'model_name', 'model_type'),

    rows: num('rows', 'row_count', 'num_rows', 'generated_rows', 'n_rows'),
    columns: num(
      'columns',
      'column_count',
      'num_columns',
      'generated_columns',
    ),
    duration: num(
      'duration_seconds',
      'elapsed_seconds',
      'elapsed_time',
      'duration',
    ),

    filePath: str('file_path', 'output_path', 'generated_file_path'),
    fileName: str('file_name', 'output_file_name', 'generated_file_name'),

    finishedAt: str(
      'finished_at',
      'completed_at',
      'generated_at',
      'created_at',
      'timestamp',
    ),
    isMultiTable: bool('multi_table', 'is_multi_table'),

    raw,
  }
}

// ─────────────────────────────────────────────────────────────
// API client
// ─────────────────────────────────────────────────────────────

export const generationApi = {
  generate: ({ datasetId, modelName, parameters }) => {
    const body = {
      dataset_id: Number(datasetId),
      model_name: modelName,
    }
    if (parameters && typeof parameters === 'object') {
      body.parameters = parameters
    }
    return apiClient.post('/generation', body, {
      timeout: 60 * 1000, // queue only
    })
  },

  getStatus: (jobId) =>
    apiClient.get(`/generation/status/${jobId}`, {
      timeout: 30 * 1000,
    }),

  generateMultiTable: ({ groupId, modelName, parameters }) => {
    const body = {
      group_id: Number(groupId),
      model_name: modelName,
    }
    if (parameters && typeof parameters === 'object') {
      body.parameters = parameters
    }
    return apiClient.post('/generation/multi-table', body, {
      timeout: 30 * 60 * 1000,
    })
  },

  generateIds: (datasetId) =>
    apiClient.post(`/generation/ids/${datasetId}`, null, {
      timeout: 10 * 60 * 1000,
    }),
}