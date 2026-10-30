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
      label: 'Number Pattern (Distribution)',
      defaultValue: 'beta',
      category: 'basic',
      type: 'select',
      options: ['beta', 'gaussian', 'gamma', 'gaussian_kde', 'truncnorm', 'uniform'],
      help: 'The curve shape used to imitate each numeric column (prices, quantities, lead times).',
      whenToChange:
        'Keep "beta" unless the Statistical Similarity score of a numeric column is low. Then try "gaussian_kde" (most flexible) or "gamma" (for positive, right-skewed values).',
      effectOnData: {
        beta: 'Default. Flexible shape that works well for values with a clear minimum and maximum, such as prices, discounts and percentages.',
        gaussian: 'Symmetric bell curve. Good when values cluster around an average, such as product weights.',
        gamma: 'Skewed curve with a long tail on the high side. Suits positive values such as delivery lead times. Not suited to columns that contain negative values.',
        gaussian_kde: 'Learns the shape directly from your data, so it can copy columns with several peaks (for example different supplier price tiers). Slower on large data.',
        truncnorm: 'Bell curve cut off at the lowest and highest values seen in your data.',
        uniform: 'Every value in the range is equally likely. Use only for columns that really are evenly spread.',
      },
      tradeOffs:
        'A more flexible shape (gaussian_kde) copies your data more closely but takes longer. Simple shapes are faster but can miss unusual patterns.',
      supplyChainExample:
        'Supplier lead times are usually skewed: most deliveries are on time and a few are very late. "gamma" or "gaussian_kde" copy this better than "gaussian".',
      whatToCheckAfter:
        'Statistical Similarity (per-column distribution charts) on the Evaluation page.',
    },
  ],
  ctgan: [
    {
      key: 'epochs',
      label: 'Training Rounds (Epochs)',
      defaultValue: 100,
      category: 'basic',
      type: 'number',
      min: 10,
      max: 2000,
      step: 10,
      help: 'How many times the model studies your full dataset. More rounds = more learning, but more time.',
      whenToChange:
        'The default of 100 is a good balance for most data. Use 30 to 50 for a quick trial. Try 300 for higher quality (about 3 times longer than 100). Go to 500 or more only if results still look weak and you have a large dataset with many columns.',
      effectOnData: {
        increase:
          'The model learns more detailed patterns between columns, and quality usually improves up to a point. Training time grows roughly in proportion to the number of rounds.',
        decrease:
          'Training finishes sooner, but the model may not learn how columns relate, so the synthetic data looks less realistic.',
      },
      tradeOffs:
        'Quality versus waiting time. After a point, extra rounds give very little improvement.',
      supplyChainExample:
        'With enough rounds, the model learns that "Express Air" shipments usually go with high-priority orders and higher unit costs.',
      whatToCheckAfter:
        'Statistical Similarity, ML Utility and Correlation scores on the Evaluation page.',
    },
    {
      key: 'batch_size',
      label: 'Batch Size',
      defaultValue: 500,
      category: 'basic',
      type: 'number',
      min: 10,
      max: 2000,
      step: 10,
      help: 'How many rows the model looks at in one learning step. It is rounded to a multiple of 10 automatically.',
      whenToChange:
        'Keep 500 for large data. For small data (a few thousand rows or fewer), try 100 to 200. Do not set it larger than your row count.',
      effectOnData: {
        increase:
          'Each round runs faster and learning is smoother, but rare categories can get less attention.',
        decrease:
          'The model pays more attention to rare categories and small groups, but each round takes longer.',
      },
      tradeOffs:
        'Speed versus attention to rare groups.',
      supplyChainExample:
        'A smaller batch helps keep rare values such as the supplier status "On Hold".',
      whatToCheckAfter:
        'Categorical column charts (are rare categories still present?) and the training time.',
    },
  ],
  tvae: [
    {
      key: 'epochs',
      label: 'Training Rounds (Epochs)',
      defaultValue: 100,
      category: 'basic',
      type: 'number',
      min: 10,
      max: 2000,
      step: 10,
      help: 'How many times the model studies your full dataset. More rounds = more learning, but more time.',
      whenToChange:
        'The default of 100 is a good balance for most data. Use 30 to 50 for a quick trial. Try 300 for higher accuracy (about 3 times longer than 100). Go to 500 or more only if results still look weak and the dataset is large.',
      effectOnData: {
        increase:
          'The model copies your numbers and column relationships more accurately. Training time grows roughly in proportion to the number of rounds.',
        decrease:
          'Faster, and often enough for small or simple datasets, but accuracy can drop.',
      },
      tradeOffs:
        'Accuracy versus waiting time. After a point, extra rounds add very little.',
      supplyChainExample:
        'More rounds help copy continuous values such as lead times, shipping weights and order totals.',
      whatToCheckAfter:
        'Statistical Similarity and ML Utility.',
    },
    {
      key: 'batch_size',
      label: 'Batch Size',
      defaultValue: 500,
      category: 'basic',
      type: 'number',
      min: 10,
      max: 2000,
      step: 10,
      help: 'How many rows the model looks at in one learning step.',
      whenToChange:
        'Keep 500 for large data. For small data (a few thousand rows or fewer), try 100 to 200. Do not set it larger than your row count.',
      effectOnData: {
        increase:
          'Faster rounds and smoother learning.',
        decrease:
          'Slower rounds, but often more stable on small datasets.',
      },
      tradeOffs:
        'Speed versus stability on small data.',
      supplyChainExample:
        'A supplier master table with a few hundred rows works better with a small batch. Large shipment history can use a bigger one.',
      whatToCheckAfter:
        'Training time and Statistical Similarity.',
    },
  ],
}

