import { useEffect, useState } from 'react'
import { Loader2, X, Layers } from 'lucide-react'
import { groupApi } from '../api/groupApi.js'
import { getErrorMessage } from '../utils/errors.js'

export default function CreateGroupDialog({
  open,
  onClose,
  onCreated,
  defaultDomain,
}) {
  const [name, setName] = useState('')
  const [domain, setDomain] = useState(defaultDomain || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setName('')
      setDomain(defaultDomain || '')
      setError('')
      setSaving(false)
    }
  }, [open, defaultDomain])

  useEffect(() => {
    const onEsc = (e) => {
      if (e.key === 'Escape' && open && !saving) onClose?.()
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [open, saving, onClose])

  if (!open) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!name.trim()) {
      setError('Group name is required.')
      return
    }
    if (!domain.trim()) {
      setError('Domain type is required.')
      return
    }

    setSaving(true)
    try {
      const created = await groupApi.create({
        groupName: name.trim(),
        domainType: domain.trim(),
      })
      onCreated?.(created)
      onClose?.()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-50 text-brand-600">
              <Layers size={16} />
            </div>
            <div>
              <p className="text-sm font-semibold text-ink-900">
                Create dataset group
              </p>
              <p className="text-[11px] text-ink-500">
                Used for multi-table generation.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="text-ink-400 hover:text-ink-700"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-ink-700">
              Group name
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. maven_orders"
              disabled={saving}
              autoFocus
              className="dx-input"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-ink-700">
              Domain type
            </span>
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g. supply_chain, retail, finance"
              disabled={saving}
              className="dx-input"
            />
            <span className="mt-1 block text-[11px] text-ink-400">
              A short label describing the domain. Free-form.
            </span>
          </label>

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              className="dx-btn-outline"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
            <button type="submit" className="dx-btn-primary" disabled={saving}>
              {saving && <Loader2 size={14} className="animate-spin" />}
              {saving ? 'Creating…' : 'Create group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}