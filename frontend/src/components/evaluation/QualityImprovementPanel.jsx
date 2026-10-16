import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle2,
  ShieldCheck,
  Download,
  Loader2,
  AlertCircle,
  Layers,
  ArrowRight,
  Info,
  ChevronRight,
  Table,
} from 'lucide-react'
import apiClient from '../../api/client.js'
import { generationApi } from '../../api/generationApi.js'
import { getErrorMessage } from '../../utils/errors.js'

export default function QualityImprovementPanel({
  resultId,
  datasetId,
  targetColumn,
  onImprovementSuccess,
}) {
  const location = useLocation()
  const returnTo = `${location.pathname}${location.search}`
  const returnToParam = `return_to=${encodeURIComponent(returnTo)}`
  const [improving, setImproving] = useState(false)
  const [error, setError] = useState('')
  const [comparisonData, setComparisonData] = useState(null)
  const [activePreviewTab, setActivePreviewTab] = useState('improved')
  const [downloading, setDownloading] = useState(false)

  const handleImproveQuality = async () => {
    if (!resultId || improving) return
    setError('')
    setImproving(true)

    try {
      const res = await generationApi.improveQuality({
        resultId,
        targetColumn,
        maxAttempts: 3,
        improvementThreshold: 1.0,
      })

      const data = res.data
      setComparisonData(data)
      if (onImprovementSuccess) {
        onImprovementSuccess(data)
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setImproving(false)
    }
  }

  const handleDownloadImproved = async () => {
    if (!comparisonData?.improved_result_id) return
    setDownloading(true)
    try {
      const res = await apiClient.get('/download', {
        params: {
          result_id: comparisonData.improved_result_id,
          type: 'dataset',
        },
        responseType: 'blob',
        timeout: 5 * 60 * 1000,
      })

      const fileName =
        comparisonData.improved_file_name ||
        `synthetic_improved_${comparisonData.improved_result_id}.csv`

      const blob = new Blob([res.data], {
        type: res.headers?.['content-type'] || 'application/octet-stream',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(`Download failed: ${getErrorMessage(err)}`)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="dx-card overflow-hidden border-brand-200/80 bg-gradient-to-b from-brand-50/20 via-white to-white shadow-sm">
      {/* Top Banner / Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-ink-100 p-5">
        <div className="flex items-start gap-3.5">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-500 text-white shadow-sm ring-4 ring-brand-100">
            <Sparkles size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink-900">
                Supply Chain Domain Quality Tuning
              </h3>
              {comparisonData && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                  <CheckCircle2 size={11} /> Improvement Evaluated
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-ink-600">
              Compare valid quality-improvement candidates using the available evaluation metrics,
              domain checks, completeness, and privacy safeguards.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {comparisonData && (
            <button
              type="button"
              onClick={handleDownloadImproved}
              disabled={downloading}
              className="dx-btn-outline inline-flex items-center gap-1.5 text-xs font-semibold"
            >
              {downloading ? (
                <Loader2 size={13} className="animate-spin text-ink-500" />
              ) : (
                <Download size={13} />
              )}
              Download Improved
            </button>
          )}

          <button
            type="button"
            onClick={handleImproveQuality}
            disabled={improving || !resultId}
            className="dx-btn-primary inline-flex items-center gap-2 text-xs font-semibold shadow-sm"
          >
            {improving ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Tuning in Progress...
              </>
            ) : (
              <>
                <Sparkles size={14} />
                {comparisonData ? 'Re-run Improvement' : 'Improve Quality'}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {improving && (
        <div className="p-8 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-brand-50 text-brand-600 ring-8 ring-brand-50/50">
            <Loader2 size={24} className="animate-spin" />
          </div>
          <p className="text-sm font-semibold text-ink-900">
            Tuning Supply Chain Data Quality
          </p>
          <p className="mx-auto mt-1 max-w-md text-xs text-ink-500 leading-relaxed">
            Running empirical relationship validation, rank-preserving quantile marginal mapping,
            and exact-match privacy filtration on your generated records...
          </p>
        </div>
      )}

      {/* Error Message */}
      {error && !improving && (
        <div className="m-5 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50/70 p-3.5 text-xs text-rose-800">
          <AlertCircle size={16} className="shrink-0 text-rose-600 mt-0.5" />
          <div>
            <p className="font-semibold">Improvement process failed</p>
            <p className="mt-0.5 text-rose-700">{error}</p>
          </div>
        </div>
      )}

      {/* Results View */}
      {comparisonData && !improving && (
        <div className="space-y-5 p-5">
          {/* Explanation Banner */}
          {comparisonData.tradeoff_explanation && (
            <div className="flex items-start gap-2.5 rounded-lg border border-brand-200 bg-brand-50/40 p-3.5 text-xs text-brand-900">
              <Info size={15} className="shrink-0 text-brand-600 mt-0.5" />
              <div className="leading-relaxed">
                <span className="font-semibold">Quality Optimization Summary: </span>
                {comparisonData.tradeoff_explanation}
              </div>
            </div>
          )}

          {/* Side-by-Side Comparison Table */}
          <div className="overflow-hidden rounded-xl border border-ink-200 bg-white shadow-sm">
            <div className="border-b border-ink-100 bg-ink-50/50 px-4 py-2.5 text-xs font-semibold text-ink-700 flex items-center justify-between">
              <span>Metric Comparison (Baseline vs Improved)</span>
              <span className="text-[11px] font-normal text-ink-500">
                Evaluation Protocol: Identical splits, seeds & target checking
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-ink-200 bg-ink-50/30 text-[11px] font-semibold text-ink-600">
                    <th className="py-2.5 px-4">Quality Dimension</th>
                    <th className="py-2.5 px-4 text-right">Baseline</th>
                    <th className="py-2.5 px-4 text-right">Improved</th>
                    <th className="py-2.5 px-4 text-right">Change</th>
                    <th className="py-2.5 px-4 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {Array.isArray(comparisonData.metrics_comparison) &&
                    comparisonData.metrics_comparison.map((row) => {
                      const isImproved = row.status === 'improved'
                      const isRegressed = row.status === 'regressed'
                      const deltaText =
                        row.change > 0 ? `+${row.change}` : `${row.change}`

                      return (
                        <tr
                          key={row.metric}
                          className="hover:bg-ink-50/40 transition-colors"
                        >
                          <td className="py-2.5 px-4 font-medium text-ink-900">
                            {row.label}
                          </td>
                          <td className="py-2.5 px-4 text-right font-mono text-ink-600">
                            {row.baseline != null ? row.baseline : '—'}
                          </td>
                          <td className="py-2.5 px-4 text-right font-mono font-semibold text-ink-900">
                            {row.improved != null ? row.improved : '—'}
                          </td>
                          <td
                            className={`py-2.5 px-4 text-right font-mono font-medium ${
                              isImproved
                                ? 'text-emerald-700'
                                : isRegressed
                                ? 'text-rose-700'
                                : 'text-ink-500'
                            }`}
                          >
                            {deltaText}
                          </td>
                          <td className="py-2.5 px-4 text-center">
                            {isImproved && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                                <TrendingUp size={11} /> Improved
                              </span>
                            )}
                            {isRegressed && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/20">
                                <TrendingDown size={11} /> Regressed
                              </span>
                            )}
                            {!isImproved && !isRegressed && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-ink-50 px-2 py-0.5 text-[10px] font-medium text-ink-600 ring-1 ring-inset ring-ink-200">
                                <Minus size={11} /> Unchanged
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Candidate selection results */}
          {Array.isArray(comparisonData.candidate_comparison) && (
            <div className="overflow-hidden rounded-xl border border-ink-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 bg-ink-50/50 px-4 py-3">
                <div>
                  <p className="text-xs font-semibold text-ink-800">Candidate Selection</p>
                  <p className="mt-0.5 text-[11px] text-ink-500">
                    Candidates are ranked using available evaluation metrics and validity checks.
                  </p>
                </div>
                {comparisonData.selected_candidate && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                    <CheckCircle2 size={12} /> Selected: {comparisonData.selected_candidate}
                  </span>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-ink-200 bg-ink-50/30 text-[11px] font-semibold text-ink-600">
                      <th className="px-4 py-2.5">Candidate</th>
                      <th className="px-4 py-2.5 text-right">Composite score</th>
                      <th className="px-4 py-2.5 text-right">Statistical</th>
                      <th className="px-4 py-2.5 text-right">Correlation</th>
                      <th className="px-4 py-2.5 text-right">ML utility</th>
                      <th className="px-4 py-2.5 text-right">Privacy</th>
                      <th className="px-4 py-2.5 text-center">Validity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {comparisonData.candidate_comparison.map((candidate) => {
                      const metrics = candidate.metrics || {}
                      const isSelected = candidate.candidate === comparisonData.selected_candidate
                      const displayScore = (value) =>
                        value == null || !Number.isFinite(Number(value))
                          ? '—'
                          : Number(value).toFixed(2)
                      return (
                        <tr key={candidate.candidate} className={isSelected ? 'bg-emerald-50/50' : 'hover:bg-ink-50/40'}>
                          <td className="px-4 py-2.5 font-medium text-ink-900">
                            <div className="flex items-center gap-1.5">
                              {candidate.candidate || 'Unnamed candidate'}
                              {isSelected && <CheckCircle2 size={12} className="text-emerald-600" />}
                            </div>
                            {candidate.reason && <p className="mt-0.5 text-[10px] text-rose-600">{candidate.reason}</p>}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono font-semibold">{displayScore(candidate.score)}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{displayScore(metrics.statistical_similarity_score)}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{displayScore(metrics.correlation_score)}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{displayScore(metrics.ml_utility_score)}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{displayScore(metrics.privacy_score)}</td>
                          <td className="px-4 py-2.5 text-center">
                            <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${candidate.valid ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                              {candidate.valid ? 'Valid' : 'Rejected'}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {comparisonData.candidate_comparison.some((candidate) => Array.isArray(candidate.evaluation_errors) && candidate.evaluation_errors.length > 0) && (
                <div className="border-t border-ink-100 px-4 py-2.5 text-[11px] text-ink-500">
                  Some metric evaluations were unavailable for one or more candidates. Hover-independent details are available in the API response.
                </div>
              )}
            </div>
          )}

          {/* Audit Trail & Rules Summary Grid */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Strategies Applied */}
            <div className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-ink-500 mb-2.5 flex items-center gap-1.5">
                <Layers size={13} className="text-brand-600" /> Strategies Applied
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Array.isArray(comparisonData.strategies_applied) &&
                  comparisonData.strategies_applied.map((strat) => (
                    <span
                      key={strat}
                      className="inline-flex items-center gap-1 rounded-md bg-ink-50 px-2.5 py-1 text-[11px] font-medium text-ink-700 ring-1 ring-inset ring-ink-200"
                    >
                      <CheckCircle2 size={11} className="text-brand-600" />
                      {strat.replace(/_/g, ' ')}
                    </span>
                  ))}
              </div>
            </div>

            {/* Privacy Guard Status */}
            <div className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-ink-500 mb-2.5 flex items-center gap-1.5">
                <ShieldCheck size={13} className="text-emerald-600" /> Privacy Guard & Leakage
              </p>
              <div className="space-y-1.5 text-xs text-ink-700">
                <div className="flex justify-between">
                  <span className="text-ink-500">Exact duplicate rate:</span>
                  <span className="font-mono font-medium text-ink-900">
                    {comparisonData.privacy_status?.exact_match_rate != null
                      ? `${(comparisonData.privacy_status.exact_match_rate * 100).toFixed(2)}%`
                      : '0.00%'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Memorized rows dropped:</span>
                  <span className="font-mono font-medium text-ink-900">
                    {comparisonData.privacy_status?.duplicates_dropped ?? 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Privacy criteria passed:</span>
                  <span className="font-semibold text-emerald-700">
                    {comparisonData.privacy_status?.passed ? 'Passed (Low Risk)' : 'Warning'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Separate evaluation and report actions for both immutable results */}
          <section className="rounded-xl border border-brand-200 bg-brand-50/40 p-4">
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-ink-900">
                Evaluate & Report — Before and After
              </h4>
              <p className="mt-1 text-xs text-ink-600">
                The original and improved datasets keep separate result IDs, so each can have
                its own evaluation and report. The original result is not overwritten.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-ink-200 bg-white p-3">
                <p className="text-xs font-semibold text-ink-900">Original generated dataset</p>
                <p className="mt-1 text-[11px] text-ink-500">
                  Result ID: {comparisonData.baseline_result_id ?? resultId}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href={`/evaluations?result_id=${encodeURIComponent(
                      comparisonData.baseline_result_id ?? resultId,
                    )}&${returnToParam}&workflow=original`}
                    className="dx-btn-outline inline-flex items-center gap-1.5 text-xs"
                  >
                    <Layers size={13} /> Original Evaluation
                  </a>
                  <a
                    href={`/reports?result_id=${encodeURIComponent(
                      comparisonData.baseline_result_id ?? resultId,
                    )}&dataset_id=${encodeURIComponent(datasetId ?? comparisonData.dataset_id ?? '')}&${returnToParam}&workflow=original`}
                    className="dx-btn-outline inline-flex items-center gap-1.5 text-xs"
                  >
                    <Table size={13} /> Original Report
                  </a>
                </div>
              </div>

              <div className="rounded-lg border border-emerald-200 bg-white p-3">
                <p className="text-xs font-semibold text-ink-900">Improved dataset</p>
                <p className="mt-1 text-[11px] text-ink-500">
                  Result ID: {comparisonData.improved_result_id ?? 'Not returned'}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href={`/evaluations?result_id=${encodeURIComponent(comparisonData.improved_result_id ?? '')}&${returnToParam}&workflow=improved`}
                    aria-disabled={!comparisonData.improved_result_id}
                    className="dx-btn-primary inline-flex items-center gap-1.5 text-xs"
                    onClick={(event) => {
                      if (!comparisonData.improved_result_id) event.preventDefault()
                    }}
                  >
                    <Layers size={13} /> Improved Evaluation
                  </a>
                  <a
                    href={`/reports?result_id=${encodeURIComponent(
                      comparisonData.improved_result_id ?? '',
                    )}&dataset_id=${encodeURIComponent(datasetId ?? comparisonData.dataset_id ?? '')}&${returnToParam}&workflow=improved`}
                    aria-disabled={!comparisonData.improved_result_id}
                    className="dx-btn-primary inline-flex items-center gap-1.5 text-xs"
                    onClick={(event) => {
                      if (!comparisonData.improved_result_id) event.preventDefault()
                    }}
                  >
                    <Table size={13} /> Improved Report
                  </a>
                </div>
              </div>
            </div>
          </section>

          {/* Interactive Preview Switcher (Baseline vs Improved) */}
          {comparisonData.previews && (
            <div className="rounded-xl border border-ink-200 bg-white overflow-hidden shadow-sm">
              <div className="flex items-center justify-between border-b border-ink-200 bg-ink-50/60 px-4 py-2">
                <div className="flex items-center gap-1 bg-ink-200/60 p-0.5 rounded-lg text-xs">
                  <button
                    type="button"
                    onClick={() => setActivePreviewTab('improved')}
                    className={`rounded-md px-3 py-1 font-medium transition-all ${
                      activePreviewTab === 'improved'
                        ? 'bg-white text-ink-900 shadow-sm'
                        : 'text-ink-600 hover:text-ink-900'
                    }`}
                  >
                    Improved Dataset ({comparisonData.previews.improved_sample?.length || 0} sample rows)
                  </button>
                  <button
                    type="button"
                    onClick={() => setActivePreviewTab('baseline')}
                    className={`rounded-md px-3 py-1 font-medium transition-all ${
                      activePreviewTab === 'baseline'
                        ? 'bg-white text-ink-900 shadow-sm'
                        : 'text-ink-600 hover:text-ink-900'
                    }`}
                  >
                    Original Baseline ({comparisonData.previews.baseline_sample?.length || 0} sample rows)
                  </button>
                </div>
                <span className="text-[11px] text-ink-500">
                  {activePreviewTab === 'improved'
                    ? 'Transformed & verified output'
                    : 'Unmodified baseline output'}
                </span>
              </div>

              <div className="overflow-x-auto max-h-64">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-ink-200 bg-ink-50 text-[11px] font-semibold text-ink-600">
                      {comparisonData.previews.columns?.map((col) => (
                        <th key={col} className="py-2 px-3 whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100 font-mono text-[11px]">
                    {(activePreviewTab === 'improved'
                      ? comparisonData.previews.improved_sample
                      : comparisonData.previews.baseline_sample
                    )?.map((row, i) => (
                      <tr key={i} className="hover:bg-ink-50/50">
                        {comparisonData.previews.columns?.map((col) => (
                          <td
                            key={col}
                            className="py-1.5 px-3 whitespace-nowrap text-ink-800"
                          >
                            {row[col] !== undefined && row[col] !== null
                              ? String(row[col])
                              : '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
