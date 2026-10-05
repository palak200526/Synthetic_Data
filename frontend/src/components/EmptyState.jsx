import { Inbox } from 'lucide-react'

export default function EmptyState({
  icon: Icon = Inbox,
  title = 'Nothing here yet',
  description,
  action,
}) {
  return (
    <div className="dx-card flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="grid h-11 w-11 place-items-center rounded-full bg-ink-100 text-ink-500">
        <Icon size={20} />
      </div>
      <div>
        <p className="text-sm font-semibold text-ink-900">{title}</p>
        {description && (
          <p className="mt-1 max-w-sm text-xs text-ink-500">{description}</p>
        )}
      </div>
      {action}
    </div>
  )
}