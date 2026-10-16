// src/components/AlgorithmParameterPanel.jsx
import { useState, useMemo } from 'react'
import {
  Sliders,
  HelpCircle,
  Info,
  RotateCcw,
  Sparkles,
  Zap,
  TrendingUp,
  Clock,
  Shield,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Layers,
  Cpu,
  Boxes,
  Activity,
  FileCheck2,
} from 'lucide-react'
import {
  MODEL_PARAMS,
  getDefaultParams,
  getParamDynamicGuidance,
  getModelById,
} from '../api/generationApi.js'

export default function AlgorithmParameterPanel({
  modelId,
  paramValues = {},
  onChange,
  disabled = false,
}) {
  const [mode, setMode] = useState('basic') // 'basic' | 'advanced'
  const [expandedKeys, setExpandedKeys] = useState(() => new Set())
  const [showMetricGuide, setShowMetricGuide] = useState(false)

  const selectedModel = useMemo(() => getModelById(modelId), [modelId])
  const allParams = useMemo(() => MODEL_PARAMS[modelId] || [], [modelId])

  // Filter parameters by current mode
  const hasAdvanced = useMemo(() => allParams.some((p) => p.category === 'advanced'), [allParams])

  const displayedParams = useMemo(() => {
    if (mode === 'basic') {
      const basicList = allParams.filter((p) => p.category === 'basic')
      // If a model has no basic parameters, fallback to showing all
      return basicList.length > 0 ? basicList : allParams
    }
    return allParams
  }, [allParams, mode])

  const toggleExpand = (key) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const handleParamChange = (key, rawValue) => {
    const paramDef = allParams.find((p) => p.key === key)
    let processedValue = rawValue

    if (paramDef?.type === 'number') {
      if (rawValue === '' || rawValue === null || rawValue === undefined) {
        processedValue = ''
      } else {
        const num = Number(rawValue)
        processedValue = Number.isNaN(num) ? '' : num
      }
    } else if (paramDef?.type === 'boolean') {
      if (rawValue === 'true' || rawValue === true) processedValue = true
      else if (rawValue === 'false' || rawValue === false) processedValue = false
      else processedValue = rawValue
    }

    const next = { ...paramValues }
    if (processedValue === '') {
      delete next[key] // blank = use the default; never send '' to the backend
    } else {
      next[key] = processedValue
    }
    onChange(next)
  }

  // Keep typed numbers inside the allowed range when the user leaves the field
  const handleNumberBlur = (param) => {
    const raw = paramValues[param.key]
    if (raw === undefined || raw === '') return
    let num = Number(raw)
    if (Number.isNaN(num)) return
    if (param.min !== undefined && num < param.min) num = param.min
    if (param.max !== undefined && num > param.max) num = param.max
    if (num !== raw) handleParamChange(param.key, num)
  }

  const handleResetToDefaults = () => {
    const defaults = getDefaultParams(modelId)
    onChange(defaults)
  }

  // Count how many parameters are currently customized from defaults
  const customCount = useMemo(() => {
    let count = 0
    for (const p of allParams) {
      const current = paramValues[p.key]
      if (
        current !== undefined &&
        current !== '' &&
        p.defaultValue !== undefined &&
        String(current) !== String(p.defaultValue)
      ) {
        count++
      }
    }
    return count
  }, [allParams, paramValues])

  return (
    <div className="mt-6 dx-card overflow-hidden border border-ink-200/80 shadow-sm">
      {/* ── Top Bar / Header ────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 bg-gradient-to-r from-ink-50/70 via-white to-ink-50/40 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
            <Sliders size={16} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink-900">
                Algorithm Parameters
              </h3>
              <span className="rounded-md bg-ink-100 px-2 py-0.5 text-[11px] font-medium text-ink-700">
                {selectedModel?.label || modelId}
              </span>
              {customCount > 0 && (
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 border border-amber-200">
                  {customCount} customized
                </span>
              )}
            </div>
            <p className="text-xs text-ink-500">
              The defaults work well for most data. Change a setting only if you need to.
            </p>
          </div>
        </div>

        {/* ── Mode Switcher & Reset Button ────────────────────────── */}
        <div className="flex items-center gap-2">
          {/* Segmented Control (only when the model has advanced settings) */}
          {hasAdvanced && (
          <div className="inline-flex rounded-lg border border-ink-200 bg-ink-50/70 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setMode('basic')}
              className={[
                'rounded-md px-3 py-1 transition-all',
                mode === 'basic'
                  ? 'bg-white font-semibold text-ink-900 shadow-sm'
                  : 'text-ink-600 hover:text-ink-900',
              ].join(' ')}
            >
              Basic
            </button>
            <button
              type="button"
              onClick={() => setMode('advanced')}
              className={[
                'flex items-center gap-1 rounded-md px-3 py-1 transition-all',
                mode === 'advanced'
                  ? 'bg-white font-semibold text-ink-900 shadow-sm'
                  : 'text-ink-600 hover:text-ink-900',
              ].join(' ')}
            >
              <Cpu size={12} />
              Advanced
            </button>
          </div>
          )}

          {/* Reset to Defaults */}
          <button
            type="button"
            onClick={handleResetToDefaults}
            disabled={disabled}
            title="Reset all settings to recommended defaults"
            className="flex items-center gap-1.5 rounded-lg border border-ink-200 bg-white px-2.5 py-1 text-xs font-medium text-ink-700 shadow-sm transition-colors hover:bg-ink-50 hover:text-ink-900 disabled:opacity-50"
          >
            <RotateCcw size={12} className="text-ink-500" />
            <span>Reset to Defaults</span>
          </button>
        </div>
      </div>

      {/* ── Parameters List ─────────────────────────────────────────── */}
      <div className="divide-y divide-ink-100 bg-white">
        {displayedParams.map((param) => {
          const rawVal = paramValues[param.key]
          const currentVal = rawVal !== undefined && rawVal !== '' ? rawVal : param.defaultValue
          const isExpanded = expandedKeys.has(param.key)
          const guidance = getParamDynamicGuidance(modelId, param.key, currentVal)
          const isCustomized =
            param.defaultValue !== undefined &&
            rawVal !== undefined &&
            rawVal !== '' &&
            String(rawVal) !== String(param.defaultValue)

          return (
            <div
              key={param.key}
              className={[
                'p-4 transition-colors',
                isCustomized ? 'bg-amber-50/20' : 'hover:bg-ink-50/30',
              ].join(' ')}
            >
              {/* Row Header + Input Control */}
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                {/* Left: Metadata & summary */}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink-900">
                      {param.label}
                    </span>
                  </div>

                  <p className="mt-1 text-xs text-ink-600 leading-relaxed">
                    {param.help || param.whatItControls}
                  </p>

                  {/* Dynamic Guidance Pill if customized */}
                  {guidance && guidance.status !== 'default' && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span
                        className={[
                          'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium border',
                          guidance.tone === 'amber'
                            ? 'border-amber-200 bg-amber-50 text-amber-800'
                            : guidance.tone === 'blue'
                              ? 'border-blue-200 bg-blue-50 text-blue-800'
                              : guidance.tone === 'teal'
                                ? 'border-teal-200 bg-teal-50 text-teal-800'
                                : guidance.tone === 'purple'
                                  ? 'border-purple-200 bg-purple-50 text-purple-800'
                                  : guidance.tone === 'indigo'
                                    ? 'border-indigo-200 bg-indigo-50 text-indigo-800'
                                    : guidance.tone === 'emerald'
                                      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                                      : 'border-ink-200 bg-ink-50 text-ink-700',
                        ].join(' ')}
                      >
                        <Zap size={11} />
                        {guidance.tag}
                      </span>
                      <span className="text-[11px] text-ink-600">
                        {guidance.message}
                      </span>
                    </div>
                  )}
                </div>

                {/* Right: Input Control */}
                <div className="w-full sm:w-56 shrink-0">
                  {param.type === 'select' ? (
                    <select
                      value={currentVal ?? param.defaultValue}
                      onChange={(e) => handleParamChange(param.key, e.target.value)}
                      disabled={disabled}
                      className="dx-input text-xs font-medium"
                    >
                      {param.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt} {opt === param.defaultValue ? '(Default)' : ''}
                        </option>
                      ))}
                    </select>
                  ) : param.type === 'boolean' ? (
                    <select
                      value={String(currentVal ?? param.defaultValue)}
                      onChange={(e) =>
                        handleParamChange(param.key, e.target.value === 'true')
                      }
                      disabled={disabled}
                      className="dx-input text-xs font-medium"
                    >
                      <option value="true">
                        True / Enabled {param.defaultValue === true ? '(Default)' : ''}
                      </option>
                      <option value="false">
                        False / Disabled {param.defaultValue === false ? '(Default)' : ''}
                      </option>
                    </select>
                  ) : (
                    <div className="relative">
                      <input
                        type="number"
                        min={param.min}
                        max={param.max}
                        step={param.step || 1}
                        value={currentVal ?? param.defaultValue}
                        onChange={(e) => handleParamChange(param.key, e.target.value)}
                        onBlur={() => handleNumberBlur(param)}
                        disabled={disabled}
                        className="dx-input text-xs font-mono font-medium pr-8"
                      />
                      {isCustomized && (
                        <button
                          type="button"
                          onClick={() => handleParamChange(param.key, param.defaultValue)}
                          title="Reset to default"
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700"
                        >
                          <RotateCcw size={12} />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Accordion Toggle: Explain Parameter & Trade-offs */}
              <div className="mt-2.5">
                <button
                  type="button"
                  onClick={() => toggleExpand(param.key)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 hover:text-brand-800"
                >
                  <Info size={13} />
                  <span>{isExpanded ? 'Hide details' : 'Learn more'}</span>
                  {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </button>

                {/* Expandable Details Container */}
                {isExpanded && (
                  <div className="mt-2.5 rounded-xl border border-ink-200/80 bg-ink-50/50 p-3.5 text-xs text-ink-700 space-y-3">
                    {/* 0. Technical info (hidden until the user asks for details) */}
                    <p className="text-[11px] text-ink-500">
                      Technical name:{' '}
                      <code className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-ink-600">
                        {param.key}
                      </code>
                      {' · '}Default:{' '}
                      <strong className="font-semibold text-ink-600">{String(param.defaultValue)}</strong>
                      {' · '}
                      {param.category === 'basic' ? 'Recommended to review' : 'Advanced setting'}
                    </p>
                    {/* 1a. When to change it */}
                    {param.whenToChange && (
                      <div className="rounded-lg border border-emerald-100 bg-emerald-50/60 p-2.5">
                        <p className="font-semibold text-emerald-900 flex items-center gap-1.5 text-[11px]">
                          <CheckCircle2 size={13} className="text-emerald-700" />
                          When should you change this?
                        </p>
                        <p className="mt-0.5 text-[11px] text-emerald-800 leading-relaxed">
                          {param.whenToChange}
                        </p>
                      </div>
                    )}

                    {/* 1. Effect on Generated Data */}
                    <div>
                      <p className="font-semibold text-ink-900 flex items-center gap-1.5">
                        <TrendingUp size={13} className="text-brand-600" />
                        Effect of changing this value
                      </p>
                      {typeof param.effectOnData === 'object' && param.effectOnData ? (
                        <div className="mt-1 space-y-1 pl-4 text-[11px] leading-relaxed">
                          {param.effectOnData.increase && (
                            <p>
                              <strong className="text-ink-800">Increasing:</strong>{' '}
                              {param.effectOnData.increase}
                            </p>
                          )}
                          {param.effectOnData.decrease && (
                            <p>
                              <strong className="text-ink-800">Decreasing:</strong>{' '}
                              {param.effectOnData.decrease}
                            </p>
                          )}
                          {Object.entries(param.effectOnData)
                            .filter(([k]) => k !== 'increase' && k !== 'decrease')
                            .map(([optKey, optDesc]) => (
                              <p key={optKey}>
                                <strong className="text-ink-800 font-mono">"{optKey}":</strong>{' '}
                                {optDesc}
                              </p>
                            ))}
                        </div>
                      ) : (
                        <p className="mt-1 text-[11px] pl-4">{String(param.effectOnData)}</p>
                      )}
                    </div>

                    {/* 2. Trade-offs */}
                    {param.tradeOffs && (
                      <div>
                        <p className="font-semibold text-ink-900 flex items-center gap-1.5">
                          <AlertTriangle size={13} className="text-amber-600" />
                          Trade-offs to consider
                        </p>
                        <p className="mt-0.5 text-[11px] pl-4 leading-relaxed text-ink-700">
                          {param.tradeOffs}
                        </p>
                      </div>
                    )}

                    {/* 3. Practical Supply Chain Example */}
                    {param.supplyChainExample && (
                      <div className="rounded-lg border border-brand-100 bg-brand-50/60 p-2.5">
                        <p className="font-semibold text-brand-900 flex items-center gap-1.5 text-[11px]">
                          <Boxes size={13} className="text-brand-700" />
                          Supply Chain Example
                        </p>
                        <p className="mt-0.5 text-[11px] text-brand-800 leading-relaxed">
                          {param.supplyChainExample}
                        </p>
                      </div>
                    )}

                    {/* 4. What to Check After Generation */}
                    {param.whatToCheckAfter && (
                      <div className="border-t border-ink-200/60 pt-2 flex items-start gap-1.5 text-[11px] text-ink-600">
                        <FileCheck2 size={13} className="text-emerald-600 shrink-0 mt-0.5" />
                        <span>
                          <strong className="text-ink-800">What to check after generation:</strong>{' '}
                          {param.whatToCheckAfter}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Post-Generation Metric Guide (collapsed by default) ─────── */}
      <div className="border-t border-ink-100 bg-gradient-to-b from-white to-ink-50/50 p-4 text-xs">
        <button
          type="button"
          onClick={() => setShowMetricGuide((v) => !v)}
          className="inline-flex items-center gap-2 font-medium text-brand-700 hover:text-brand-800"
        >
          <Activity size={14} className="text-brand-600" />
          <span>{showMetricGuide ? 'Hide: how results are checked' : 'How are the results checked?'}</span>
          {showMetricGuide ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {showMetricGuide && (
          <>
            <p className="mt-2 text-xs text-ink-500 mb-3 leading-relaxed">
              Changing a setting may improve one quality score while lowering another:
            </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          <div className="rounded-lg border border-ink-100 bg-white p-2.5 shadow-2xs">
            <p className="font-semibold text-ink-800 flex items-center gap-1.5 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Statistical Similarity
            </p>
            <p className="mt-1 text-[11px] text-ink-500 leading-normal">
              Measures whether synthetic column distributions (means, percentiles, shapes) mirror real historical data.
            </p>
          </div>

          <div className="rounded-lg border border-ink-100 bg-white p-2.5 shadow-2xs">
            <p className="font-semibold text-ink-800 flex items-center gap-1.5 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-blue-500" />
              Correlation & Dependencies
            </p>
            <p className="mt-1 text-[11px] text-ink-500 leading-normal">
              Validates that mathematical relationships (e.g. quantity × unit_price ≈ total) are faithfully reproduced.
            </p>
          </div>

          <div className="rounded-lg border border-ink-100 bg-white p-2.5 shadow-2xs">
            <p className="font-semibold text-ink-800 flex items-center gap-1.5 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-purple-500" />
              ML Utility
            </p>
            <p className="mt-1 text-[11px] text-ink-500 leading-normal">
              Tests whether downstream machine learning models trained on synthetic data perform well on real held-out data.
            </p>
          </div>

          <div className="rounded-lg border border-ink-100 bg-white p-2.5 shadow-2xs">
            <p className="font-semibold text-ink-800 flex items-center gap-1.5 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              Business-Rule Validity
            </p>
            <p className="mt-1 text-[11px] text-ink-500 leading-normal">
              Verifies domain requirements (e.g. shipment date ≥ order date, inventory stock ≥ 0, positive prices).
            </p>
          </div>

          <div className="rounded-lg border border-ink-100 bg-white p-2.5 shadow-2xs">
            <p className="font-semibold text-ink-800 flex items-center gap-1.5 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              Privacy & Duplicate Guard
            </p>
            <p className="mt-1 text-[11px] text-ink-500 leading-normal">
              Guarantees the model has not simply memorized or copied real supplier or order records verbatim.
            </p>
          </div>

          <div className="rounded-lg border border-brand-100 bg-brand-50/50 p-2.5 shadow-2xs">
            <p className="font-semibold text-brand-900 flex items-center gap-1.5 text-[11px]">
              <Sparkles size={11} className="text-brand-600" />
              Improve Quality Workflow
            </p>
            <p className="mt-1 text-[11px] text-brand-700 leading-normal">
              After initial generation, review metrics and use "Improve Quality" to apply marginal matching and duplicate filtering.
            </p>
          </div>
        </div>
          </>
        )}
      </div>
    </div>
  )
}