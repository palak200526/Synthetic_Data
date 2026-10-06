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

export function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString()
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