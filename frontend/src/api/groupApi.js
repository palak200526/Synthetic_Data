import apiClient from './client.js'

const STORAGE_KEY = 'datrixa.groups'

export function loadLocalGroups() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

function saveLocalGroups(groups) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(groups))
  } catch {
    /* noop */
  }
}

export function rememberGroup({ id, name, domainType }) {
  if (id == null) return
  const existing = loadLocalGroups().filter((g) => String(g.id) !== String(id))
  existing.unshift({
    id,
    name: name || `Group ${id}`,
    domainType: domainType || null,
    createdAt: new Date().toISOString(),
  })
  saveLocalGroups(existing.slice(0, 100))
}

export function forgetGroup(id) {
  saveLocalGroups(loadLocalGroups().filter((g) => String(g.id) !== String(id)))
}

export function getGroupById(id) {
  return loadLocalGroups().find((g) => String(g.id) === String(id)) || null
}

export const groupApi = {
  create: async ({ groupName, domainType }) => {
    const res = await apiClient.post('/groups', {
      group_name: groupName,
      domain_type: domainType,
    })
    const d = res.data || {}
    if (d.group_id != null) {
      rememberGroup({
        id: d.group_id,
        name: d.group_name,
        domainType: d.domain_type,
      })
    }
    return d
  },

  list: async () => {
    try {
      const res = await apiClient.get('/groups')
      const backendGroups = res.data?.groups || []
      // Sync local groups with backend
      for (const g of backendGroups) {
        rememberGroup({
          id: g.group_id,
          name: g.group_name,
          domainType: g.domain_type,
        })
      }
      return backendGroups
    } catch (err) {
      // Fallback to local storage if endpoint fails
      const local = loadLocalGroups()
      return local.map((g) => ({
        group_id: g.id,
        group_name: g.name,
        domain_type: g.domainType,
        created_at: g.createdAt,
      }))
    }
  },

  getDatasets: async (groupId) => {
    const res = await apiClient.get(`/groups/${groupId}/datasets`)
    return res.data?.datasets || []
  },

  assignDataset: async (groupId, datasetId) => {
    const res = await apiClient.post(`/groups/${groupId}/datasets/${datasetId}`)
    return res.data
  },
}