import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Database,
  Cpu,
  ShieldCheck,
  Activity,
  UploadCloud,
  GitBranch,
  FileText,
  ArrowRight,
  Plus,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import DatasetCard from '../components/DatasetCard.jsx'
import DataTable from '../components/DataTable.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import EmptyState from '../components/EmptyState.jsx'
import ErrorState from '../components/ErrorState.jsx'
import SkeletonCard from '../components/SkeletonCard.jsx'

import { useAuth } from '../context/AuthContext.jsx'
import {
  dashboardApi,
  normalizeDashboard,
  mergeLocalDatasets,
} from '../api/dashboardApi.js'
import { getErrorMessage } from '../utils/errors.js'

const QUICK_ACTIONS = [
  {
    to: '/upload',
    icon: UploadCloud,
    title: 'Upload dataset',
    desc: 'Import a CSV to start the workflow.',
  },
  {
    to: '/relationships',
    icon: GitBranch,
    title: 'Relationship analysis',
    desc: 'Map foreign keys across related tables.',
  },
  {
    to: '/reports',
    icon: FileText,
    title: 'Reports',
    desc: 'Review and download evaluation reports.',
  },
]

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await dashboardApi.get()
      setData(mergeLocalDatasets(normalizeDashboard(res.data)))
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const stats = data?.stats || {}
  const recentDatasets = data?.recentDatasets || []
  const recentGenerations = data?.recentGenerations || []
  const recentEvaluations = data?.recentEvaluations || []

  const greeting =
    user?.name || user?.username || user?.email?.split('@')[0] || 'there'

  const scoreDisplay =
    stats.avgScore == null
      ? null
      : `${(stats.avgScore <= 1 ? stats.avgScore * 100 : stats.avgScore).toFixed(1)}%`

  return (
    <>
      <PageHeader
        title={`Welcome back, ${greeting}`}
        subtitle="A snapshot of your datasets, generations, and evaluations."
        actions={
          <button
            onClick={() => navigate('/upload')}
            className="dx-btn-primary"
          >
            <Plus size={14} /> New dataset
          </button>
        }
      />

      {error && <ErrorState message={error} onRetry={load} />}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Database}
          label="Datasets"
          value={stats.datasets ?? (recentDatasets.length || null)}
          loading={loading}
          accent="brand"
        />
        <StatCard
          icon={Cpu}
          label="Generations"
          value={stats.generations}
          loading={loading}
          accent="ink"
        />
        <StatCard
          icon={ShieldCheck}
          label="Evaluations"
          value={stats.evaluations}
          loading={loading}
          accent="ink"
        />
        <StatCard
          icon={Activity}
          label="Overall score"
          value={scoreDisplay}
          hint={
            !loading && stats.avgScore == null
              ? 'Not reported by backend'
              : undefined
          }
          loading={loading}
          accent="emerald"
        />
      </div>

      <div className="mt-8">
        <h2 className="mb-3 text-sm font-semibold text-ink-900">Quick actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {QUICK_ACTIONS.map(({ to, icon: Icon, title, desc }) => (
            <button
              key={to}
              type="button"
              onClick={() => navigate(to)}
              className="dx-card group flex items-start gap-3 p-5 text-left transition hover:border-brand-300 hover:shadow-md"
            >
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                <Icon size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink-900">{title}</p>
                <p className="mt-0.5 text-xs text-ink-500">{desc}</p>
              </div>
              <ArrowRight
                size={14}
                className="text-ink-300 transition group-hover:text-brand-500"
              />
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-900">Recent datasets</h2>
          <button
            onClick={() => navigate('/upload')}
            className="text-xs font-medium text-brand-600 hover:underline"
          >
            Upload new
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SkeletonCard className="h-28" />
            <SkeletonCard className="h-28" />
            <SkeletonCard className="h-28" />
          </div>
        ) : recentDatasets.length === 0 ? (
          <EmptyState
            icon={Database}
            title="No datasets yet"
            description="Upload your first dataset to begin profiling, generation, and evaluation."
            action={
              <button
                onClick={() => navigate('/upload')}
                className="dx-btn-primary mt-2"
              >
                <UploadCloud size={14} /> Upload dataset
              </button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recentDatasets.slice(0, 6).map((ds, i) => {
              const id = ds?.id || ds?.dataset_id
              const session = ds?.session_id
              const qs = session != null ? `?session=${session}` : ''
              return (
                <DatasetCard
                  key={id || i}
                  dataset={ds}
                  onClick={() =>
                    id
                      ? navigate(`/datasets/${id}/profile${qs}`)
                      : undefined
                  }
                />
              )
            })}
          </div>
        )}
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-semibold text-ink-900">
            Recent generations
          </h2>
          <DataTable
            loading={loading}
            data={recentGenerations}
            emptyTitle="No generations yet"
            emptyDescription="Run a generation from any dataset's Generation page."
            columns={[
              {
                key: 'name',
                header: 'Dataset',
                render: (r) =>
                  r?.dataset_name || r?.name || r?.dataset_id || '—',
              },
              {
                key: 'model',
                header: 'Model',
                render: (r) => r?.model || r?.model_type || '—',
              },
              {
                key: 'status',
                header: 'Status',
                render: (r) =>
                  r?.status ? <StatusBadge status={r.status} /> : '—',
              },
              {
                key: 'created_at',
                header: 'Created',
                render: (r) =>
                  r?.created_at
                    ? new Date(r.created_at).toLocaleString()
                    : '—',
              },
            ]}
          />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-ink-900">
            Recent evaluations
          </h2>
          <DataTable
            loading={loading}
            data={recentEvaluations}
            emptyTitle="No evaluations yet"
            emptyDescription="Evaluate a synthetic dataset to see metrics here."
            columns={[
              {
                key: 'dataset',
                header: 'Dataset',
                render: (r) =>
                  r?.dataset_name || r?.name || r?.dataset_id || '—',
              },
              {
                key: 'score',
                header: 'Score',
                render: (r) => {
                  const s = r?.overall_score
                  if (s == null) return '—'
                  return typeof s === 'number' ? s.toFixed(3) : String(s)
                },
              },
              {
                key: 'status',
                header: 'Status',
                render: (r) =>
                  r?.status ? <StatusBadge status={r.status} /> : '—',
              },
              {
                key: 'created_at',
                header: 'Created',
                render: (r) =>
                  r?.created_at
                    ? new Date(r.created_at).toLocaleString()
                    : '—',
              },
            ]}
          />
        </div>
      </div>
    </>
  )
}