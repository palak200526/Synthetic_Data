import apiClient from './client.js'

// Confirmed contract:
//   POST /column-analysis/{dataset_id}
//   → { status: "queued", job_id, message, poll_url }
//
//   GET  /column-analysis/status/{job_id}
//   → PENDING | PROGRESS | SUCCESS | FAILURE
//     SUCCESS: { status, result: { status, dataset_id, columns_analyzed, data: { columns: [...] } } }

export const VALID_ACTIONS = [
  'keep',
  'remove',
  'new_id',
  'generalize',
  'derived',
  'llm',
]

export const llmApi = {
  // Start the background analysis job
  analyzeColumns: (datasetId) =>
    apiClient.post(`/column-analysis/${datasetId}`, null, {
      timeout: 60 * 1000, // 1 minute — just to queue, fast
    }),

  // Poll job status
  getAnalysisStatus: (jobId) =>
    apiClient.get(`/column-analysis/status/${jobId}`, {
      timeout: 30 * 1000,
    }),
}

export function extractAnalysis(data) {
  if (!data || typeof data !== 'object') return []

  // Support both old (sync) and new (job result) shapes:
  //   old: { data: { columns: [...] } }
  //   new: { result: { data: { columns: [...] } } }
  const list =
    data?.result?.data?.columns ||
    data?.data?.columns ||
    data?.columns ||
    []

  if (!Array.isArray(list)) return []

  return list
    .map((c) => {
      const columnName = c?.column_name || c?.columnName || c?.name
      if (!columnName) return null
      const action = VALID_ACTIONS.includes(c?.action) ? c.action : 'keep'
      return {
        columnName,
        isIdentifier:
          c?.is_identifier === true || c?.isIdentifier === true,
        action,
        reason: c?.reason || c?.explanation || null,
      }
    })
    .filter(Boolean)
}