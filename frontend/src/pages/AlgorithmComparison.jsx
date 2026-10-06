// src/pages/AlgorithmComparison.jsx
import { Link } from 'react-router-dom'
import { ArrowRight, Info, Sparkles } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import AlgorithmSummaryCard, { ALGORITHM_INFO } from '../components/AlgorithmSummaryCard.jsx'

const COMPARISON_ROWS = [
  { label: 'Model family',       key: 'short' },
  { label: 'Training speed',     key: 'speed' },
  { label: 'Handles non-linear', get: (i) => i.goodFor.includes('nonlinear') ? 'Yes' : 'Limited' },
  { label: 'Mixed types',        get: (i) => i.goodFor.includes('mixed_types') ? 'Yes' : 'Marginal' },
  { label: 'Mode collapse risk', get: (i) => i.id === 'ctgan' ? 'Higher' : i.id === 'tvae' ? 'Low' : 'N/A' },
  { label: 'Best for',           key: 'bestFor' },
]

export default function AlgorithmComparison() {
  const algos = Object.values(ALGORITHM_INFO)

  return (
    <>
      <PageHeader
        title="How synthetic data is generated"
        subtitle="Understand the three generation algorithms Datrixa offers, and pick the right one for your data."
        breadcrumb={
          <Link to="/dashboard" className="inline-flex items-center gap-1 hover:text-ink-700">
            Dashboard
          </Link>
        }
      />

      {/* Decision guide */}
      <div className="dx-card mb-6 p-5">
        <div className="flex items-start gap-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
            <Info size={16} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink-900">Quick decision guide</p>
            <ul className="mt-2 space-y-1 text-xs text-ink-600">
              <li>· <strong>Just want a fast, sensible baseline?</strong> Start with Gaussian Copula.</li>
              <li>· <strong>Data has complex column interactions or mixed types?</strong> Try CTGAN.</li>
              <li>· <strong>Small dataset, want stable training?</strong> Try TVAE.</li>
              <li>· <strong>Not sure?</strong> Generate with two or three and compare evaluation scores.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Comparison table */}
      <div className="dx-card mb-6 overflow-hidden">
        <div className="border-b border-ink-100 px-5 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
            At a glance
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink-200 bg-ink-50/60">
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                  Property
                </th>
                {algos.map((a) => (
                  <th key={a.id} className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                    {a.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARISON_ROWS.map((row) => (
                <tr key={row.label} className="border-b border-ink-100 last:border-b-0">
                  <td className="px-4 py-3 align-top text-xs font-medium text-ink-700">
                    {row.label}
                  </td>
                  {algos.map((a) => (
                    <td key={a.id} className="px-4 py-3 align-top text-xs text-ink-600">
                      {row.get ? row.get(a) : a[row.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-algorithm deep dive */}
      <div className="space-y-5">
        <h2 className="text-sm font-semibold text-ink-900">Deep dive</h2>
        {algos.map((a) => (
          <AlgorithmSummaryCard key={a.id} algorithmId={a.id} />
        ))}
      </div>

      <div className="mt-8 dx-card p-5">
        <div className="flex items-start gap-3">
          <Sparkles size={16} className="mt-0.5 shrink-0 text-brand-600" />
          <div>
            <p className="text-sm font-semibold text-ink-900">
              Try all three and compare
            </p>
            <p className="mt-1 text-xs text-ink-500">
              Generate the same dataset with each algorithm, then open the Evaluation
              Dashboard. Each dimension (statistical similarity, correlation, ML utility)
              gives you a numeric score you can compare side by side.
            </p>
            <Link to="/dashboard" className="dx-btn-outline mt-3 text-xs">
              Go to datasets <ArrowRight size={12} />
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}