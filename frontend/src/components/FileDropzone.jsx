import { useCallback, useRef, useState } from 'react'
import { UploadCloud, FileCheck2, X } from 'lucide-react'

export default function FileDropzone({
  accept,
  onFiles,
  files = [],
  multiple = false,
  disabled,
  hint,
  validate,
}) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState('')

  const handle = useCallback(
    (incoming) => {
      setLocalError('')
      const list = Array.from(incoming || [])
      if (list.length === 0) return

      if (!multiple && list.length > 1) {
        onFiles(list.slice(0, 1))
        return
      }

      if (validate) {
        for (const f of list) {
          const err = validate(f)
          if (err) {
            setLocalError(err)
            return
          }
        }
      }
      onFiles(list)
    },
    [onFiles, validate, multiple],
  )

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    handle(e.dataTransfer.files)
  }

  const onDragOver = (e) => {
    e.preventDefault()
    if (!disabled) setDragging(true)
  }

  const onDragLeave = () => setDragging(false)

  const removeAt = (e, i) => {
    e.stopPropagation()
    setLocalError('')
    const next = files.filter((_, idx) => idx !== i)
    onFiles(next)
    if (inputRef.current) inputRef.current.value = ''
  }

  const clearAll = (e) => {
    e.stopPropagation()
    setLocalError('')
    onFiles([])
    if (inputRef.current) inputRef.current.value = ''
  }

  const hasFiles = files.length > 0

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) =>
          (e.key === 'Enter' || e.key === ' ') &&
          !disabled &&
          inputRef.current?.click()
        }
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={[
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition cursor-pointer',
          dragging
            ? 'border-brand-400 bg-brand-50/60'
            : 'border-ink-200 bg-white hover:border-brand-300 hover:bg-ink-50/60',
          disabled ? 'opacity-60 cursor-not-allowed' : '',
        ].join(' ')}
      >
        <div
          className={[
            'grid h-11 w-11 place-items-center rounded-full',
            hasFiles ? 'bg-emerald-50 text-emerald-600' : 'bg-brand-50 text-brand-600',
          ].join(' ')}
        >
          {hasFiles ? <FileCheck2 size={20} /> : <UploadCloud size={20} />}
        </div>

        <div>
          <p className="text-sm font-medium text-ink-900">
            {hasFiles
              ? `${files.length} file${files.length > 1 ? 's' : ''} selected`
              : 'Drop files here, or click to browse'}
          </p>
          {hint && <p className="mt-1 text-xs text-ink-500">{hint}</p>}
          {multiple && !hasFiles && (
            <p className="mt-1 text-[11px] text-ink-400">
              You can select multiple files at once.
            </p>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          disabled={disabled}
          onChange={(e) => handle(e.target.files)}
        />
      </div>

      {localError && <p className="mt-2 text-xs text-rose-600">{localError}</p>}

      {hasFiles && (
        <ul className="mt-3 space-y-1.5">
          {files.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              className="flex items-center justify-between gap-3 rounded-lg border border-ink-200 bg-ink-50/60 px-3 py-2 text-xs"
            >
              <span className="min-w-0 truncate font-medium text-ink-700">
                {f.name}
              </span>
              <span className="shrink-0 text-ink-400">
                {(f.size / 1024).toFixed(1)} KB
              </span>
              {!disabled && (
                <button
                  type="button"
                  onClick={(e) => removeAt(e, i)}
                  className="shrink-0 text-ink-400 hover:text-rose-600"
                  title="Remove"
                >
                  <X size={12} />
                </button>
              )}
            </li>
          ))}
          {!disabled && files.length > 1 && (
            <li className="pt-1 text-right">
              <button
                type="button"
                onClick={clearAll}
                className="text-[11px] text-ink-500 hover:text-rose-600"
              >
                Clear all
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}