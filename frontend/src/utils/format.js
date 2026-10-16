export function formatNumber(n, options = {}) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const { decimals } = options
  if (decimals != null) {
    return new Intl.NumberFormat(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(n)
  }
  return new Intl.NumberFormat().format(n)
}

export function formatPercent(n, digits = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

/**
 * Parse a timestamp coming from the backend.
 * Postgres TIMESTAMP columns are serialised without a timezone
 * ("2026-10-13T05:19:57"), which `new Date()` would read as *local* time.
 * The server stores UTC, so treat zone-less strings as UTC.
 */
export function parseServerDate(value) {
  if (!value) return null
  if (value instanceof Date) return value
  let v = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(v) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(v)) {
    v = v.replace(' ', 'T') + 'Z'
  }
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTime(value) {
  if (!value) return '—'
  const d = parseServerDate(value)
  if (!d) return String(value)
  return d.toLocaleString()
}

export function formatTime(value) {
  if (!value) return '—'
  const d = parseServerDate(value)
  if (!d) return String(value)
  return d.toLocaleTimeString()
}

export function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(bytes)) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let n = bytes
  let u = 0
  while (n >= 1024 && u < units.length - 1) {
    n /= 1024
    u++
  }
  return `${n.toFixed(n >= 10 || u === 0 ? 0 : 1)} ${units[u]}`
}