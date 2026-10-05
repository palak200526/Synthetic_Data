import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Loader2,
  ShieldCheck,
  Layers,
  Plus,
  ChevronDown,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import FileDropzone from '../components/FileDropzone.jsx'
import ErrorState from '../components/ErrorState.jsx'
import CreateGroupDialog from '../components/CreateGroupDialog.jsx'

import {
  datasetApi,
  isSupportedFile,
  ACCEPT_ATTR,
  SUPPORTED_EXTENSIONS,
} from '../api/datasetApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { saveBatch } from '../utils/batchStore.js'
import { loadLocalGroups } from '../api/groupApi.js'

export default function Upload() {
  const navigate = useNavigate()

  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')

  // Group + domain
  const [groups, setGroups] = useState(() => loadLocalGroups())
  const [groupId, setGroupId] = useState('')
  const [domainType, setDomainType] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    setGroups(loadLocalGroups())
  }, [dialogOpen])

  const multi = files.length > 1

  const validate = (f) => {
    if (!isSupportedFile(f)) {
      return `Unsupported file type. Allowed: ${SUPPORTED_EXTENSIONS.map(
        (e) => '.' + e,
      ).join(', ')}`
    }
    return null
  }

  const handleCreated = (created) => {
    if (created?.group_id != null) {
      setGroupId(String(created.group_id))
      if (created.domain_type) setDomainType(created.domain_type)
    }
    setGroups(loadLocalGroups())
  }

  const handleUpload = async () => {
    if (files.length === 0 || uploading) return
    setError('')
    setUploading(true)
    setProgress(0)

    try {
      const opts = { onProgress: setProgress }
      if (groupId) opts.groupId = Number(groupId)
      if (domainType.trim()) opts.domainType = domainType.trim()

      const res = await datasetApi.upload(files, opts)
      const data = res.data || {}
      const sessionId = data.session_id ?? null
      const list = Array.isArray(data.datasets) ? data.datasets : []

      if (list.length === 0) {
        setError('Upload succeeded but no datasets were returned.')
        return
      }

      const batch = list.map((d) => ({
        id: d?.dataset_id ?? d?.datasetId ?? d?.id,
        fileName: d?.file_name ?? null,
        storedFileName: d?.stored_file_name ?? null,
        uploadDate: d?.upload_date ?? null,
        rows: d?.data?.rows ?? null,
        columns: d?.data?.columns ?? null,
        columnNames: Array.isArray(d?.data?.column_names)
          ? d.data.column_names
          : [],
        groupId: d?.group_id ?? null,
        domainType: d?.domain_type ?? null,
      }))

      const firstId = batch[0].id
      if (firstId == null) {
        setError('Upload response had no dataset_id for the first file.')
        return
      }
      if (sessionId != null) saveBatch(sessionId, batch)

      const qs = sessionId != null ? `?session=${sessionId}` : ''
      navigate(`/datasets/${firstId}/profile${qs}`, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  const totalLabel =
    files.length === 0
      ? null
      : `${files.length} file${files.length > 1 ? 's' : ''} ready`

  return (
    <>
      <CreateGroupDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={handleCreated}
      />

      <PageHeader
        title="Upload dataset"
        subtitle="Import one or more tabular files to begin the Datrixa workflow."
        breadcrumb="Datasets · New"
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="dx-card p-5">
            <FileDropzone
              multiple
              files={files}
              onFiles={setFiles}
              accept={ACCEPT_ATTR}
              disabled={uploading}
              validate={validate}
              hint={`Supported: ${SUPPORTED_EXTENSIONS.join(', ')}`}
            />

            {uploading && (
              <div className="mt-4">
                <div className="mb-1 flex items-center justify-between text-[11px] text-ink-500">
                  <span>Uploading…</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                  <div
                    className="h-full rounded-full bg-brand-600 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4">
                <ErrorState title="Upload failed" message={error} />
              </div>
            )}

            <div className="mt-5 flex items-center justify-between gap-2">
              <span className="text-xs text-ink-500">{totalLabel}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="dx-btn-outline"
                  onClick={() => {
                    setFiles([])
                    setError('')
                    setProgress(0)
                  }}
                  disabled={files.length === 0 || uploading}
                >
                  Reset
                </button>
                <button
                  type="button"
                  className="dx-btn-primary"
                  onClick={handleUpload}
                  disabled={files.length === 0 || uploading}
                >
                  {uploading && <Loader2 size={14} className="animate-spin" />}
                  {uploading
                    ? 'Uploading…'
                    : files.length > 1
                    ? `Upload ${files.length} files`
                    : 'Upload and continue'}
                </button>
              </div>
            </div>
          </div>

          {/* ── Group / domain options ─────────────────────── */}
          {multi && (
            <div className="dx-card p-5">
              <div className="flex items-center gap-2 text-brand-600">
                <Layers size={16} />
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Dataset group (optional)
                </span>
              </div>
              <p className="mt-1 text-[11px] text-ink-500">
                Assign all files in this upload to a group. Required later for
                multi-table generation.
              </p>

              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink-700">
                    Group
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <select
                        value={groupId}
                        onChange={(e) => setGroupId(e.target.value)}
                        disabled={uploading}
                        className="dx-input appearance-none pr-9 cursor-pointer"
                      >
                        <option value="">— None —</option>
                        {groups.map((g) => (
                          <option key={g.id} value={g.id}>
                            {g.name} (#{g.id})
                            {g.domainType ? ` · ${g.domainType}` : ''}
                          </option>
                        ))}
                      </select>
                      <ChevronDown
                        size={14}
                        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => setDialogOpen(true)}
                      disabled={uploading}
                      className="dx-btn-outline shrink-0"
                      title="Create a new group"
                    >
                      <Plus size={14} /> New
                    </button>
                  </div>
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink-700">
                    Domain type (optional)
                  </span>
                  <input
                    type="text"
                    value={domainType}
                    onChange={(e) => setDomainType(e.target.value)}
                    disabled={uploading}
                    placeholder="e.g. retail, supply_chain"
                    className="dx-input"
                  />
                </label>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="dx-card p-5">
            <div className="flex items-center gap-2 text-brand-600">
              <ShieldCheck size={16} />
              <span className="text-xs font-semibold uppercase tracking-wider">
                What happens next
              </span>
            </div>
            <ol className="mt-3 space-y-2.5 text-xs text-ink-600">
              <li className="flex gap-2">
                <span className="text-ink-400">1.</span>
                Each file is stored and assigned its own dataset ID.
              </li>
              <li className="flex gap-2">
                <span className="text-ink-400">2.</span>
                Profiles are computed per file.
              </li>
              <li className="flex gap-2">
                <span className="text-ink-400">3.</span>
                Switch between them from the profile page.
              </li>
              <li className="flex gap-2">
                <span className="text-ink-400">4.</span>
                Multi-table groups enable joint generation.
              </li>
            </ol>
          </div>

          <div className="dx-card p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
              Notes
            </p>
            <ul className="mt-2 space-y-2 text-xs text-ink-600">
              <li>· Group and domain are optional for single files.</li>
              <li>· For multi-table generation, assign a group.</li>
              <li>· Groups are created on the backend and cached locally.</li>
            </ul>
          </div>
        </aside>
      </div>
    </>
  )
}