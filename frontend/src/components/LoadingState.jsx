import { Loader2 } from 'lucide-react'

export default function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-ink-500">
      <Loader2 size={16} className="animate-spin" />
      <span>{label}</span>
    </div>
  )
}