/**
 * Returns default parameter values object for a given model.
 */
export function getDefaultParams(modelId) {
  const params = MODEL_PARAMS[modelId] || []
  const out = {}
  for (const p of params) {
    if (p.defaultValue !== undefined) {
      out[p.key] = p.defaultValue
    }
  }
  return out
}

/**
 * Plain-language feedback shown under a parameter once its value is changed.
 * Tones used here must exist in AlgorithmParameterPanel's tone map:
 * amber | blue | teal | purple | emerald | indigo
 */
export function getParamDynamicGuidance(modelId, key, currentValue) {
  const params = MODEL_PARAMS[modelId] || []
  const def = params.find((p) => p.key === key)
  if (!def || currentValue === undefined || currentValue === null || currentValue === '') {
    return null
  }

  const defaultVal = def.defaultValue
  if (String(currentValue) === String(defaultVal)) {
    return {
      status: 'default',
      tag: 'Default Value',
      tone: 'ink',
      message: 'Using the recommended value.',
    }
  }

  const num = Number(currentValue)
  const higher = num > Number(defaultVal)

  switch (key) {
    case 'epochs':
      return higher
        ? {
            status: 'higher', tone: 'amber', tag: 'Longer Training',
            message: `Raised from ${defaultVal} to ${num}. Takes longer. Quality may improve, but with diminishing returns.`,
          }
        : {
            status: 'lower', tone: 'blue', tag: 'Faster Training',
            message: `Lowered from ${defaultVal} to ${num}. Finishes sooner, but the model may learn column relationships less well.`,
          }

    case 'batch_size':
      return higher
        ? {
            status: 'higher', tone: 'teal', tag: 'Faster Rounds',
            message: `Raised from ${defaultVal} to ${num}. Each round is quicker, but rare categories may get less attention.`,
          }
        : {
            status: 'lower', tone: 'indigo', tag: 'More Attention to Rare Groups',
            message: `Lowered from ${defaultVal} to ${num}. Small groups get more attention, but each round takes longer. Keep it below your row count.`,
          }

    case 'learning_rate':
      return higher
        ? {
            status: 'higher', tone: 'amber', tag: 'Faster but Less Stable',
            message: 'Learns faster at first, but results can become inconsistent. Compare against a default run.',
          }
        : {
            status: 'lower', tone: 'blue', tag: 'Slower but Steadier',
            message: 'More stable training, but it usually needs more epochs to reach the same quality.',
          }

    case 'discriminator_steps':
      return {
        status: 'higher', tone: 'amber', tag: 'Longer Training',
        message: `The checker learns ${num} times per update. This can add variety, but training takes noticeably longer.`,
      }

    case 'log_frequency':
      return currentValue === false || currentValue === 'false'
        ? {
            status: 'changed', tone: 'amber', tag: 'Rare Categories May Shrink',
            message: 'Categories will follow their real proportions, and very rare ones may disappear. Check the categorical charts.',
          }
        : {
            status: 'changed', tone: 'teal', tag: 'Rare Categories Protected',
            message: 'Rare categories get extra attention and are more likely to appear.',
          }

    case 'embedding_dim':
    case 'latent_dim':
      return higher
        ? {
            status: 'higher', tone: 'purple', tag: 'More Capacity',
            message: `Raised from ${defaultVal} to ${num}. Can keep more detail on wide data, with slightly more time and memory.`,
          }
        : {
            status: 'lower', tone: 'blue', tag: 'Lighter Model',
            message: `Lowered from ${defaultVal} to ${num}. Faster and lighter, but fine details can be lost.`,
          }

    case 'loss_factor':
      return higher
        ? {
            status: 'higher', tone: 'purple', tag: 'Closer to Real Data',
            message: `Raised from ${defaultVal} to ${num}. Values follow your real data more closely. Check the Privacy score for copied rows.`,
          }
        : {
            status: 'lower', tone: 'emerald', tag: 'More Variety',
            message: `Lowered from ${defaultVal} to ${num}. More varied rows and less copying, but relationships can look softer.`,
          }

    case 'l2scale':
      return higher
        ? {
            status: 'higher', tone: 'emerald', tag: 'More Privacy Protection',
            message: 'The model memorises real rows less. Patterns may become slightly softer.',
          }
        : {
            status: 'lower', tone: 'amber', tag: 'Tighter Fit',
            message: 'The model fits your data more tightly, which raises the chance of copying real rows. Check the Privacy score.',
          }

    case 'default_distribution':
      return {
        status: 'changed', tone: 'indigo', tag: 'Distribution Changed',
        message: `Numeric columns will be modelled with "${currentValue}". Check the per-column charts on the Evaluation page.`,
      }

    case 'enforce_min_max_values':
      return currentValue === false || currentValue === 'false'
        ? {
            status: 'changed', tone: 'amber', tag: 'Range Limit Off',
            message: 'Values can go outside the original min / max, including negative values. Check Business-Rule Validity.',
          }
        : {
            status: 'changed', tone: 'teal', tag: 'Range Limit On',
            message: 'Values stay inside the original min / max.',
          }

    case 'random_state':
      return {
        status: 'changed', tone: 'teal', tag: 'Different Random Sample',
        message: 'A different seed gives a different sample. Use the same seed to repeat a result.',
      }

    default:
      return {
        status: 'custom', tone: 'blue', tag: 'Custom Value',
        message: `Changed from the default (${defaultVal}). Check the Evaluation page after generating.`,
      }
  }
}

