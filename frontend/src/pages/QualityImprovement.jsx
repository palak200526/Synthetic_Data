import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, BarChart3 } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import QualityImprovementPanel from '../components/evaluation/QualityImprovementPanel.jsx'

export default function QualityImprovement() {
  const { datasetId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const resultId = searchParams.get('result_id')
  const sessionId = searchParams.get('session')

  return (
    <div className="space-y-5">
      <PageHeader
        title="Quality Improvement"
        subtitle="Improve synthetic dataset quality, compare candidate results, and review privacy and validity checks."
        breadcrumb={
          <button
            type="button"
            onClick={() => {
              const qs = new URLSearchParams()
              if (resultId) qs.set('result_id', resultId)
              if (sessionId) qs.set('session', sessionId)
              navigate(`/datasets/${datasetId}/evaluate${qs.toString() ? `?${qs.toString()}` : ''}`)
            }}
            className="inline-flex items-center gap-1 hover:text-ink-700"
          >
            <ArrowLeft size={12} /> Back to Evaluation
          </button>
        }
        actions={
          <button
            type="button"
            className="dx-btn-outline inline-flex items-center gap-2"
            onClick={() => {
              const qs = new URLSearchParams()
              if (resultId) qs.set('result_id', resultId)
              if (sessionId) qs.set('session', sessionId)
              navigate(`/datasets/${datasetId}/evaluate${qs.toString() ? `?${qs.toString()}` : ''}`)
            }}
          >
            <BarChart3 size={14} /> View Evaluation
          </button>
        }
      />

      {!resultId ? (
        <div className="dx-card p-5 text-sm text-ink-600">
          No generation result was selected. Return to Evaluation and open Quality Improvement from a dataset with a valid result.
        </div>
      ) : (
        <QualityImprovementPanel resultId={resultId} datasetId={datasetId} />
      )}
    </div>
  )
}
