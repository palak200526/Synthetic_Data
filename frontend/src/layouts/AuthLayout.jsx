import { Outlet } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

export default function AuthLayout() {
  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-ink-900 p-10 text-white">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-500">
            <Sparkles size={16} />
          </div>
          <span className="text-base font-semibold tracking-tight">Datrixa</span>
        </div>

        <div className="max-w-md">
          <h2 className="text-2xl font-semibold leading-snug tracking-tight">
            Intelligent Data Transformation and Assessment Platform
          </h2>
          <p className="mt-3 text-sm text-ink-300">
            Generate, evaluate, and validate synthetic datasets with statistical,
            utility, and privacy-aware metrics — powered by LLM-assisted column
            analysis.
          </p>
        </div>

        <p className="text-xs text-ink-500">
          © {new Date().getFullYear()} Datrixa
        </p>
      </div>

      <div className="flex items-center justify-center bg-white p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <Outlet />
        </div>
      </div>
    </div>
  )
}