export const LLM_TEXT_PARAMS = [
  {
    key: 'llm_text_batch_size',
    label: 'LLM text batch size',
    help: 'How many text values are requested from the local LLM in one call.',
    type: 'number',
    min: 1,
    step: 1,
  },
  {
    key: 'llm_text_max_concurrency',
    label: 'LLM text parallel requests',
    help: 'How many batches are sent to Ollama at the same time (1-16). Match it to OLLAMA_NUM_PARALLEL on the server.',
    type: 'number',
    min: 1,
    step: 1,
  },
  {
    key: 'llm_text_timeout',
    label: 'LLM text timeout (seconds)',
    help: 'Maximum time to wait for the LLM per call before giving up.',
    type: 'number',
    min: 1,
    step: 1,
  },
  {
    key: 'llm_text_max_retries',
    label: 'LLM text max retries',
    help: 'How many times a failed LLM text call is retried.',
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

// Backend multi-table response returns `tables: { [datasetId]: {...} }`.
function normalizeDatasets(data, raw) {
  const fromTables = data.tables || raw.tables
  if (fromTables && typeof fromTables === 'object') {
    const list = Array.isArray(fromTables)
      ? fromTables
      : Object.values(fromTables)
    return list.map((t) => ({
      datasetId: toNum(t.dataset_id),
      resultId: toNum(t.result_id),
      runId: toNum(t.run_id),
      fileName: t.file_name || t.source_filename || null,
      sourceFileName: t.source_filename || null,
      rows: toNum(t.row_count ?? t.rows),
      columns: toNum(t.column_count ?? t.columns),
    }))
  }
  const arr = Array.isArray(data.datasets)
    ? data.datasets
    : Array.isArray(raw.datasets)
      ? raw.datasets
      : []
  return arr.map((d) => ({
    ...d,
    datasetId: d.datasetId ?? toNum(d.dataset_id),
    resultId: d.resultId ?? toNum(d.result_id),
    runId: d.runId ?? toNum(d.run_id),
    fileName: d.fileName ?? d.file_name ?? null,
  }))
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

    datasets: normalizeDatasets(data, raw),
    referentialIntegrity:
      typeof data.referential_integrity === 'boolean'
        ? data.referential_integrity
        : null,
    groupId: num('group_id'),

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

  algorithmStats: () =>
    apiClient.get('/generation/algorithm-stats', { timeout: 30 * 1000 }),

  preview: (resultId, limit = 10) =>
    apiClient.get('/generation/preview', {
      params: { result_id: Number(resultId), limit },
      timeout: 30 * 1000,
    }),

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

  improveQuality: ({ resultId, parameters, maxAttempts, improvementThreshold, targetColumn }) =>
    apiClient.post(
      '/generation/improve-quality',
      {
        result_id: Number(resultId),
        parameters: parameters || {},
        max_attempts: maxAttempts || 3,
        improvement_threshold: improvementThreshold ?? 1.0,
        target_column: targetColumn || null,
      },
      {
        timeout: 15 * 60 * 1000,
      },
    ),

  submitQualityFeedback: ({ resultId, improvedResultId, feedback, focusArea, comment }) =>
    apiClient.post('/generation/quality-feedback', {
      result_id: Number(resultId),
      improved_result_id: improvedResultId ? Number(improvedResultId) : null,
      feedback,
      focus_area: focusArea || null,
      comment: comment || null,
    }),

  listJobs: (params) =>
    apiClient.get('/generation/jobs', { params, timeout: 30 * 1000 }),

  listActiveJobs: () =>
    apiClient.get('/generation/jobs/active', { timeout: 30 * 1000 }),

  getJobDetails: (jobId) =>
    apiClient.get(`/generation/jobs/${jobId}`, { timeout: 30 * 1000 }),

  pauseJob: (jobId) =>
    apiClient.post(`/generation/jobs/${jobId}/pause`, null, { timeout: 30 * 1000 }),

  resumeJob: (jobId) =>
    apiClient.post(`/generation/jobs/${jobId}/resume`, null, { timeout: 30 * 1000 }),

  restartJob: (jobId) =>
    apiClient.post(`/generation/jobs/${jobId}/restart`, null, { timeout: 30 * 1000 }),

  cancelJob: (jobId) =>
    apiClient.post(`/generation/jobs/${jobId}/cancel`, null, { timeout: 30 * 1000 }),

  discardJob: (jobId) =>
    apiClient.delete(`/generation/jobs/${jobId}`, { timeout: 30 * 1000 }),

  downloadDataset: async (resultId, fileName = 'synthetic_dataset.csv') => {
    const res = await apiClient.get('/download', {
      params: { result_id: Number(resultId), type: 'dataset' },
      responseType: 'blob',
      timeout: 5 * 60 * 1000,
    })
    const blob = new Blob([res.data], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName.endsWith('.csv') ? fileName : `${fileName}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  downloadMultiTableDataset: async (resultId) => {
    const res = await apiClient.get('/download/multi-table', {
      params: { result_id: Number(resultId) },
      responseType: 'blob',
      timeout: 5 * 60 * 1000,
    })
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `datrixa_multitable_result_${Number(resultId)}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
}