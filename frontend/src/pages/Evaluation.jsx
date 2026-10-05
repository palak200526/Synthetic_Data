import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Loader2,
  ShieldCheck,
  PlayCircle,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Info,
  BarChart3,
  ListChecks,
  FileText,
  Brain,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import ErrorState from '../components/ErrorState.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Toast from '../components/Toast.jsx'

import { datasetApi, normalizeDatasetProfile } from '../api/datasetApi.js'
import { evaluationApi, extractCategorySections } from '../api/evaluationApi.js'
import { getErrorMessage } from '../utils/errors.js'
import { formatNumber } from '../utils/format.js'
import { loadBatch, getLastSessionId } from '../utils/batchStore.js'

import {
  CATEGORY_ORDER,
  CategoryScoreCard,
  NotReturnedCard,
  StatisticalPanel,
  CorrelationPanel,
  MLUtilityPanel,
  RelationshipPanel,
  colorForScore,
  toneForScore,
} from '../components/evaluation/index.js'

// ── helpers ─────────────────────────────────────────────────────

function deriveOverallScore(categories, evaluation) {
  if (evaluation?.overallScore != null) return evaluation.overallScore
  const scores = CATEGORY_ORDER
    .map((k) => categories[k]?.score)
    .filter((s) => typeof s === 'number')
  if (scores.length === 0) return null
  return scores.reduce((a, b) => a + b, 0) / scores.length
}

// ── main ────────────────────────────────────────────────────────

