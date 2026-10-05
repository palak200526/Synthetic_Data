// src/components/AlgorithmSummaryCard.jsx
import { GitBranch, Brain, Sparkles, Zap, AlertTriangle, CheckCircle2, Clock } from 'lucide-react'

export const ALGORITHM_INFO = {
  gaussian_copula: {
    id: 'gaussian_copula',
    label: 'Gaussian Copula',
    short: 'Statistical',
    icon: GitBranch,
    accent: 'brand',
    speed: 'Fast',
    speedTone: 'emerald',
    tagline: 'Distribution-faithful and fast',
    oneLiner:
      "Models each column's distribution, then links them together with a Gaussian copula to reproduce linear correlations.",
    howItWorks: [
      'Each numeric column is transformed into a normal distribution using a quantile transformer.',
      'Categorical columns are stored as empirical frequency distributions.',
      'A correlation matrix is learned across the transformed numeric columns.',
      'New rows are drawn as correlated normal vectors, then inverse-transformed back to the original scale.',
    ],
    strengths: [
      'Very fast, even on wide tables',
      'Preserves each column\u2019s marginal distribution',
      'Preserves linear correlations well',
    ],
    limitations: [
      'Assumes a joint Gaussian dependence structure',
      'Struggles with non-linear relationships',
      'Categorical interactions are captured only marginally',
    ],
    bestFor: 'Numeric-heavy tabular data where speed matters',
    goodFor: ['distribution', 'linear_correlation'],
  },

  ctgan: {
    id: 'ctgan',
    label: 'CTGAN',
    short: 'Deep generative (GAN)',
    icon: Brain,
    accent: 'violet',
    speed: 'Slow',
    speedTone: 'amber',
    tagline: 'Captures complex, non-linear structure',
    oneLiner:
      'A conditional tabular GAN that learns adversarial representations of your data to capture intricate column interactions.',
    howItWorks: [
      'Numeric columns are min-max scaled; categorical columns are encoded as indices.',
      'A generator network maps random noise to synthetic rows.',
      'A discriminator network tries to tell real rows from synthetic ones.',
      'Both networks train adversarially until the discriminator can no longer separate them.',
      'Numeric outputs are reshaped back to the empirical distribution via quantile calibration.',
    ],
    strengths: [
      'Captures non-linear dependencies between columns',
      'Handles mixed-type tables (numeric + categorical)',
      'Often produces the highest ML utility scores',
    ],
    limitations: [
      'Training takes minutes on large tables',
      'Sensitive to hyperparameters (epochs, batch size, learning rate)',
      'Can collapse to a small set of rows on small datasets',
    ],
    bestFor: 'Mixed-type datasets where fidelity matters more than speed',
    goodFor: ['nonlinear', 'mixed_types', 'ml_utility'],
  },

  tvae: {
    id: 'tvae',
    label: 'TVAE',
    short: 'Deep generative (VAE)',
    icon: Sparkles,
    accent: 'emerald',
    speed: 'Slow',
    speedTone: 'amber',
    tagline: 'Smooth latent space, stable training',
    oneLiner:
      'A variational autoencoder that compresses rows into a compact latent space and reconstructs them from samples.',
    howItWorks: [
      'An encoder network compresses each row into a small latent vector (mean + variance).',
      'A decoder network reconstructs a row from a sampled latent vector.',
      'Training maximizes reconstruction quality while keeping the latent space smooth (KL divergence).',
      'New rows are produced by sampling latent vectors and decoding them.',
    ],
    strengths: [
      'Smoother latent space reduces mode collapse vs CTGAN',
      'Well-suited to smaller datasets',
      'Deterministic training, easier to reproduce',
    ],
    limitations: [
      'Tends to smooth out extreme values',
      'May under-represent rare categorical categories',
      'Slower than Gaussian Copula',
    ],
    bestFor: 'Smaller datasets or dense, continuous distributions',
    goodFor: ['stability', 'small_data'],
  },
}

function Chip({ children, tone = 'ink' }) {
  const tones = {
    emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber:   'bg-amber-50 text-amber-700 ring-amber-200',
    violet:  'bg-violet-50 text-violet-700 ring-violet-200',
    brand:   'bg-brand-50 text-brand-700 ring-brand-200',
    ink:     'bg-ink-100 text-ink-600 ring-ink-200',
  }
  return (
    <span className={['inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset', tones[tone]].join(' ')}>
      {children}
    </span>
  )
}

/**
 * Compact card used in the model picker.
 */
export function AlgorithmPickerCard({ algorithmId, active, disabled, onClick }) {
  const info = ALGORITHM_INFO[algorithmId]
  if (!info) return null
  const Icon = info.icon

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        'flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition',
        active
          ? 'border-brand-400 bg-brand-50/40 ring-2 ring-brand-500/20'
          : 'border-ink-200 bg-white hover:border-brand-300 hover:bg-ink-50/40',
        disabled ? 'opacity-60 cursor-not-allowed' : '',
      ].join(' ')}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
            <Icon size={15} />
          </div>
          <span className="truncate text-sm font-semibold text-ink-900">
            {info.label}
          </span>
        </div>
        <Chip tone={info.speedTone}>
          <Clock size={9} /> {info.speed}
        </Chip>
      </div>
      <p className="text-[11px] font-medium text-ink-500">{info.tagline}</p>
      <p className="text-xs leading-snug text-ink-600">{info.oneLiner}</p>
    </button>
  )
}

/**
 * Full expanded card, used in the algorithm comparison section.
 */
export default function AlgorithmSummaryCard({ algorithmId, defaultOpen = false }) {
  const info = ALGORITHM_INFO[algorithmId]
  if (!info) return null
  const Icon = info.icon

  return (
    <div className="dx-card overflow-hidden">
      <div className="flex items-start gap-3 border-b border-ink-100 p-5">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-ink-900">{info.label}</h3>
            <Chip tone="ink">{info.short}</Chip>
            <Chip tone={info.speedTone}>
              <Clock size={9} /> {info.speed}
            </Chip>
          </div>
          <p className="mt-1 text-xs text-ink-500">{info.oneLiner}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-0 sm:grid-cols-3">
        {/* How it works */}
        <div className="border-b border-ink-100 p-5 sm:border-b-0 sm:border-r">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            <Zap size={11} className="text-brand-600" /> How it works
          </p>
          <ol className="list-decimal space-y-1.5 pl-4 text-xs leading-relaxed text-ink-700">
            {info.howItWorks.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        </div>

        {/* Strengths */}
        <div className="border-b border-ink-100 p-5 sm:border-b-0 sm:border-r">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            <CheckCircle2 size={11} className="text-emerald-600" /> Strengths
          </p>
          <ul className="space-y-1.5 text-xs leading-relaxed text-ink-700">
            {info.strengths.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-emerald-500">·</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Limitations */}
        <div className="p-5">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            <AlertTriangle size={11} className="text-amber-600" /> Trade-offs
          </p>
          <ul className="space-y-1.5 text-xs leading-relaxed text-ink-700">
            {info.limitations.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-amber-500">·</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="border-t border-ink-100 bg-ink-50/60 px-5 py-3">
        <p className="text-[11px] text-ink-600">
          <span className="font-semibold text-ink-800">Best for: </span>
          {info.bestFor}
        </p>
      </div>
    </div>
  )
}