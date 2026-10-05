import { AlertTriangle } from 'lucide-react'

export default function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="dx-card border-red-200 bg-red-50/60 p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-red-100 text-red-600">
          <AlertTriangle size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-red-800">{title}</p>
          {message && <p className="mt-0.5 text-xs text-red-700">{message}</p>}
          {onRetry && (
            <button onClick={onRetry} className="dx-btn-outline mt-3 text-xs">
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  )
}