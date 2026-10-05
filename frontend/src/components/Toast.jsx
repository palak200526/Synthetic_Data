import { useEffect } from 'react'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'

const VARIANTS = {
  success: { icon: CheckCircle2, className: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  error:   { icon: AlertCircle,  className: 'border-rose-200 bg-rose-50 text-rose-800' },
  info:    { icon: Info,         className: 'border-ink-200 bg-white text-ink-800' },
}

export default function Toast({ open, type = 'success', title, message, onClose, duration = 4000 }) {
  useEffect(() => {
    if (!open) return
    const t = setTimeout(onClose, duration)
    return () => clearTimeout(t)
  }, [open, duration, onClose])

  if (!open) return null
  const v = VARIANTS[type] || VARIANTS.info
  const Icon = v.icon

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 w-full max-w-sm">
      <div className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-4 shadow-lg ${v.className}`}>
        <Icon size={18} className="mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          {title && <p className="text-sm font-semibold">{title}</p>}
          {message && <p className="mt-0.5 text-xs opacity-90">{message}</p>}
        </div>
        <button onClick={onClose} className="shrink-0 opacity-60 hover:opacity-100" aria-label="Dismiss">
          <X size={14} />
        </button>
      </div>
    </div>
  )
}