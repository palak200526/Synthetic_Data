import { useEffect, useState } from 'react'
import { Loader2, X, GitBranch, ArrowRight, Key, Link2 } from 'lucide-react'
import { relationshipApi } from '../api/relationshipApi.js'
import { datasetApi } from '../api/datasetApi.js'
import { getErrorMessage } from '../utils/errors.js'

export default function AddRelationshipDialog({
  open,
  onClose,
  onCreated,
  groupId,
  availableDatasets = [],
}) {
  const [parentDatasetId, setParentDatasetId] = useState('')
  const [parentColumn, setParentColumn] = useState('')
  const [parentColumns, setParentColumns] = useState([])
  const [loadingParentCols, setLoadingParentCols] = useState(false)

  const [childDatasetId, setChildDatasetId] = useState('')
  const [childColumn, setChildColumn] = useState('')
  const [childColumns, setChildColumns] = useState([])
  const [loadingChildCols, setLoadingChildCols] = useState(false)

  const [relationshipType, setRelationshipType] = useState('one-to-many')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setError('')
      setSaving(false)
      if (availableDatasets.length >= 2) {
        setParentDatasetId(
          String(availableDatasets[0].dataset_id ?? availableDatasets[0].id),
        )
        setChildDatasetId(
          String(availableDatasets[1].dataset_id ?? availableDatasets[1].id),
        )
      } else if (availableDatasets.length === 1) {
        setParentDatasetId(
          String(availableDatasets[0].dataset_id ?? availableDatasets[0].id),
        )
        setChildDatasetId('')
      } else {
        setParentDatasetId('')
        setChildDatasetId('')
      }
      setParentColumn('')
      setChildColumn('')
      setParentColumns([])
      setChildColumns([])
      setRelationshipType('one-to-many')
    }
  }, [open, availableDatasets])

  useEffect(() => {
    const onEsc = (e) => {
      if (e.key === 'Escape' && open && !saving) onClose?.()
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [open, saving, onClose])

  useEffect(() => {
    if (!parentDatasetId) {
      setParentColumns([])
      setParentColumn('')
      return
    }
    let cancelled = false
    setLoadingParentCols(true)
    datasetApi
      .getColumns(parentDatasetId)
      .then((res) => {
        if (cancelled) return
        const cols = res.data?.columns || []
        setParentColumns(cols)
        if (cols.length > 0) {
          const idCol = cols.find((c) => c.name.toLowerCase().includes('id'))
          setParentColumn(idCol ? idCol.name : cols[0].name)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn('Failed to load parent columns:', err)
          setParentColumns([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingParentCols(false)
      })
    return () => {
      cancelled = true
    }
  }, [parentDatasetId])

  useEffect(() => {
    if (!childDatasetId) {
      setChildColumns([])
      setChildColumn('')
      return
    }
    let cancelled = false
    setLoadingChildCols(true)
    datasetApi
      .getColumns(childDatasetId)
      .then((res) => {
        if (cancelled) return
        const cols = res.data?.columns || []
        setChildColumns(cols)
        if (cols.length > 0) {
          const matching = cols.find(
            (c) =>
              parentColumn &&
              c.name.toLowerCase() === parentColumn.toLowerCase(),
          )
          const idCol = cols.find((c) => c.name.toLowerCase().includes('id'))
          setChildColumn(
            matching ? matching.name : idCol ? idCol.name : cols[0].name,
          )
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn('Failed to load child columns:', err)
          setChildColumns([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingChildCols(false)
      })
    return () => {
      cancelled = true
    }
  }, [childDatasetId, parentColumn])

  if (!open) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!groupId) {
      setError(
        'Group ID is required. Please select or create a dataset group first.',
      )
      return
    }
    if (!parentDatasetId) {
      setError('Please select a parent dataset.')
      return
    }
    if (!parentColumn) {
      setError('Please select a parent primary key column.')
      return
    }
    if (!childDatasetId) {
      setError('Please select a child dataset.')
      return
    }
    if (!childColumn) {
      setError('Please select a child foreign key column.')
      return
    }
    if (String(parentDatasetId) === String(childDatasetId)) {
      setError('Parent and child datasets must be different tables.')
      return
    }

    setSaving(true)
    try {
      const result = await relationshipApi.create({
        groupId,
        parentDatasetId,
        parentColumn,
        childDatasetId,
        childColumn,
        relationshipType,
      })
      onCreated?.(result)
      onClose?.()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const getDatasetLabel = (d) => {
    const id = d.dataset_id ?? d.id
    const name = d.dataset_name || d.name || d.file_name || `Dataset ${id}`
    const rows = d.row_count != null ? ` (${d.row_count} rows)` : ''
    return `#${id} - ${name}${rows}`
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-relationship-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose?.()
      }}
    >
      <div className="relative w-full max-w-xl rounded-2xl border border-ink-200 bg-white p-6 shadow-xl sm:p-7">
        <button
          type="button"
          onClick={onClose}
          disabled={saving}
          aria-label="Close dialog"
          className="absolute right-4 top-4 rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700 disabled:opacity-50"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
            <GitBranch size={20} />
          </div>
          <div>
            <h2
              id="add-relationship-title"
              className="text-lg font-semibold text-ink-900"
            >
              Create table relationship
            </h2>
            <p className="text-xs text-ink-500">
              Define a foreign key link between datasets to preserve
              referential integrity.
            </p>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          {/* PARENT TABLE */}
          <div className="space-y-3 rounded-xl border border-ink-200 bg-ink-50/60 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-600">
              <Key size={13} />
              <span>Parent table (primary key source)</span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-700">
                  Parent dataset
                </label>
                <select
                  value={parentDatasetId}
                  onChange={(e) => setParentDatasetId(e.target.value)}
                  disabled={saving}
                  className="dx-input cursor-pointer text-xs"
                >
                  <option value="">Select parent dataset…</option>
                  {availableDatasets.map((d) => {
                    const id = d.dataset_id ?? d.id
                    return (
                      <option key={id} value={id}>
                        {getDatasetLabel(d)}
                      </option>
                    )
                  })}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-ink-700">
                  Primary key column
                </label>
                <div className="relative">
                  <select
                    value={parentColumn}
                    onChange={(e) => setParentColumn(e.target.value)}
                    disabled={
                      saving || loadingParentCols || parentColumns.length === 0
                    }
                    className="dx-input cursor-pointer pr-9 text-xs disabled:opacity-60"
                  >
                    {loadingParentCols ? (
                      <option value="">Loading columns…</option>
                    ) : parentColumns.length === 0 ? (
                      <option value="">Select dataset first</option>
                    ) : (
                      parentColumns.map((c) => (
                        <option key={c.name} value={c.name}>
                          {c.name} ({c.type})
                        </option>
                      ))
                    )}
                  </select>
                  {loadingParentCols && (
                    <Loader2 className="absolute right-3 top-2.5 h-3.5 w-3.5 animate-spin text-ink-400" />
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* CONNECTOR */}
          <div className="flex items-center justify-center gap-2 py-0.5 text-ink-400">
            <span className="h-px w-16 bg-ink-200" />
            <div className="flex items-center gap-1.5 rounded-full border border-ink-200 bg-white px-2.5 py-0.5 font-mono text-[11px] text-ink-500">
              <Link2 size={12} className="text-brand-600" />
              <span>references</span>
              <ArrowRight size={12} />
            </div>
            <span className="h-px w-16 bg-ink-200" />
          </div>

          {/* CHILD TABLE */}
          <div className="space-y-3 rounded-xl border border-ink-200 bg-ink-50/60 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-600">
              <GitBranch size={13} />
              <span>Child table (foreign key holder)</span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-700">
                  Child dataset
                </label>
                <select
                  value={childDatasetId}
                  onChange={(e) => setChildDatasetId(e.target.value)}
                  disabled={saving}
                  className="dx-input cursor-pointer text-xs"
                >
                  <option value="">Select child dataset…</option>
                  {availableDatasets
                    .filter(
                      (d) =>
                        String(d.dataset_id ?? d.id) !==
                        String(parentDatasetId),
                    )
                    .map((d) => {
                      const id = d.dataset_id ?? d.id
                      return (
                        <option key={id} value={id}>
                          {getDatasetLabel(d)}
                        </option>
                      )
                    })}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-ink-700">
                  Foreign key column
                </label>
                <div className="relative">
                  <select
                    value={childColumn}
                    onChange={(e) => setChildColumn(e.target.value)}
                    disabled={
                      saving || loadingChildCols || childColumns.length === 0
                    }
                    className="dx-input cursor-pointer pr-9 text-xs disabled:opacity-60"
                  >
                    {loadingChildCols ? (
                      <option value="">Loading columns…</option>
                    ) : childColumns.length === 0 ? (
                      <option value="">Select dataset first</option>
                    ) : (
                      childColumns.map((c) => (
                        <option key={c.name} value={c.name}>
                          {c.name} ({c.type})
                        </option>
                      ))
                    )}
                  </select>
                  {loadingChildCols && (
                    <Loader2 className="absolute right-3 top-2.5 h-3.5 w-3.5 animate-spin text-ink-400" />
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* CARDINALITY */}
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-700">
              Relationship cardinality
            </label>
            <select
              value={relationshipType}
              onChange={(e) => setRelationshipType(e.target.value)}
              disabled={saving}
              className="dx-input cursor-pointer text-xs"
            >
              <option value="one-to-many">
                One-to-many (1 parent record maps to multiple child records)
              </option>
              <option value="many-to-one">
                Many-to-one (multiple records share a parent)
              </option>
              <option value="one-to-one">
                One-to-one (single unique link per record)
              </option>
            </select>
          </div>

          <div className="mt-6 flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="dx-btn-outline"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !parentColumn || !childColumn}
              className="dx-btn-primary"
            >
              {saving ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <GitBranch size={14} />
                  Create relationship
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}