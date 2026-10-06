import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  GitBranch,
  Plus,
  Trash2,
  PlayCircle,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Database,
  Key,
  ArrowRight,
  Download,
  RefreshCw,
  Table,
  Layers,
  Sparkles,
  ShieldCheck,
  FileSpreadsheet,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import Toast from '../components/Toast.jsx'
import CreateGroupDialog from '../components/CreateGroupDialog.jsx'
import AddRelationshipDialog from '../components/AddRelationshipDialog.jsx'

import { groupApi } from '../api/groupApi.js'
import { relationshipApi } from '../api/relationshipApi.js'
import { datasetApi } from '../api/datasetApi.js'
import apiClient from '../api/client.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber } from '../utils/format.js'

export default function Relationships() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialGroupId =
    searchParams.get('group_id') || searchParams.get('groupId')

  const [groups, setGroups] = useState([])
  const [selectedGroupId, setSelectedGroupId] = useState(
    initialGroupId ? Number(initialGroupId) : null,
  )
  const [loadingGroups, setLoadingGroups] = useState(true)

  const [groupTables, setGroupTables] = useState([])
  const [loadingTables, setLoadingTables] = useState(false)

  const [allDatasets, setAllDatasets] = useState([])
  const [selectedDatasetToAssign, setSelectedDatasetToAssign] = useState('')
  const [assigningTable, setAssigningTable] = useState(false)

  const [relationships, setRelationships] = useState([])
  const [loadingRelationships, setLoadingRelationships] = useState(false)
  const [deletingRelId, setDeletingRelId] = useState(null)

  const [generationModel, setGenerationModel] = useState('gaussian_copula')
  const [generating, setGenerating] = useState(false)
  const [generationResult, setGenerationResult] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)

  const [openCreateGroup, setOpenCreateGroup] = useState(false)
  const [openAddRel, setOpenAddRel] = useState(false)

  const [toast, setToast] = useState({
    open: false,
    type: 'success',
    title: '',
    message: '',
  })
  const showToast = (type, title, message) =>
    setToast({ open: true, type, title, message })

  const loadGroups = useCallback(async () => {
    setLoadingGroups(true)
    try {
      const list = await groupApi.list()
      setGroups(list || [])
      if (!selectedGroupId && list && list.length > 0) {
        setSelectedGroupId(list[0].group_id ?? list[0].id)
      }
    } catch (err) {
      console.warn('Failed to load dataset groups:', err)
    } finally {
      setLoadingGroups(false)
    }
  }, [selectedGroupId])

  const loadAllDatasets = useCallback(async () => {
    try {
      const res = await datasetApi.list()
      setAllDatasets(res.data?.datasets || [])
    } catch (err) {
      console.warn('Failed to load all datasets:', err)
    }
  }, [])

  useEffect(() => {
    loadGroups()
    loadAllDatasets()
  }, [loadGroups, loadAllDatasets])

  useEffect(() => {
    if (selectedGroupId != null) {
      setSearchParams({ group_id: String(selectedGroupId) }, { replace: true })
    }
  }, [selectedGroupId, setSearchParams])

  const loadGroupData = useCallback(async (groupId) => {
    if (!groupId) {
      setGroupTables([])
      setRelationships([])
      return
    }
    setLoadingTables(true)
    setLoadingRelationships(true)
    try {
      const [tables, rels] = await Promise.all([
        groupApi.getDatasets(groupId).catch(() => []),
        relationshipApi.listByGroup(groupId).catch(() => []),
      ])
      setGroupTables(tables || [])
      setRelationships(rels || [])
    } catch (err) {
      console.warn('Failed to load group tables/relationships:', err)
    } finally {
      setLoadingTables(false)
      setLoadingRelationships(false)
    }
  }, [])

  useEffect(() => {
    if (selectedGroupId != null) loadGroupData(selectedGroupId)
  }, [selectedGroupId, loadGroupData])

  const selectedGroup = useMemo(
    () =>
      groups.find(
        (g) => String(g.group_id ?? g.id) === String(selectedGroupId),
      ) || null,
    [groups, selectedGroupId],
  )

  const handleGroupCreated = (created) => {
    const newId = created.group_id ?? created.id
    showToast(
      'success',
      'Group created',
      `Dataset group "${created.group_name}" created successfully.`,
    )
    loadGroups().then(() => {
      if (newId) setSelectedGroupId(Number(newId))
    })
  }

  const handleRelationshipCreated = () => {
    showToast(
      'success',
      'Relationship created',
      'Primary/Foreign key relationship created successfully.',
    )
    if (selectedGroupId) loadGroupData(selectedGroupId)
  }

  const handleDeleteRelationship = async (relId) => {
    if (!window.confirm('Are you sure you want to remove this relationship?'))
      return
    setDeletingRelId(relId)
    try {
      await relationshipApi.delete(relId)
      showToast(
        'success',
        'Relationship deleted',
        'The relationship was deleted successfully.',
      )
      setRelationships((prev) =>
        prev.filter((r) => r.relationship_id !== relId),
      )
    } catch (err) {
      showToast('error', 'Delete failed', getErrorMessage(err))
    } finally {
      setDeletingRelId(null)
    }
  }

  const handleAssignDataset = async (e) => {
    e.preventDefault()
    if (!selectedGroupId || !selectedDatasetToAssign) return
    setAssigningTable(true)
    try {
      await groupApi.assignDataset(selectedGroupId, selectedDatasetToAssign)
      showToast(
        'success',
        'Table added',
        `Dataset #${selectedDatasetToAssign} added to group.`,
      )
      setSelectedDatasetToAssign('')
      loadGroupData(selectedGroupId)
    } catch (err) {
      showToast('error', 'Add table failed', getErrorMessage(err))
    } finally {
      setAssigningTable(false)
    }
  }

  const handleGenerateMultiTable = async () => {
    if (!selectedGroupId) return
    if (relationships.length === 0) {
      showToast(
        'error',
        'Missing relationships',
        'Please define at least one relationship before generating data.',
      )
      return
    }
    setGenerating(true)
    setGenerationResult(null)
    try {
      const result = await relationshipApi.generateMultiTable({
        groupId: selectedGroupId,
        modelName: generationModel,
        parameters: { random_state: 42 },
      })
      setGenerationResult(result)
      showToast(
        'success',
        'Generation completed',
        'Multi-table synthetic data generated with 100% referential integrity.',
      )
    } catch (err) {
      showToast('error', 'Generation failed', getErrorMessage(err))
    } finally {
      setGenerating(false)
    }
  }

  const handleDownloadDataset = async (tableInfo) => {
    const datasetId = tableInfo.dataset_id
    const resultId = tableInfo.result_id
    const fileName =
      tableInfo.file_name || `synthetic_dataset_${datasetId}.csv`

    setDownloadingId(datasetId)
    try {
      const params = resultId
        ? { result_id: resultId, type: 'dataset' }
        : { dataset_id: datasetId, type: 'dataset' }
      const res = await apiClient.get('/download', {
        params,
        responseType: 'blob',
        timeout: 5 * 60 * 1000,
      })
      const blob = new Blob([res.data], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', fileName)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      showToast('success', 'Download started', `Downloading ${fileName}...`)
    } catch (err) {
      showToast('error', 'Download failed', getErrorMessage(err))
    } finally {
      setDownloadingId(null)
    }
  }

  const unassignedDatasets = useMemo(() => {
    const currentTableIds = new Set(
      groupTables.map((t) => Number(t.dataset_id ?? t.id)),
    )
    return allDatasets.filter(
      (d) => !currentTableIds.has(Number(d.dataset_id ?? d.id)),
    )
  }, [allDatasets, groupTables])

  return (
    <>
      <PageHeader
        title="Multi-table & relationships"
        subtitle="Configure parent-child foreign key relationships across datasets and generate connected multi-table synthetic data."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                if (selectedGroupId) loadGroupData(selectedGroupId)
                loadGroups()
              }}
              className="dx-btn-outline"
            >
              <RefreshCw size={14} /> Refresh
            </button>
            <button
              type="button"
              onClick={() => setOpenCreateGroup(true)}
              className="dx-btn-outline"
            >
              <Layers size={14} /> New group
            </button>
            <button
              type="button"
              disabled={!selectedGroupId}
              onClick={() => setOpenAddRel(true)}
              className="dx-btn-primary"
            >
              <Plus size={14} /> Add relationship
            </button>
          </div>
        }
      />

      <div className="space-y-6">
        {/* Group selector */}
        <div className="dx-card p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                <Layers size={18} />
              </div>
              <div className="min-w-0">
                <label
                  htmlFor="group-select"
                  className="block text-[11px] font-semibold uppercase tracking-wide text-ink-500"
                >
                  Active dataset group
                </label>
                <select
                  id="group-select"
                  value={selectedGroupId || ''}
                  onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                  disabled={loadingGroups || groups.length === 0}
                  className="dx-input mt-1 min-w-[240px] cursor-pointer"
                >
                  {groups.length === 0 ? (
                    <option value="">No dataset groups found</option>
                  ) : (
                    groups.map((g) => {
                      const id = g.group_id ?? g.id
                      return (
                        <option key={id} value={id}>
                          {g.group_name || `Group #${id}`}
                          {g.domain_type ? ` (${g.domain_type})` : ''}
                        </option>
                      )
                    })
                  )}
                </select>
              </div>
            </div>

            {selectedGroup && (
              <div className="flex flex-wrap items-center gap-2 self-end sm:self-center">
                {selectedGroup.domain_type && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-700 ring-1 ring-inset ring-brand-200">
                    Domain: {selectedGroup.domain_type}
                  </span>
                )}
                <span className="inline-flex items-center gap-1 rounded-full bg-ink-100 px-2.5 py-0.5 text-[11px] font-medium text-ink-700 ring-1 ring-inset ring-ink-200">
                  Group ID: #{selectedGroupId}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={Table}
            label="Tables in group"
            value={loadingTables ? null : groupTables.length}
            hint="Relational datasets linked together"
            accent="brand"
          />
          <StatCard
            icon={GitBranch}
            label="Active relationships"
            value={loadingRelationships ? null : relationships.length}
            hint="Foreign key mappings defined"
            accent="ink"
          />
          <StatCard
            icon={ShieldCheck}
            label="Referential integrity"
            value={
              generationResult?.referential_integrity != null
                ? generationResult.referential_integrity
                  ? '100% valid'
                  : 'Invalid'
                : relationships.length > 0
                ? 'Configured'
                : 'Pending'
            }
            hint="Parent-child foreign key validity"
            accent={
              generationResult?.referential_integrity === false
                ? 'rose'
                : relationships.length > 0
                ? 'emerald'
                : 'amber'
            }
          />
          <StatCard
            icon={Sparkles}
            label="Multi-table generation"
            value={
              relationships.length > 0 && groupTables.length >= 2
                ? 'Ready'
                : 'Setup required'
            }
            hint="Relational synthesis capability"
            accent={
              relationships.length > 0 && groupTables.length >= 2
                ? 'emerald'
                : 'ink'
            }
          />
        </div>

        {/* Relationships + tables */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitBranch size={16} className="text-brand-600" />
                <h3 className="text-sm font-semibold text-ink-900">
                  Configured relationships ({relationships.length})
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setOpenAddRel(true)}
                disabled={!selectedGroupId}
                className="text-xs font-medium text-brand-600 hover:underline disabled:opacity-50"
              >
                + Add relationship
              </button>
            </div>

            {loadingRelationships ? (
              <div className="dx-card flex items-center justify-center p-12">
                <Loader2 size={20} className="animate-spin text-brand-600" />
              </div>
            ) : relationships.length === 0 ? (
              <div className="dx-card p-8 text-center">
                <GitBranch size={32} className="mx-auto mb-2 text-ink-300" />
                <h4 className="text-sm font-medium text-ink-900">
                  No relationships defined for this group
                </h4>
                <p className="mx-auto mt-1 max-w-sm text-xs text-ink-500">
                  Add a relationship between parent and child tables (such as
                  customers to orders) to enable relational synthetic
                  generation.
                </p>
                <button
                  type="button"
                  onClick={() => setOpenAddRel(true)}
                  disabled={!selectedGroupId}
                  className="dx-btn-primary mt-4"
                >
                  <Plus size={14} /> Create first relationship
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {relationships.map((rel) => {
                  const isDeleting = deletingRelId === rel.relationship_id
                  return (
                    <div
                      key={rel.relationship_id}
                      className="dx-card flex flex-col justify-between gap-4 p-4 sm:flex-row sm:items-center"
                    >
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2">
                          <Key size={14} className="text-brand-600" />
                          <div>
                            <span className="block text-[10px] font-semibold uppercase text-brand-600">
                              Parent (PK)
                            </span>
                            <span className="text-xs font-medium text-ink-900">
                              {rel.parent_table_name ||
                                `Dataset #${rel.parent_dataset_id}`}
                            </span>
                            <div className="mt-0.5 font-mono text-[11px] text-brand-700">
                              .{rel.parent_column}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 px-1 text-ink-400">
                          <span className="text-[10px] font-medium uppercase tracking-wider text-ink-500">
                            {rel.relationship_type || '1:N'}
                          </span>
                          <ArrowRight size={14} />
                        </div>

                        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
                          <GitBranch size={14} className="text-emerald-600" />
                          <div>
                            <span className="block text-[10px] font-semibold uppercase text-emerald-600">
                              Child (FK)
                            </span>
                            <span className="text-xs font-medium text-ink-900">
                              {rel.child_table_name ||
                                `Dataset #${rel.child_dataset_id}`}
                            </span>
                            <div className="mt-0.5 font-mono text-[11px] text-emerald-700">
                              .{rel.child_column}
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center">
                        <button
                          type="button"
                          onClick={() =>
                            handleDeleteRelationship(rel.relationship_id)
                          }
                          disabled={isDeleting}
                          title="Delete relationship"
                          className="rounded-lg p-2 text-ink-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                        >
                          {isDeleting ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Trash2 size={14} />
                          )}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Tables in group */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-brand-600" />
              <h3 className="text-sm font-semibold text-ink-900">
                Tables in group ({groupTables.length})
              </h3>
            </div>

            {unassignedDatasets.length > 0 && selectedGroupId && (
              <form onSubmit={handleAssignDataset} className="flex gap-2">
                <select
                  value={selectedDatasetToAssign}
                  onChange={(e) => setSelectedDatasetToAssign(e.target.value)}
                  className="dx-input cursor-pointer py-1.5 text-xs"
                >
                  <option value="">+ Assign another table…</option>
                  {unassignedDatasets.map((d) => {
                    const id = d.dataset_id ?? d.id
                    const name =
                      d.dataset_name ||
                      d.name ||
                      d.file_name ||
                      `Dataset #${id}`
                    return (
                      <option key={id} value={id}>
                        #{id} — {name}
                      </option>
                    )
                  })}
                </select>
                <button
                  type="submit"
                  disabled={!selectedDatasetToAssign || assigningTable}
                  className="dx-btn-outline shrink-0 text-xs"
                >
                  {assigningTable ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    'Add'
                  )}
                </button>
              </form>
            )}

            {loadingTables ? (
              <div className="dx-card flex items-center justify-center p-8">
                <Loader2 size={18} className="animate-spin text-brand-600" />
              </div>
            ) : groupTables.length === 0 ? (
              <div className="dx-card p-6 text-center text-xs text-ink-500">
                No tables in this group yet. Upload datasets with this group ID
                or assign existing datasets above.
              </div>
            ) : (
              <div className="max-h-[460px] space-y-2.5 overflow-y-auto pr-1">
                {groupTables.map((table) => {
                  const id = table.dataset_id ?? table.id
                  const name =
                    table.dataset_name ||
                    table.name ||
                    table.file_name ||
                    `Dataset #${id}`
                  return (
                    <div
                      key={id}
                      className="dx-card p-3.5 transition hover:border-brand-300"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-[10px] font-semibold text-ink-400">
                              #{id}
                            </span>
                            <span className="truncate text-xs font-medium text-ink-900">
                              {name}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center gap-3 text-[11px] text-ink-500">
                            <span>
                              {table.row_count != null
                                ? `${formatNumber(table.row_count)} rows`
                                : 'N/A rows'}
                            </span>
                            <span>•</span>
                            <span>
                              {table.column_count != null
                                ? `${table.column_count} cols`
                                : 'N/A cols'}
                            </span>
                          </div>
                        </div>
                        <Link
                          to={`/datasets/${id}/profile`}
                          className="text-[11px] font-medium text-brand-600 hover:underline"
                        >
                          Profile →
                        </Link>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Multi-table generation */}
        <div className="dx-card p-6">
          <div className="flex flex-col gap-4 border-b border-ink-100 pb-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles size={18} className="text-brand-600" />
                <h3 className="text-base font-semibold text-ink-900">
                  Multi-table synthetic generation
                </h3>
              </div>
              <p className="mt-1 text-xs text-ink-500">
                Fit generative models across all linked tables in this group
                and synthesize new data with 100% referential integrity
                guaranteed.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <select
                value={generationModel}
                onChange={(e) => setGenerationModel(e.target.value)}
                disabled={generating}
                className="dx-input cursor-pointer py-2 text-xs"
              >
                <option value="gaussian_copula">
                  Gaussian Copula (fast & relational)
                </option>
                <option value="ctgan">CTGAN (deep tabular GAN)</option>
                <option value="tvae">TVAE (variational autoencoder)</option>
              </select>

              <button
                type="button"
                onClick={handleGenerateMultiTable}
                disabled={
                  generating ||
                  !selectedGroupId ||
                  relationships.length === 0
                }
                className="dx-btn-primary"
              >
                {generating ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Synthesizing…
                  </>
                ) : (
                  <>
                    <PlayCircle size={14} />
                    Generate multi-table data
                  </>
                )}
              </button>
            </div>
          </div>

          {generating && (
            <div className="mt-6 flex flex-col items-center justify-center rounded-xl border border-dashed border-brand-200 bg-brand-50/40 p-8 text-center">
              <Loader2
                size={28}
                className="mb-3 animate-spin text-brand-600"
              />
              <p className="text-sm font-medium text-ink-900">
                Synthesizing multi-table datasets for group #{selectedGroupId}…
              </p>
              <p className="mt-1 text-xs text-ink-500">
                Generating rows and enforcing primary/foreign key mappings to
                guarantee 100% referential integrity.
              </p>
            </div>
          )}

          {generationResult && !generating && (
            <div className="mt-6 space-y-5">
              <div
                className={[
                  'flex items-center justify-between gap-4 rounded-xl border p-4',
                  generationResult.referential_integrity
                    ? 'border-emerald-200 bg-emerald-50'
                    : 'border-rose-200 bg-rose-50',
                ].join(' ')}
              >
                <div className="flex items-center gap-3">
                  {generationResult.referential_integrity ? (
                    <CheckCircle2
                      size={22}
                      className="shrink-0 text-emerald-600"
                    />
                  ) : (
                    <AlertCircle
                      size={22}
                      className="shrink-0 text-rose-600"
                    />
                  )}
                  <div>
                    <h4 className="text-sm font-semibold text-ink-900">
                      {generationResult.referential_integrity
                        ? 'Referential integrity: 100% preserved'
                        : 'Referential integrity failed'}
                    </h4>
                    <p className="text-xs text-ink-600">
                      {generationResult.referential_integrity
                        ? 'All synthetic child foreign keys exist in the generated parent tables. Zero orphaned records.'
                        : 'Some synthetic child records reference non-existent parent primary keys.'}
                    </p>
                  </div>
                </div>
                <span
                  className={[
                    'shrink-0 rounded-full px-3 py-1 text-xs font-semibold',
                    generationResult.referential_integrity
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-rose-100 text-rose-700',
                  ].join(' ')}
                >
                  {generationResult.referential_integrity ? 'Valid' : 'Invalid'}
                </span>
              </div>

              <div>
                <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-500">
                  Generated tables
                </h4>
                <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(generationResult.tables || {}).map(
                    ([dId, tbl]) => {
                      const isDownloading = downloadingId === tbl.dataset_id
                      return (
                        <div key={dId} className="dx-card space-y-3 p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5">
                                <FileSpreadsheet
                                  size={14}
                                  className="text-brand-600"
                                />
                                <span className="truncate text-xs font-semibold text-ink-900">
                                  {tbl.source_filename ||
                                    `Dataset #${tbl.dataset_id}`}
                                </span>
                              </div>
                              <p
                                className="mt-1 max-w-[200px] truncate font-mono text-[11px] text-ink-500"
                                title={tbl.file_name}
                              >
                                {tbl.file_name}
                              </p>
                            </div>
                            <span className="rounded-md border border-brand-200 bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-700">
                              #{tbl.dataset_id}
                            </span>
                          </div>

                          <div className="flex items-center justify-between border-t border-ink-100 pt-2 text-xs text-ink-500">
                            <span>
                              {tbl.row_count != null
                                ? `${formatNumber(tbl.row_count)} rows`
                                : 'N/A'}
                            </span>
                            <span>
                              {tbl.column_count != null
                                ? `${tbl.column_count} columns`
                                : 'N/A'}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 pt-1">
                            <button
                              type="button"
                              onClick={() => handleDownloadDataset(tbl)}
                              disabled={isDownloading}
                              className="dx-btn-outline w-full justify-center text-xs"
                            >
                              {isDownloading ? (
                                <Loader2
                                  size={14}
                                  className="animate-spin"
                                />
                              ) : (
                                <Download size={14} />
                              )}
                              Download CSV
                            </button>
                            <Link
                              to={`/datasets/${tbl.dataset_id}/evaluate${
                                tbl.result_id
                                  ? `?result_id=${tbl.result_id}`
                                  : ''
                              }`}
                              className="dx-btn-outline shrink-0 text-xs"
                              title="Evaluate this synthetic table"
                            >
                              Evaluate
                            </Link>
                          </div>
                        </div>
                      )
                    },
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <CreateGroupDialog
        open={openCreateGroup}
        onClose={() => setOpenCreateGroup(false)}
        onCreated={handleGroupCreated}
        defaultDomain="supply_chain"
      />

      <AddRelationshipDialog
        open={openAddRel}
        onClose={() => setOpenAddRel(false)}
        onCreated={handleRelationshipCreated}
        groupId={selectedGroupId}
        availableDatasets={
          groupTables.length >= 2 ? groupTables : allDatasets
        }
      />

      <Toast
        open={toast.open}
        type={toast.type}
        title={toast.title}
        message={toast.message}
        onClose={() => setToast((t) => ({ ...t, open: false }))}
      />
    </>
  )
}