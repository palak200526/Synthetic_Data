import { Check, Circle, ArrowRight, UploadCloud, ScanSearch, SlidersHorizontal, WandSparkles, Cpu, ShieldCheck, FileText } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { getLastSessionId, loadBatch } from '../utils/batchStore.js'

const STEPS = [
  { key: 'upload', label: 'Upload', short: 'Upload dataset', description: 'Add a CSV or Excel file', icon: UploadCloud },
  { key: 'profile', label: 'Profile', short: 'Inspect data', description: 'Review columns and data quality', icon: ScanSearch },
  { key: 'columns', label: 'Column setup', short: 'Configure columns', description: 'Review LLM suggestions and actions', icon: SlidersHorizontal },
  { key: 'preprocess', label: 'Preprocess', short: 'Prepare data', description: 'Apply and validate your configuration', icon: WandSparkles },
  { key: 'generate', label: 'Generate', short: 'Create synthetic data', description: 'Choose a model and generate data', icon: Cpu },
  { key: 'evaluate', label: 'Evaluate', short: 'Check quality', description: 'Compare utility, similarity and privacy', icon: ShieldCheck },
  { key: 'reports', label: 'Reports', short: 'Export results', description: 'Review and download outputs', icon: FileText },
]

function getCurrentStep(pathname) {
  if (pathname === '/upload') return 0
  if (/\/profile\/?$/.test(pathname)) return 1
  if (/\/columns\/?$/.test(pathname)) return 2
  if (/\/preprocess\/?$/.test(pathname)) return 3
  if (/\/generate\/?$/.test(pathname)) return 4
  if (/\/(evaluate|quality-improvement)\/?$/.test(pathname)) return 5
  if (pathname === '/reports') return 6
  return -1
}

export default function WorkflowStepper() {
  const location = useLocation()
  const currentIndex = getCurrentStep(location.pathname)
  const datasetMatch = location.pathname.match(/^\/datasets\/([^/]+)/)
  const session = new URLSearchParams(location.search).get('session')
  const lastSessionId = session || getLastSessionId()
  const lastBatch = lastSessionId ? loadBatch(lastSessionId) : []
  const storedDatasetId = lastBatch.length ? lastBatch[lastBatch.length - 1]?.id : null
  const datasetId = datasetMatch?.[1] || (storedDatasetId != null ? String(storedDatasetId) : null)

  // Keep this component limited to the dataset journey, not unrelated settings/history pages.
  if (currentIndex < 0) return null

  const hrefFor = (step) => {
    if (step.key === 'upload') return '/upload'
    if (step.key === 'reports') return '/reports'
    if (!datasetId) return null
    const query = session ? `?session=${encodeURIComponent(session)}` : ''
    return `/datasets/${datasetId}/${step.key}${query}`
  }

  const current = STEPS[currentIndex]
  const progress = ((currentIndex + 1) / STEPS.length) * 100
  const canNavigate = Boolean(datasetId)

  return (
    <section aria-label="Dataset workflow" className="mb-6 overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-[0_2px_8px_rgba(15,23,42,0.035)]">
      <div className="flex flex-col gap-4 border-b border-ink-100 px-4 py-4 sm:px-5 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-brand-700">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-600" /> Guided workflow
          </div>
          <h2 className="mt-1 text-base font-semibold text-ink-900">{current.short}</h2>
          <p className="mt-0.5 text-sm text-ink-500">{current.description}. Follow the steps below to complete your dataset journey.</p>
        </div>
        <div className="flex shrink-0 items-center gap-3 md:min-w-40 md:justify-end">
          <div className="min-w-28 flex-1 md:flex-none">
            <div className="mb-1.5 flex items-center justify-between gap-3 text-xs text-ink-500">
              <span>Step {currentIndex + 1} of {STEPS.length}</span>
              <span className="font-medium text-ink-700">{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-ink-100">
              <div className="h-full rounded-full bg-brand-600 transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </div>

      <nav aria-label="Workflow steps" className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-4 sm:p-4 lg:grid-cols-7">
        {STEPS.map((step, index) => {
          const Icon = step.icon
          const isCurrent = index === currentIndex
          const isPast = index < currentIndex
          const href = hrefFor(step)
          // Allow navigation only to the immediately previous or next step.
          // All other steps remain visible but disabled to prevent skipping ahead.
          const isAdjacent = Math.abs(index - currentIndex) === 1
          const isClickable = Boolean(href) && isAdjacent
          const content = (
            <>
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border transition-colors ${isCurrent ? 'border-brand-600 bg-brand-600 text-white shadow-sm' : isPast ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-ink-200 bg-ink-50 text-ink-400'}`}>
                {isPast ? <Check size={15} strokeWidth={2.5} /> : <Icon size={15} strokeWidth={2} />}
              </div>
              <div className="min-w-0 flex-1">
                <div className={`truncate text-xs font-semibold ${isCurrent ? 'text-brand-700' : isPast ? 'text-ink-800' : 'text-ink-500'}`}>{step.label}</div>
                <div className="mt-0.5 text-[10px] leading-4 text-ink-400">{isCurrent ? 'You are here' : isPast ? 'Previous step' : 'Up next'}</div>
              </div>
              {isClickable && <ArrowRight size={13} className="ml-auto hidden shrink-0 text-ink-300 group-hover:text-brand-600 sm:block" />}
            </>
          )
          const classes = `group flex min-h-[58px] items-center gap-2 rounded-xl border px-2.5 py-2 text-left transition-all ${isCurrent ? 'border-brand-200 bg-brand-50/70 ring-1 ring-brand-100' : isPast ? 'border-ink-100 bg-white hover:border-brand-200 hover:bg-brand-50/40' : 'border-ink-100 bg-white'} ${isClickable ? 'cursor-pointer' : ''}`
          return isClickable ? (
            <Link key={step.key} to={href} className={classes} aria-label={`Go to ${step.label}`}>
              {content}
            </Link>
          ) : (
            <div key={step.key} className={classes} aria-current={isCurrent ? 'step' : undefined} aria-disabled={!href && !isCurrent}>
              {content}
            </div>
          )
        })}
      </nav>
      <div className="flex items-start gap-2 border-t border-ink-100 bg-ink-50/60 px-4 py-3 sm:px-5">
        <Circle size={14} className="mt-0.5 shrink-0 fill-brand-100 text-brand-600" />
        <p className="text-xs leading-5 text-ink-500"><span className="font-semibold text-ink-700">Tip:</span> Use the previous or next step to move through the workflow in order. Other steps are disabled to help you avoid skipping required actions.</p>
      </div>
    </section>
  )
}
