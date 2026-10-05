export default function InfoGrid({ items }) {
  const visible = items.filter((i) => i && i.value != null && i.value !== '')
  if (visible.length === 0) return null

  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
      {visible.map(({ label, value }) => (
        <div key={label} className="min-w-0">
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            {label}
          </dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-ink-900">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  )
}