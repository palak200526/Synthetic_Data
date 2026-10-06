import apiClient from './client.js'

// Confirmed contract:
//   POST /column-configurations
//     { configurations: [{ dataset_id, column_name, column_type,
//                          is_identifier, action, rule }] }
//   GET  /column-configurations/{dataset_id}
//     → { status, message, dataset_id, data: [
//         { configuration_id, dataset_id, column_name,
//           column_type, is_identifier, action } ] }

export const configurationApi = {
  save: (datasetId, rows) => {
    const configurations = rows.map((r) => ({
      dataset_id: Number(datasetId),
      column_name: r.columnName,
      column_type: r.columnType,
      is_identifier: r.isIdentifier,
      action: r.action,
      rule: r.rule ?? null,
    }))
    return apiClient.post('/column-configurations', { configurations })
  },
  get: (datasetId) => apiClient.get(`/column-configurations/${datasetId}`),
}

export function extractConfigurations(data) {
  if (!data || typeof data !== 'object') return []
  const list = Array.isArray(data.data) ? data.data : []
  return list.map((c) => ({
    configurationId: c.configuration_id,
    datasetId: c.dataset_id,
    columnName: c.column_name,
    columnType: c.column_type,
    isIdentifier: c.is_identifier === true,
    action: c.action || 'keep',
    rule: c.rule ?? null,
  }))
}