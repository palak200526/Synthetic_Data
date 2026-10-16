// src/components/evaluation/MlTargetSelector.jsx
import { useEffect, useState } from 'react'
import { ChevronDown, Sparkles, AlertCircle, AlertTriangle, Play, RefreshCw, ArrowRight } from 'lucide-react'

export default function MLTargetSelector({ raw = {}, disabled, onChange }) {
  const options = Array.isArray(raw?.target_options) ? raw.target_options : []
  const status = raw?.status || 'pending_target'
  const suggestedTarget = raw?.suggested_target
  const suggestedSource = raw?.suggested_source
  const suggestedReason = raw?.suggested_reason
  const currentTarget = raw?.target_column

  const defaultSelection = currentTarget || suggestedTarget || options[0]?.column || ''
  const [selectedTarget, setSelectedTarget] = useState(defaultSelection)
  const [isEditing, setIsEditing] = useState(status !== 'evaluated')

  useEffect(() => {
    if (currentTarget) {
      setSelectedTarget(currentTarget)
    } else if (suggestedTarget) {
      setSelectedTarget(suggestedTarget)
    } else if (options.length > 0 && !selectedTarget) {
      setSelectedTarget(options[0]?.column || '')
    }
  }, [currentTarget, suggestedTarget, options])

  useEffect(() => {
    if (status !== 'evaluated') {
      setIsEditing(true)
    } else {
      setIsEditing(false)
    }
  }, [status, currentTarget])

  if (options.length === 0) {
    return (
      <div className="mb-4 rounded-xl border border-ink-200 bg-ink-50/50 p-4 text-xs text-ink-600">
        No columns in this dataset are suitable for machine learning utility evaluation.
      </div>
    )
  }

  const handleProceed = () => {
    if (selectedTarget && onChange) {
      onChange(selectedTarget)
    }
  }

  // Evaluated state - Compact view with "Change target" link
  if (status === 'evaluated' && !isEditing) {
    return (
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ink-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-700">
          <span className="font-semibold text-ink-900">Target column:</span>
          <span className="font-mono font-medium rounded bg-ink-100 px-2 py-0.5 text-ink-800">
            {currentTarget}
          </span>
          {raw.task_type && (
            <span className="capitalize text-ink-500">
              ({raw.task_type})
            </span>
          )}
        </div>
        <button
          type="button"
          disabled={disabled}
          onClick={() => setIsEditing(true)}
          className="text-xs font-semibold text-brand-600 hover:text-brand-700 hover:underline disabled:opacity-50"
        >
          Change target
        </button>
      </div>
    )
  }

  // Un-evaluated or Editing state - Prompt Card with Dropdown & Proceed button
  let promptMessage = null
  if (suggestedSource === 'llm' && suggestedTarget) {
    promptMessage = (
      <span>
        LLM suggests <strong className="font-semibold text-ink-900">{suggestedTarget}</strong> as target
        {suggestedReason ? ` (${suggestedReason})` : ''}. Proceed, or choose another.
      </span>
    )
  } else if (suggestedSource === 'unavailable') {
    promptMessage = (
      <span>
        Local LLM is unavailable. Pick a target column below.
      </span>
    )
  } else {
    promptMessage = (
      <span>
        Choose a target column to evaluate ML Utility.
      </span>
    )
  }

  return (
    <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50/30 p-4 shadow-sm">
      <div className="mb-3 flex items-start gap-2.5">
        <div className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded bg-brand-100 text-brand-700">
          <Sparkles size={12} />
        </div>
        <p className="text-xs leading-relaxed text-ink-700">
          {promptMessage}
        </p>
      </div>

      {status === 'not_applicable' && raw.reason && (
        <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-600" />
            <div>
              <p className="font-medium">{raw.reason}</p>
              {raw.reason_detail && (
                <p className="mt-1 font-mono text-[11px] text-amber-700">
                  Technical detail: {raw.reason_detail}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <select
            id="ml-target-select"
            value={selectedTarget}
            disabled={disabled}
            onChange={(e) => setSelectedTarget(e.target.value)}
            className="dx-input w-full cursor-pointer appearance-none bg-white pr-9 text-xs font-medium"
          >
            {options.map((o) => (
              <option key={o.column} value={o.column}>
                {o.column} — {o.task_type} · {o.unique_values} unique values
              </option>
            ))}
          </select>
          <ChevronDown
            size={14}
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={disabled || !selectedTarget}
            onClick={handleProceed}
            className="dx-btn-primary shrink-0 py-2 px-4 text-xs font-semibold inline-flex items-center gap-1.5"
          >
            {disabled ? <RefreshCw size={12} className="animate-spin" /> : <ArrowRight size={12} />}
            Proceed
          </button>

          {status === 'evaluated' && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => setIsEditing(false)}
              className="dx-btn-outline shrink-0 py-2 px-3 text-xs"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}