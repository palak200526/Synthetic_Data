export default function PageHeader({ title, subtitle, actions, breadcrumb }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {breadcrumb && (
          <div className="mb-1 text-xs text-ink-400">{breadcrumb}</div>
        )}
        <h1 className="text-xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {subtitle && (
          <p className="mt-1 text-sm text-ink-500">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}