import { useCallback, useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  FileText,
  Download,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  BarChart3,
  Sparkles,
  ArrowRight,
  Database,
  Layers,
  FileSpreadsheet,
  FileCode,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import DataTable from '../components/DataTable.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import EmptyState from '../components/EmptyState.jsx'
import ErrorState from '../components/ErrorState.jsx'
import Toast from '../components/Toast.jsx'

import { reportApi } from '../api/reportApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber } from '../utils/format.js'

function toneForScore(score) {
  if (score == null) return 'neutral'
  if (score >= 80) return 'success'
  if (score >= 50) return 'warning'
  return 'error'
}

export default function Report() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const urlResultId = searchParams.get('result_id')
  const urlDatasetId = searchParams.get('dataset_id')

  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [downloadingFormat, setDownloadingFormat] = useState(null)
  const [error, setError] = useState('')
  const [toast, setToast] = useState(null)

  const [report, setReport] = useState(null)
  const [userReports, setUserReports] = useState([])
  const [activeTab, setActiveTab] = useState('statistical')

  // Fetch report data
  const loadReport = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      if (urlResultId || urlDatasetId) {
        const res = await reportApi.get({
          result_id: urlResultId || undefined,
          dataset_id: urlDatasetId || undefined,
        })
        const reportData = res?.data?.data || res?.data
        setReport(reportData)
      } else {
        const res = await reportApi.get()
        const reportsList = res?.data?.data?.reports || []
        const latestReport = res?.data?.data?.latest_report || null
        setUserReports(reportsList)
        if (latestReport) {
          setReport(latestReport)
        } else if (reportsList.length > 0) {
          const latest = reportsList[0]
          const fullRes = await reportApi.get({ result_id: latest.result_id })
          setReport(fullRes?.data?.data || fullRes?.data)
        }
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [urlResultId, urlDatasetId])

  useEffect(() => {
    loadReport()
  }, [loadReport])

  // Trigger report generation / regeneration
  const handleGenerate = async () => {
    const resId =
      report?.metadata?.result_id ||
      urlResultId ||
      userReports[0]?.result_id
    if (!resId) {
      setToast({
        type: 'warning',
        title: 'Cannot Generate',
        message: 'No generated dataset result available to create report.',
      })
      return
    }
    setGenerating(true)
    try {
      const res = await reportApi.generate(resId, 'json')
      setReport(res?.data?.data || res?.data)
      // refresh user reports list
      const listRes = await reportApi.get()
      setUserReports(listRes?.data?.data?.reports || [])
      setToast({
        type: 'success',
        title: 'Report Generated',
        message: 'Evaluation report created successfully.',
      })
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Generation Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setGenerating(false)
    }
  }

  // Handle artifact download
  const handleDownload = async (format) => {
    const resId =
      report?.metadata?.result_id ||
      urlResultId ||
      userReports[0]?.result_id
    const dsId =
      report?.metadata?.dataset_id ||
      urlDatasetId ||
      userReports[0]?.dataset_id

    setDownloadingFormat(format)
    try {
      const fileName = await reportApi.download({
        result_id: resId || undefined,
        dataset_id: dsId || undefined,
        format,
      })
      setToast({
        type: 'success',
        title: 'Download Started',
        message: fileName,
      })
    } catch (err) {
      setToast({
        type: 'error',
        title: 'Download Failed',
        message: getErrorMessage(err),
      })
    } finally {
      setDownloadingFormat(null)
    }
  }

  const meta = report?.metadata || {}
  const summary = report?.executive_summary || {}
  const dimScores = summary.dimension_scores || {}
  const stats = report?.statistical_similarity || {}
  const textEval = report?.text_evaluation || {}
  const corr = report?.correlation_covariance || {}
  const ml = report?.ml_utility || {}
  const ref = report?.relationship_integrity || {}

  // Statistical columns table
  const statColumns = Object.entries(stats.columns || {}).map(([name, c]) => ({
    name,
    columnType: c?.column_type || 'unknown',
    status: c?.status || '—',
    reason: c?.reason || null,
    score: c?.score,
    metrics: c?.metrics || {},
  }))

  const statTableColumns = [
    {
      key: 'name',
      header: 'Column',
      render: (r) => <span className="font-semibold text-ink-900">{r.name}</span>,
    },
    {
      key: 'columnType',
      header: 'Type',
      render: (r) => (
        <span className="text-xs px-2 py-0.5 rounded bg-ink-100 text-ink-700 font-mono">
          {r.columnType}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => {
        if (r.status === 'evaluated') {
          return <span className="dx-badge dx-badge-success">Evaluated</span>
        }
        return (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="dx-badge bg-slate-100 text-slate-700 border border-slate-300">
              Excluded
            </span>
            {r.reason && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                {r.reason}
              </span>
            )}
          </div>
        )
      },
    },
    {
      key: 'score',
      header: 'Score',
      render: (r) => {
        if (r.status === 'excluded' || r.score == null) {
          return <span className="text-ink-400 font-mono">—</span>
        }
        return (
          <span
            className={`font-semibold font-mono ${
              r.score >= 80
                ? 'text-emerald-600'
                : r.score >= 50
                ? 'text-amber-600'
                : 'text-rose-600'
            }`}
          >
            {formatNumber(r.score, { decimals: 1 })}%
          </span>
        )
      },
    },
  ]

  // Text evaluation columns table
  const textColumns = Object.entries(textEval.columns || {}).map(([name, tc]) => ({
    name,
    score: tc?.score,
    metrics: tc?.metrics || {},
  }))

  const textTableColumns = [
    {
      key: 'name',
      header: 'Text Column',
      render: (r) => <span className="font-semibold text-ink-900">{r.name}</span>,
    },
    {
      key: 'score',
      header: 'Text Score',
      render: (r) => (
        <span className="font-semibold font-mono text-primary-600">
          {r.score != null ? `${formatNumber(r.score, { decimals: 1 })}%` : '—'}
        </span>
      ),
    },
    {
      key: 'uniqueness',
      header: 'Uniqueness',
      render: (r) => {
        const dupe = r.metrics?.near_duplicate_rate ?? 0
        const uniq = Math.max(0, 1 - dupe) * 100
        return <span className="font-mono text-ink-700">{uniq.toFixed(1)}% unique</span>
      },
    },
    {
      key: 'originality',
      header: 'Originality (Non-verbatim)',
      render: (r) => {
        const orig = (r.metrics?.originality_rate ?? 1.0) * 100
        return <span className="font-mono text-emerald-600">{orig.toFixed(1)}% original</span>
      },
    },
    {
      key: 'length',
      header: 'Length Similarity',
      render: (r) => {
        const lSim = r.metrics?.length_similarity?.char_length_similarity
        return (
          <span className="font-mono text-ink-700">
            {lSim != null ? `${(lSim * 100).toFixed(1)}%` : '—'}
          </span>
        )
      },
    },
    {
      key: 'semantic',
      header: 'Semantic Consistency',
      render: (r) => {
        const sem = r.metrics?.semantic_consistency?.consistency_rate
        if (sem == null) return <span className="text-ink-400">N/A</span>
        return (
          <span className="font-mono text-emerald-700 font-medium">
            {(sem * 100).toFixed(1)}% match
          </span>
        )
      },
    },
  ]

  return (
    <>
      <Toast
        open={!!toast}
        type={toast?.type || 'success'}
        title={toast?.title}
        message={toast?.message}
        onClose={() => setToast(null)}
      />

      <PageHeader
        title="Evaluation Report"
        subtitle="Comprehensive assessment of statistical similarity, correlations, ML utility, referential integrity, and text quality."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              className="dx-btn-outline"
              onClick={handleGenerate}
              disabled={generating || loading}
            >
              {generating ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              {generating ? 'Regenerating…' : 'Regenerate'}
            </button>

            <button
              type="button"
              className="dx-btn-outline text-ink-800"
              onClick={() => handleDownload('html')}
              disabled={downloadingFormat === 'html' || !report}
              title="Download standalone HTML report"
            >
              {downloadingFormat === 'html' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FileCode size={14} />
              )}
              HTML
            </button>

            <button
              type="button"
              className="dx-btn-outline text-ink-800"
              onClick={() => handleDownload('csv')}
              disabled={downloadingFormat === 'csv' || !report}
              title="Download CSV summary"
            >
              {downloadingFormat === 'csv' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FileSpreadsheet size={14} />
              )}
              CSV
            </button>

            <button
              type="button"
              className="dx-btn-primary"
              onClick={() => handleDownload('json')}
              disabled={downloadingFormat === 'json' || !report}
              title="Download full JSON report"
            >
              {downloadingFormat === 'json' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              Download JSON
            </button>
          </div>
        }
      />

      {userReports.length > 0 && (
        <div className="mb-5 flex items-center justify-between bg-ink-50 px-4 py-2.5 rounded-lg border border-ink-200">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-ink-700">Available Reports:</span>
            <select
              value={report?.metadata?.result_id || ''}
              onChange={async (e) => {
                const targetId = Number(e.target.value)
                if (targetId) {
                  setLoading(true)
                  try {
                    const fullRes = await reportApi.get({ result_id: targetId })
                    setReport(fullRes?.data?.data || fullRes?.data)
                  } finally {
                    setLoading(false)
                  }
                }
              }}
              className="text-xs font-medium bg-white border border-ink-300 rounded-md px-3 py-1.5 text-ink-900 shadow-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              {userReports.map((r) => (
                <option key={r.result_id} value={r.result_id}>
                  {r.dataset_name} — Run #{r.run_id} ({r.overall_score != null ? `Score: ${r.overall_score}%` : 'Evaluated'})
                </option>
              ))}
            </select>
          </div>
          <span className="text-xs text-ink-500">
            {userReports.length} report{userReports.length > 1 ? 's' : ''} available
          </span>
        </div>
      )}

      {loading && !report ? (
        <div className="flex items-center justify-center p-12">
          <Loader2 size={32} className="animate-spin text-primary-500" />
        </div>
      ) : error ? (
        <ErrorState title="Failed to load report" description={error} onRetry={loadReport} />
      ) : !report ? (
        <EmptyState
          icon={FileText}
          title="No Report Generated Yet"
          description="Click below to automatically generate an evaluation report for your generated dataset."
          action={
            <button
              type="button"
              className="dx-btn-primary"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              Generate Report Now
            </button>
          }
        />
      ) : (
        <div className="space-y-6">
          {/* Executive Summary Card */}
          <div className="dx-card p-6 bg-gradient-to-r from-ink-900 to-ink-800 text-white shadow-lg">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold tracking-tight">Executive Summary</h2>
                  <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-primary-500/20 text-primary-300 border border-primary-500/30">
                    Grade: {summary.rating || 'N/A'}
                  </span>
                </div>
                <p className="text-ink-200 text-sm max-w-2xl leading-relaxed">
                  {summary.summary_text || 'Evaluation complete across all dimensions.'}
                </p>
                <div className="flex items-center gap-4 text-xs text-ink-300 pt-2 flex-wrap">
                  <span>Dataset: <strong className="text-white">{meta.dataset_name}</strong></span>
                  <span>•</span>
                  <span>Model: <strong className="text-white">{meta.model_name}</strong></span>
                  <span>•</span>
                  <span>Run ID: <strong className="text-white">#{meta.run_id}</strong></span>
                  <span>•</span>
                  <span>Rows: <strong className="text-white">{meta.row_count}</strong></span>
                  <span>•</span>
                  <span>Date: <strong className="text-white">{meta.generated_at}</strong></span>
                </div>
              </div>

              <div className="flex flex-col items-center justify-center bg-white/10 rounded-xl p-5 border border-white/10 min-w-[140px]">
                <span className="text-4xl font-extrabold text-primary-400">
                  {summary.overall_quality_score != null
                    ? `${formatNumber(summary.overall_quality_score, { decimals: 1 })}%`
                    : '—'}
                </span>
                <span className="text-[11px] font-semibold tracking-wider uppercase text-ink-300 mt-1">
                  Overall Score
                </span>
              </div>
            </div>
          </div>

          {/* 5-Dimension Overview Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard
              title="Statistical Similarity"
              value={
                dimScores.statistical_similarity != null
                  ? `${formatNumber(dimScores.statistical_similarity, { decimals: 1 })}%`
                  : '—'
              }
              tone={toneForScore(dimScores.statistical_similarity)}
              subtitle={`${stats.evaluated_columns ?? 0}/${stats.total_common_columns ?? 0} columns`}
            />
            <StatCard
              title="Free-Form Text Quality"
              value={
                dimScores.text_evaluation != null
                  ? `${formatNumber(dimScores.text_evaluation, { decimals: 1 })}%`
                  : '—'
              }
              tone={toneForScore(dimScores.text_evaluation)}
              subtitle={
                textEval.evaluated_text_columns?.length
                  ? `${textEval.evaluated_text_columns.length} text col(s)`
                  : 'Conditioned & diverse'
              }
            />
            <StatCard
              title="Correlation & Covariance"
              value={
                dimScores.correlation_covariance != null
                  ? `${formatNumber(dimScores.correlation_covariance, { decimals: 1 })}%`
                  : '—'
              }
              tone={toneForScore(dimScores.correlation_covariance)}
              subtitle={corr.status || 'not_applicable'}
            />
            <StatCard
              title="ML Utility"
              value={
                dimScores.ml_utility != null
                  ? `${formatNumber(dimScores.ml_utility, { decimals: 1 })}%`
                  : '—'
              }
              tone={toneForScore(dimScores.ml_utility)}
              subtitle={ml.task_type || 'not_applicable'}
            />
            <StatCard
              title="Referential Integrity"
              value={
                dimScores.relationship_integrity != null
                  ? `${formatNumber(dimScores.relationship_integrity, { decimals: 1 })}%`
                  : '—'
              }
              tone={toneForScore(dimScores.relationship_integrity)}
              subtitle={ref.status || 'not_applicable'}
            />
          </div>

          {/* Section Navigation Tabs */}
          <div className="border-b border-ink-200">
            <nav className="flex space-x-6">
              {[
                { id: 'statistical', label: 'Statistical Similarity (US-023)' },
                { id: 'text', label: 'Text Quality & Conditioning' },
                { id: 'correlation', label: 'Correlation & Covariance (US-024)' },
                { id: 'ml', label: 'ML Utility (US-025)' },
                { id: 'referential', label: 'Referential Integrity (US-027)' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-primary-600 text-primary-600 font-semibold'
                      : 'border-transparent text-ink-500 hover:text-ink-700 hover:border-ink-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* TAB 1: Statistical Similarity */}
          {activeTab === 'statistical' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold text-ink-900">
                    Column-Level Marginal Distributions
                  </h3>
                  <p className="text-xs text-ink-500">
                    Evaluated: <strong>{stats.evaluated_columns ?? 0}</strong> • Excluded: <strong>{stats.excluded_columns ?? 0}</strong> (Excluded columns do NOT penalize overall score)
                  </p>
                </div>
              </div>
              <DataTable
                columns={statTableColumns}
                data={statColumns}
                emptyTitle="No columns evaluated"
                emptyDescription="No column statistical metrics available."
              />
            </div>
          )}

          {/* TAB 2: Text Quality & Conditioning */}
          {activeTab === 'text' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-semibold text-ink-900">
                  Free-Form Text Originality & Semantic Conditioning
                </h3>
                <p className="text-xs text-ink-500">
                  Measures whether synthetic free-form text avoids verbatim copying, maintains diversity, and aligns semantically with structured row labels (e.g. Sentiment).
                </p>
              </div>
              {textColumns.length > 0 ? (
                <DataTable
                  columns={textTableColumns}
                  data={textColumns}
                  emptyTitle="No text columns"
                  emptyDescription="No free-form text columns evaluated in this dataset."
                />
              ) : (
                <div className="dx-card p-6 text-center text-ink-500">
                  No free-form string columns found in this dataset.
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Correlation & Covariance */}
          {activeTab === 'correlation' && (
            <div className="dx-card p-6 space-y-4">
              <h3 className="text-base font-semibold text-ink-900">
                Correlation and Covariance Matrix Preservation
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="bg-ink-50 p-4 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">Status</span>
                  <div className="text-lg font-bold text-ink-900 mt-1">{corr.status || 'not_applicable'}</div>
                </div>
                <div className="bg-ink-50 p-4 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">Similarity Score</span>
                  <div className="text-lg font-bold text-primary-600 mt-1">
                    {corr.overall_score != null ? `${formatNumber(corr.overall_score, { decimals: 1 })}%` : '—'}
                  </div>
                </div>
                <div className="bg-ink-50 p-4 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">Numerical Columns</span>
                  <div className="text-sm font-medium text-ink-800 mt-1">
                    {corr.numerical_columns?.length ? corr.numerical_columns.join(', ') : 'None (<2 numerical cols)'}
                  </div>
                </div>
              </div>
              {corr.reason && (
                <p className="text-xs text-amber-700 bg-amber-50 p-3 rounded border border-amber-200">
                  {corr.reason}
                </p>
              )}
            </div>
          )}

          {/* TAB 4: ML Utility */}
          {activeTab === 'ml' && (
            <div className="dx-card p-6 space-y-4">
              <h3 className="text-base font-semibold text-ink-900">
                Synthetic-Train / Real-Test Predictive Performance
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
                <div className="bg-ink-50 p-3 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">Status</span>
                  <div className="text-base font-bold text-ink-900 mt-1">{ml.status || 'not_applicable'}</div>
                </div>
                <div className="bg-ink-50 p-3 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">Task</span>
                  <div className="text-base font-bold text-ink-900 mt-1">{ml.task_type || 'N/A'}</div>
                </div>
                <div className="bg-ink-50 p-3 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">Target</span>
                  <div className="text-base font-bold text-ink-900 mt-1">{ml.target_column || 'N/A'}</div>
                </div>
                <div className="bg-ink-50 p-3 rounded-lg">
                  <span className="text-xs text-ink-500 uppercase font-semibold">ML Score</span>
                  <div className="text-base font-bold text-emerald-600 mt-1">
                    {ml.overall_score != null ? `${formatNumber(ml.overall_score, { decimals: 1 })}%` : '—'}
                  </div>
                </div>
              </div>
              {ml.reason && (
                <p className="text-xs text-amber-700 bg-amber-50 p-3 rounded border border-amber-200">
                  {ml.reason}
                </p>
              )}
            </div>
          )}

          {/* TAB 5: Referential Integrity */}
          {activeTab === 'referential' && (
            <div className="dx-card p-6 space-y-4">
              <h3 className="text-base font-semibold text-ink-900">
                Cross-Table Referential Integrity
              </h3>
              <p className="text-sm text-ink-600">
                {ref.message || 'Validates parent-child foreign key matching across multi-table datasets.'}
              </p>
              <div className="bg-ink-50 p-4 rounded-lg inline-block">
                <span className="text-xs text-ink-500 uppercase font-semibold">Integrity Status</span>
                <div className="text-base font-bold text-ink-900 mt-1">{ref.status || 'not_applicable'}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}