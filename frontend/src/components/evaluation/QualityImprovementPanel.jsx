import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
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
  X,
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
  const navigate = useNavigate()
  const returnTo = `${location.pathname}${location.search}`
  const returnToParam = `return_to=${encodeURIComponent(returnTo)}`
  const [improving, setImproving] = useState(false)
  const [error, setError] = useState('')
  const [comparisonData, setComparisonData] = useState(null)
  const [activePreviewTab, setActivePreviewTab] = useState('improved')
  const [downloading, setDownloading] = useState(false)
  const [activeMetric, setActiveMetric] = useState(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  // Keep the original/baseline result available for re-runs after the first improvement.
  const sourceResultId = resultId ?? comparisonData?.baseline_result_id ?? comparisonData?.original_result_id

  const handleImproveQuality = async () => {
    if (!sourceResultId || improving) return
    setError('')
    setImproving(true)

    try {
      const res = await generationApi.improveQuality({
        resultId: sourceResultId,
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
          <button
            type="button"
            onClick={handleImproveQuality}
            disabled={!sourceResultId || improving}
            className="dx-btn-primary inline-flex items-center gap-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-50"
          >
            {improving ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Sparkles size={13} />
            )}
            {improving ? "Improving..." : "Improve Quality"}
          </button>
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
          {/* Improved evaluation dimensions are shown separately; Advanced remains unchanged. */}
          <section className="rounded-xl border border-emerald-200 bg-white p-4 shadow-sm">
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-ink-900">Improved Evaluation Dimensions</h4>
              <p className="mt-1 text-xs text-ink-500">Key evaluation scores for the improved synthetic dataset.</p>
            </div>
            {(() => {
              const rows = Array.isArray(comparisonData.metrics_comparison) ? comparisonData.metrics_comparison : []
              const lookup = Object.fromEntries(rows.map((row) => [String(row.metric || '').toLowerCase(), row]))
              const dimensions = [
                {
                  label: 'Statistical Similarity',
                  keys: ['statistical_similarity'],
                  description: 'Measures how closely synthetic column distributions resemble the real dataset.',
                },
                {
                  label: 'Correlation & Covariance',
                  keys: ['correlation_score', 'correlation_and_covariance', 'correlation_covariance'],
                  description: 'Measures how well relationships between columns are preserved in the synthetic dataset.',
                },
                {
                  label: 'ML Utility',
                  keys: ['ml_utility', 'ml_utility_score'],
                  description: 'Measures how useful the synthetic dataset is for training models evaluated on real data.',
                },
                {
                  label: 'Relationship Integrity',
                  keys: ['business_rule_validity', 'relationship_integrity'],
                  description: 'Measures whether records satisfy the evaluated business and relationship rules.',
                },
              ]
              const findRow = (keys) => keys.map((key) => lookup[key]).find(Boolean)
              const formatScore = (value) => {
                if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return 'Not evaluated'
                return Number(value).toFixed(2)
              }
              return (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {dimensions.map((dimension, index) => {
                    const row = findRow(dimension.keys)
                    const value = row?.improved
                    const originalValue = row?.baseline
                    const scoreAvailable = value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
                    const originalAvailable = originalValue !== null && originalValue !== undefined && originalValue !== '' && Number.isFinite(Number(originalValue))
                    const iconTone = ['bg-violet-50 text-violet-600', 'bg-blue-50 text-blue-600', 'bg-amber-50 text-amber-700', 'bg-emerald-50 text-emerald-700'][index]
                    return (
                      <div
                        key={dimension.label}
                        className="group relative overflow-hidden rounded-xl border border-ink-200 bg-white p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-md"
                      >
                        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand-400/80 via-brand-500/60 to-emerald-400/70" />
                        <div className="flex items-start justify-between gap-3 pt-1">
                          <div className="flex min-w-0 items-center gap-2.5">
                            <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${iconTone}`}>
                              {index === 0 ? <TrendingUp size={17} /> : index === 1 ? <ShieldCheck size={17} /> : index === 2 ? <Sparkles size={17} /> : <Layers size={17} />}
                            </span>
                            <span className="text-xs font-semibold leading-snug text-ink-700">{dimension.label}</span>
                          </div>
                          <span className="shrink-0 rounded-full bg-ink-50 px-2 py-1 text-[9px] font-semibold uppercase tracking-wide text-ink-500 ring-1 ring-inset ring-ink-100">Improved</span>
                        </div>
                        <div className="mt-4 flex items-end justify-between gap-2">
                          <div className={`text-2xl font-bold tracking-tight tabular-nums ${scoreAvailable ? 'text-ink-950' : 'text-ink-400'}`}>{formatScore(value)}</div>
                          <span className="pb-1 text-[10px] font-medium uppercase tracking-wider text-ink-400">Improved</span>
                        </div>
                        <div className="mt-1 text-[11px] font-medium tabular-nums text-ink-500">Original: {formatScore(originalAvailable ? originalValue : null)}</div>
                        <div className="mt-3 border-t border-ink-100 pt-2.5 text-[11px] leading-relaxed text-ink-500">{dimension.description}</div>
                      </div>
                    )
                  })}
                </div>
              )
            })()}
          </section>

          {/* Advanced metrics show real before/after values as well as explanations. */}
          <section className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm">
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-ink-900">Advanced Metrics &amp; Diagnostics</h4>
              <p className="mt-1 text-xs text-ink-500">Actual baseline and improved scores. Select an info icon for the metric definition.</p>
            </div>
            {(() => {
              const rows = Array.isArray(comparisonData.metrics_comparison) ? comparisonData.metrics_comparison : []
              const lookup = Object.fromEntries(rows.map((row) => [row.metric, row]))
              const privacy = comparisonData.privacy_status || {}
              const cards = [
                { label: 'Statistical Similarity', keys: ['statistical_similarity'], suffix: '', description: 'Measures how closely synthetic column distributions resemble the real dataset. Higher scores generally indicate closer marginal distributions.' },
                { label: 'Correlation Error', keys: ['correlation_error'], suffix: '', description: 'Measures the difference between real and synthetic feature-correlation relationships. Lower error is better.' },
                { label: 'ML Utility', keys: ['ml_utility_score'], suffix: '', description: 'Measures whether a model trained using synthetic data performs well on held-out real data.' },
                { label: 'Business-rule Validity', keys: ['business_rule_validity'], suffix: '%', description: 'The percentage of evaluated records that satisfy the inferred or configured domain rules.' },
                { label: 'Completeness Score', keys: ['completeness_score'], suffix: '%', description: 'The percentage of cells containing values rather than missing data.' },
                { label: 'Exact-match Rate', keys: ['exact_match_rate'], suffix: '%', scale: 100, description: 'The percentage of synthetic rows that exactly match rows in the real reference data. Lower is generally safer.' },
                { label: 'DCR Privacy Ratio', keys: ['dcr_ratio'], suffix: '×', privacyKey: 'dcr_privacy_ratio', description: 'Compares synthetic-to-real nearest-record distance with real-to-real nearest-neighbour distance. This is a diagnostic, not a privacy guarantee.' },
                { label: 'Duplicate Row Rate', keys: ['duplicate_row_rate'], suffix: '%', privacyKey: 'duplicate_row_rate', description: 'The percentage of rows repeated within the synthetic dataset. Lower rates usually indicate more row diversity.' },
              ]
              const format = (value, card) => {
                if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'Unavailable'
                const scaled = Number(value) * (card.scale || 1)
                return `${scaled.toFixed(2)}${card.suffix}`
              }
              return <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {cards.map((card) => {
                  const row = card.keys.map((key) => lookup[key]).find(Boolean)
                  let baseline = row?.baseline
                  let improved = row?.improved
                  if (card.privacyKey && privacy[card.privacyKey] != null) improved = privacy[card.privacyKey]
                  const isRatioPercent = card.label === 'Exact-match Rate'
                  const displayCard = { ...card, scale: isRatioPercent ? 100 : 1 }
                  return <div key={card.label} className="rounded-lg border border-ink-100 bg-ink-50/40 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-medium text-ink-800">{card.label}</span>
                      <button type="button" aria-label={`Explain ${card.label}`} title={`Explain ${card.label}`} onClick={() => setActiveMetric({ label: card.label, description: card.description })} className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-brand-600 hover:bg-brand-50 focus:outline-none focus:ring-2 focus:ring-brand-300"><Info size={15} /></button>
                    </div>
                    <div className="mt-2 text-lg font-semibold tabular-nums text-ink-900">{format(improved, displayCard)}</div>
                    <div className="mt-1 text-[11px] text-ink-500">Baseline: {format(baseline, displayCard)}</div>
                  </div>
                })}
              </div>
            })()}
          </section>

          {activeMetric && (
            <div className="fixed inset-0 z-[100] flex items-center justify-center bg-ink-950/50 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setActiveMetric(null) }}>
              <div role="dialog" aria-modal="true" aria-labelledby="metric-explanation-title" className="w-full max-w-lg rounded-2xl border border-ink-200 bg-white p-5 shadow-2xl">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 id="metric-explanation-title" className="text-base font-semibold text-ink-900">{activeMetric.label}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-ink-600">{activeMetric.description}</p>
                  </div>
                  <button type="button" aria-label="Close metric explanation" onClick={() => setActiveMetric(null)} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-500 hover:bg-ink-100"><X size={17} /></button>
                </div>
                <div className="mt-5 flex justify-end"><button type="button" className="dx-btn-primary" onClick={() => setActiveMetric(null)}>Close</button></div>
              </div>
            </div>
          )}


          {/* Advanced diagnostics are collapsed by default to keep the main page clean. */}
          <section className="rounded-xl border border-ink-200 bg-white shadow-sm">
            <button
              type="button"
              aria-expanded={showAdvanced}
              aria-controls="quality-advanced-details"
              onClick={() => setShowAdvanced((open) => !open)}
              className="flex w-full items-center justify-between gap-3 rounded-xl px-4 py-4 text-left hover:bg-ink-50/70 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-300"
            >
              <span>
                <span className="block text-sm font-semibold text-ink-900">Advanced</span>
                <span className="mt-1 block text-xs text-ink-500">Metrics, metric explanations, applied strategies and privacy diagnostics</span>
              </span>
              <ChevronRight size={18} className={`shrink-0 text-ink-500 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
            </button>
            {showAdvanced && (
              <div id="quality-advanced-details" className="space-y-4 border-t border-ink-200 p-4">
          {/* Metric comparison belongs inside Advanced. */}
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
                      const metricDescriptions = {
                        statistical_similarity: 'Measures how closely synthetic column distributions resemble the real dataset. Higher scores generally indicate closer marginal distributions.',
                        correlation_score: 'Measures how well relationships between columns are preserved. Higher scores generally indicate closer correlation structure.',
                        correlation_error: 'Measures the difference between real and synthetic feature-correlation relationships. Lower error is better.',
                        ml_utility: 'Measures whether a model trained using synthetic data performs well on held-out real data.',
                        ml_utility_score: 'Measures whether a model trained using synthetic data performs well on held-out real data.',
                        business_rule_validity: 'Percentage of evaluated records that satisfy inferred or configured domain rules.',
                        exact_match_rate: 'Percentage of synthetic rows that exactly match rows in the real reference data. Lower is generally safer.',
                        dcr_ratio: 'Compares synthetic-to-real nearest-record distance with real-to-real nearest-neighbour distance. This is a diagnostic, not a privacy guarantee.',
                        dcr_privacy_ratio: 'Compares synthetic-to-real nearest-record distance with real-to-real nearest-neighbour distance. This is a diagnostic, not a privacy guarantee.',
                        completeness_score: 'Percentage of cells containing values rather than missing data.',
                        duplicate_row_rate: 'Percentage of rows repeated within the synthetic dataset. Lower rates usually indicate more row diversity.',
                      }
                      const description = metricDescriptions[row.metric] || `Shows the baseline and improved values for ${row.label || row.metric}. The status indicates whether this metric improved, regressed, or remained unchanged.`

                      return (
                        <tr
                          key={row.metric}
                          className="hover:bg-ink-50/40 transition-colors"
                        >
                          <td className="py-2.5 px-4 font-medium text-ink-900">
                            <span className="inline-flex items-center gap-1.5">
                              <span>{row.label}</span>
                              <button
                                type="button"
                                aria-label={`Explain ${row.label || row.metric}`}
                                title={`Explain ${row.label || row.metric}`}
                                onClick={() => setActiveMetric({ label: row.label || row.metric, description })}
                                className="inline-grid h-6 w-6 shrink-0 place-items-center rounded-full text-brand-600 hover:bg-brand-50 focus:outline-none focus:ring-2 focus:ring-brand-300"
                              >
                                <Info size={13} />
                              </button>
                            </span>
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

          {/* Use the same evaluated metrics in the diagnostics cards and privacy summary. */}
          {(() => {
            const metricRows = Array.isArray(comparisonData.metrics_comparison)
              ? comparisonData.metrics_comparison
              : []
            const metricLookup = Object.fromEntries(metricRows.map((row) => [row.metric, row]))
            const privacy = comparisonData.privacy_status || {}
            const metricValue = (key) => metricLookup[key]?.improved
            const exactMatchRate = privacy.exact_match_rate ?? metricValue('exact_match_rate')
            const duplicateRowRate = privacy.duplicate_row_rate ?? metricValue('duplicate_row_rate')
            const dcrRatio = privacy.dcr_privacy_ratio ?? metricValue('dcr_ratio')
            const percent = (value, fraction = false) => {
              if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'Not available'
              return `${(Number(value) * (fraction ? 100 : 1)).toFixed(2)}%`
            }
            const ratio = (value) => {
              if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'Not available'
              return `${Number(value).toFixed(2)}×`
            }
            return (
          /* Audit Trail & Rules Summary Grid */
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
                    {percent(exactMatchRate, true)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Memorized rows dropped:</span>
                  <span className="font-mono font-medium text-ink-900">
                    {comparisonData.privacy_status?.duplicates_dropped ?? 'Not returned'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Duplicate row rate:</span>
                  <span className="font-mono font-medium text-ink-900">
                    {percent(duplicateRowRate)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">DCR privacy ratio:</span>
                  <span className="font-mono font-medium text-ink-900">
                    {ratio(dcrRatio)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Privacy criteria passed:</span>
                  <span className="font-semibold text-emerald-700">
                    {comparisonData.privacy_status?.privacy_status === 'error' ? 'Could not evaluate' : comparisonData.privacy_status?.privacy_status === 'not_applicable' ? 'Insufficient comparable data' : comparisonData.privacy_status?.passed == null ? 'Not evaluated' : comparisonData.privacy_status.passed ? 'Passed (Low Risk)' : 'Review recommended'}
                  </span>
                </div>
              </div>
            </div>
          </div>
            )
          })()}
              </div>
            )}
          </section>

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
                  <button
                    type="button"
                    onClick={() => navigate(`/datasets/${encodeURIComponent(datasetId ?? comparisonData.dataset_id ?? '')}/evaluate?result_id=${encodeURIComponent(comparisonData.baseline_result_id ?? resultId)}`)}
                    className="dx-btn-outline inline-flex items-center gap-1.5 text-xs"
                    title="Return to the page you came from"
                  >
                    <Layers size={13} /> Original Evaluation
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/reports?result_id=${encodeURIComponent(comparisonData.baseline_result_id ?? resultId)}&dataset_id=${encodeURIComponent(datasetId ?? comparisonData.dataset_id ?? '')}&${returnToParam}&workflow=original`)}
                    className="dx-btn-outline inline-flex items-center gap-1.5 text-xs"
                  >
                    <Table size={13} /> Original Report
                  </button>
                </div>
              </div>

              <div className="rounded-lg border border-emerald-200 bg-white p-3">
                <p className="text-xs font-semibold text-ink-900">Improved dataset</p>
                <p className="mt-1 text-[11px] text-ink-500">
                  Result ID: {comparisonData.improved_result_id ?? 'Not returned'}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => comparisonData.improved_result_id && navigate(`/datasets/${encodeURIComponent(datasetId ?? comparisonData.dataset_id ?? '')}/evaluate?result_id=${encodeURIComponent(comparisonData.improved_result_id)}&${returnToParam}&workflow=improved`)}
                    disabled={!comparisonData.improved_result_id}
                    className="dx-btn-primary inline-flex items-center gap-1.5 text-xs disabled:opacity-50"
                  >
                    <Layers size={13} /> Improved Evaluation
                  </button>
                  <button
                    type="button"
                    onClick={() => comparisonData.improved_result_id && navigate(`/reports?result_id=${encodeURIComponent(comparisonData.improved_result_id)}&dataset_id=${encodeURIComponent(datasetId ?? comparisonData.dataset_id ?? '')}&${returnToParam}&workflow=improved`)}
                    disabled={!comparisonData.improved_result_id}
                    className="dx-btn-primary inline-flex items-center gap-1.5 text-xs disabled:opacity-50"
                  >
                    <Table size={13} /> Improved Report
                  </button>
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
