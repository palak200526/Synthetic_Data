import apiClient from './client.js'

export const relationshipApi = {
  /**
   * Get all relationships configured for a dataset group.
   */
  listByGroup: async (groupId) => {
    const res = await apiClient.get(`/relationships/group/${groupId}`)
    return res.data?.relationships || []
  },

  /**
   * Create a foreign key relationship between two datasets.
   */
  create: async ({
    groupId,
    parentDatasetId,
    parentColumn,
    childDatasetId,
    childColumn,
    relationshipType = 'one-to-many',
  }) => {
    const res = await apiClient.post('/relationships', {
      group_id: Number(groupId),
      parent_dataset_id: Number(parentDatasetId),
      parent_column: parentColumn,
      child_dataset_id: Number(childDatasetId),
      child_column: childColumn,
      relationship_type: relationshipType,
    })
    return res.data
  },

  /**
   * Delete a dataset relationship by ID.
   */
  delete: async (relationshipId) => {
    const res = await apiClient.delete(`/relationships/${relationshipId}`)
    return res.data
  },

  /**
   * Trigger multi-table synthetic data generation for a dataset group.
   */
  generateMultiTable: async ({ groupId, modelName = 'gaussian_copula', parameters = {} }) => {
    const res = await apiClient.post('/generation/multi-table', {
      group_id: Number(groupId),
      model_name: modelName,
      parameters: parameters,
    })
    return res.data
  },

  /**
   * Run relationship analysis (correlation/covariance) on a single dataset.
   */
  analyze: async (datasetId, { testSize = 0.2, randomState = 42 } = {}) => {
    const res = await apiClient.post(
      `/relationships/dataset?dataset_id=${datasetId}`,
      {
        test_size: testSize,
        random_state: randomState,
      }
    )
    return res.data
  },

  /**
   * Get stored relationship analysis for a single dataset.
   */
  getAnalysis: async (datasetId) => {
    const res = await apiClient.get(`/relationships/${datasetId}`)
    return res.data
  },
}
