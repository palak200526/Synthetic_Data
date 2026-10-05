export default function FormField({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  autoComplete,
  error,
  disabled,
  rightSlot,
  hint,
}) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-xs font-medium text-ink-700">
          {label}
        </span>
      )}
      <div className="relative">
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          disabled={disabled}
          className={[
            'dx-input',
            error ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' : '',
            rightSlot ? 'pr-10' : '',
          ].join(' ')}
        />
        {rightSlot && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-2">
            {rightSlot}
          </div>
        )}
      </div>
      {error ? (
        <span className="mt-1 block text-[11px] text-red-600">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-[11px] text-ink-400">{hint}</span>
      ) : null}
    </label>
  )
}