export default function Evaluation() {
  const { datasetId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session') || getLastSessionId()
  const resultId = searchParams.get('result_id')

  // Batch context
  const [batch, setBatch] = useState(() => loadBatch(sessionId))
  useEffect(() => {
    setBatch(loadBatch(sessionId))
  }, [sessionId])

  const batchEntry = useMemo(() => {
    if (!Array.isArray(batch)) return null
    return batch.find((b) => String(b?.id) === String(datasetId)) || null
  }, [batch, datasetId])

  // Context
  const [profile, setProfile] = useState(null)
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [loadError, setLoadError] = useState('')

  // Evaluation
  const [evaluation, setEvaluation] = useState(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState('')
  const [toast, setToast] = useState(null)
  const [activeCategory, setActiveCategory] = useState('statistical_similarity')

  const autoRanRef = useRef(false)

  const loadProfile = useCallback(async () => {
    setLoadingProfile(true)
    setLoadError('')
    try {
      const res = await datasetApi.profile(datasetId)
      const norm = normalizeDatasetProfile(res.data) || {}
      if (batchEntry) {
        if (!norm.name) norm.name = batchEntry.fileName
        if (norm.rows == null) norm.rows = batchEntry.rows
        if (norm.columnsCount == null) norm.columnsCount = batchEntry.columns
      }
      setProfile(norm)
    } catch (err) {
      setLoadError(getErrorMessage(err))
    } finally {
      setLoadingProfile(false)
    }
  }, [datasetId, batchEntry])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  const runEvaluation = useCallback(async () => {
    if (!resultId) {
      setRunError('No result_id in the URL.')
      return
    }
    setRunError('')
    setEvaluation(null)
    setRunning(true)
    try {
      const res = await evaluationApi.run(resultId)
      setEvaluation(res.data)
      setToast({
        type: 'success',
        title: 'Evaluation complete',
        message: res.data?.message || 'Evaluation finished successfully.',
      })
    } catch (err) {
      setRunError(getErrorMessage(err))
    } finally {
      setRunning(false)
    }
  }, [resultId])

  useEffect(() => {
    if (autoRanRef.current) return
    if (!resultId) return
    autoRanRef.current = true
    runEvaluation()
  }, [resultId, runEvaluation])

  const goto = (path) => {
    const qs = sessionId ? `?session=${sessionId}` : ''
    navigate(`${path}${qs}`)
  }

  // Extract category sections from the raw evaluation payload
  const categories = useMemo(
    () => extractCategorySections(evaluation?.raw || evaluation || {}),
    [evaluation],
  )

  const overallScore = useMemo(
    () => deriveOverallScore(categories, evaluation),
    [categories, evaluation],
  )

  const activeSection = categories[activeCategory]
  const anyCategory = CATEGORY_ORDER.some((k) => categories[k])

  const renderCategoryPanel = () => {
    if (!activeSection) return <NotReturnedCard categoryKey={activeCategory} />
    if (activeCategory === 'statistical_similarity') {
      return <StatisticalPanel section={activeSection} />
    }
    if (activeCategory === 'data_quality') {
      return <CorrelationPanel section={activeSection} />
    }
    if (activeCategory === 'ml_utility') {
      return <MLUtilityPanel section={activeSection} />
    }
    if (activeCategory === 'relationship_integrity') {
      return <RelationshipPanel section={activeSection} />
    }
    return <NotReturnedCard categoryKey={activeCategory} />
  }

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
        title="Evaluation"
        subtitle="Detailed per-dimension assessment of the synthetic data against the source dataset."
        breadcrumb={
          <button
            onClick={() => goto(`/datasets/${datasetId}/generate`)}
            className="inline-flex items-center gap-1 hover:text-ink-700"
          >
            <ArrowLeft size={12} /> Generation
          </button>
        }
        actions={
          <>
            <button
              type="button"
              className="dx-btn-outline"
              onClick={runEvaluation}
              disabled={running || !resultId}
              title={!resultId ? 'No result_id in the URL' : 'Re-run evaluation'}
            >
              {running ? (
                <Loader2 size={14} className="animate-spin" />
              ) : evaluation ? (
                <RefreshCw size={14} />
              ) : (
                <PlayCircle size={14} />
              )}
              {running ? 'Evaluating…' : evaluation ? 'Re-evaluate' : 'Run evaluation'}
            </button>

            {resultId && (
              <button
                type="button"
                className="dx-btn-primary"
                onClick={() =>
                  navigate(`/reports?result_id=${resultId}&dataset_id=${datasetId}`)
                }
              >
                <FileText size={14} /> View Report
              </button>
            )}

            <button
              type="button"
              className="dx-btn-outline"
              onClick={() => navigate('/evaluations')}
            >
              Dashboard <ArrowRight size={12} />
            </button>
          </>
        }
      />

      {/* Context strip */}
      {resultId ? (
        <div className="mb-5 rounded-lg border border-ink-200 bg-ink-50/60 px-4 py-3 text-xs text-ink-600">
          Evaluating <span className="font-medium text-ink-800">result #{resultId}</span>
          {profile?.name && (
            <>
              {' '}for dataset{' '}
              <span className="font-medium text-ink-800">{profile.name}</span>
            </>
          )}
        </div>
      ) : (
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-700" />
            <div>
              <p className="text-sm font-semibold text-amber-900">
                No generation result selected
              </p>
              <p className="mt-0.5 text-xs text-amber-800">
                Run a generation first, then click <strong>Continue to evaluation</strong>.
                That will pass the resulting <code className="font-mono">result_id</code> to
                this page.
              </p>
              <button
                className="dx-btn-outline mt-3 text-xs"
                onClick={() => goto(`/datasets/${datasetId}/generate`)}
              >
                <ArrowLeft size={12} /> Go to Generation
              </button>
            </div>
          </div>
        </div>
      )}

      {loadError && <ErrorState message={loadError} onRetry={loadProfile} />}

      {loadingProfile && !loadError && (
        <div className="dx-card">
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-ink-500">
            <Loader2 size={16} className="animate-spin" />
            Loading dataset context…
          </div>
        </div>
      )}

      {!loadingProfile && !loadError && (
        <>
          {/* Header stat cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={BarChart3}
              label="Overall score"
              value={overallScore != null ? Number(overallScore).toFixed(2) : null}
              hint={
                overallScore != null
                  ? 'Mean across available dimensions'
                  : undefined
              }
              accent={
                overallScore != null
                  ? toneForScore(overallScore)
                  : 'ink'
              }
              loading={running && !evaluation}
            />
            <StatCard
              icon={ListChecks}
              label="Dimensions evaluated"
              value={CATEGORY_ORDER.filter((k) => categories[k]).length}
              hint={`of ${CATEGORY_ORDER.length}`}
              loading={running && !evaluation}
              accent="brand"
            />
            <StatCard
              icon={ShieldCheck}
              label="Dataset"
              value={profile?.name || batchEntry?.fileName || `#${datasetId}`}
              loading={loadingProfile}
              accent="ink"
            />
            <StatCard
              icon={Info}
              label="Result ID"
              value={resultId || null}
              hint={evaluation?.data?.dataset_id != null ? `Synthetic dataset #${evaluation.data.dataset_id}` : undefined}
              accent="ink"
            />
          </div>

          {/* Running state */}
          {running && !evaluation && (
            <div className="mt-6 dx-card p-6">
              <div className="flex items-center gap-3">
                <Loader2 size={18} className="animate-spin text-brand-600" />
                <div>
                  <p className="text-sm font-semibold text-ink-900">
                    Running evaluation…
                  </p>
                  <p className="text-xs text-ink-500">
                    Statistical similarity, correlation, ML utility, and referential
                    integrity are computed in one pass.
                  </p>
                </div>
              </div>
              <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                <div className="h-full w-1/3 animate-pulse rounded-full bg-brand-500" />
              </div>
            </div>
          )}

          {/* Error */}
          {!running && runError && (
            <div className="mt-6">
              <ErrorState
                title="Evaluation failed"
                message={runError}
                onRetry={runEvaluation}
              />
            </div>
          )}

          {/* Results */}
          {!running && !runError && evaluation && anyCategory && (
            <>
              {/* Success banner */}
              <div className="mt-6 dx-card p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
                      <CheckCircle2 size={20} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-ink-900">
                        {evaluation?.message || 'Evaluation completed'}
                      </p>
                      <p className="mt-0.5 text-[11px] text-ink-500">
                        {CATEGORY_ORDER.filter((k) => categories[k]).length} dimension(s)
                        returned by the backend.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      className="dx-btn-outline"
                      onClick={() => navigate('/algorithms')}
                      title="Learn how each algorithm generates data"
                    >
                      <Brain size={14} /> Algorithms
                    </button>
                    <button
                      className="dx-btn-primary"
                      onClick={() => navigate(`/evaluations?result_id=${resultId}`)}
                    >
                      Open dashboard <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Dimension tabs */}
              <div className="mt-6">
                <h2 className="mb-3 text-sm font-semibold text-ink-900">
                  Evaluation dimensions
                </h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {CATEGORY_ORDER.map((key) => (
                    <CategoryScoreCard
                      key={key}
                      categoryKey={key}
                      section={categories[key]}
                      active={activeCategory === key}
                      onClick={() => setActiveCategory(key)}
                    />
                  ))}
                </div>
              </div>

              {/* Active panel */}
              <div className="mt-6">{renderCategoryPanel()}</div>

              {/* Raw response */}
              {evaluation?.raw && (
                <details className="mt-6">
                  <summary className="cursor-pointer text-[11px] font-medium text-ink-500 hover:text-ink-700">
                    Raw response
                  </summary>
                  <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-ink-900 p-3 text-[11px] leading-relaxed text-ink-100">
                    {JSON.stringify(evaluation.raw, null, 2)}
                  </pre>
                </details>
              )}
            </>
          )}

          {/* Ready state */}
          {!running && !runError && !evaluation && resultId && (
            <div className="mt-6">
              <EmptyState
                icon={ShieldCheck}
                title="Ready to evaluate"
                description={`Click "Run evaluation" to compare the synthetic data of result #${resultId} against the source dataset.`}
                action={
                  <button className="dx-btn-primary mt-2" onClick={runEvaluation}>
                    <PlayCircle size={14} /> Run evaluation
                  </button>
                }
              />
            </div>
          )}

          {/* About panel */}
          <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2"></div>
            <aside className="space-y-4">
              <div className="dx-card p-5">
                <div className="flex items-center gap-2 text-brand-600">
                  <Info size={16} />
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    About evaluation
                  </span>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-ink-600">
                  <li>· Compares synthetic columns against the source dataset.</li>
                  <li>
                    · Each dimension has a "How is this calculated?" panel below
                    its charts.
                  </li>
                  <li>
                    · Uses the saved <code className="font-mono">result_id</code> from
                    the last generation run.
                  </li>
                  <li>
                    · Higher score = more similar to the source.
                  </li>
                  <li>
                    · <button
                        onClick={() => navigate('/algorithms')}
                        className="text-brand-600 hover:underline"
                      >
                        Compare generation algorithms →
                      </button>
                  </li>
                </ul>
              </div>
            </aside>
          </div>
        </>
      )}
    </>
  )
}