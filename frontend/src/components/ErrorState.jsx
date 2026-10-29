import { AlertTriangle, ChevronDown, Lightbulb } from 'lucide-react'

export default function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  const rawMessage = String(message || '')
  const isLlmTextFailure =
    /Could not generate valid, non-placeholder strings/i.test(rawMessage) ||
    /unfulfilled records after batch and per-record retries/i.test(rawMessage)

  const columnMatch = rawMessage.match(/column\s+[\'\"]([^\'\"]+)[\'\"]/i)
  const columnName = columnMatch?.[1]
  const friendlyTitle = isLlmTextFailure ? 'Some text values could not be generated' : title

  return (
    <div className="dx-card border-red-200 bg-red-50/70 p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-red-100 text-red-600">
          <AlertTriangle size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-red-900">{friendlyTitle}</p>

          {isLlmTextFailure ? (
            <>
              <p className="mt-1 text-sm leading-6 text-red-800">
                The local Ollama model could not produce valid text for every row
                {columnName ? <> in <strong>{columnName}</strong></> : ''}. Its response may
                have been incomplete, too similar to the source examples, or formatted
                unexpectedly. Datrixa stopped rather than saving placeholder text.
              </p>
              <div className="mt-3 rounded-lg border border-red-200 bg-white/70 p-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-red-900">
                  <Lightbulb size={14} /> What you can try
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-red-800">
                  <li>Retry generation once the Ollama model is ready.</li>
                  <li>If it happens again, reduce the LLM text batch size in generation parameters.</li>
                  <li>Check that Ollama is running and the selected model is available.</li>
                  <li>Review the column examples and configuration for {columnName ? `“${columnName}”` : 'the affected text column'}.</li>
                </ul>
              </div>
              <details className="mt-3 rounded-lg border border-red-200/80 bg-white/50 px-3 py-2">
                <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-red-800">
                  <ChevronDown size={14} /> Technical details
                </summary>
                <p className="mt-2 break-words font-mono text-[11px] leading-5 text-red-700">{rawMessage}</p>
              </details>
            </>
          ) : (
            message && <p className="mt-1 break-words text-xs leading-5 text-red-700">{message}</p>
          )}

          {onRetry && (
            <button onClick={onRetry} className="dx-btn-outline mt-4 border-red-300 bg-white text-xs text-red-800 hover:bg-red-100">
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
