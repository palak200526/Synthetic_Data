import { Outlet } from 'react-router-dom'

export default function AuthLayout() {
  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-ink-900 via-ink-900 to-ink-800 p-10 text-white">
        <img
          src="/datrixa-logo-white.png"
          alt="Datrixa"
          className="h-10 w-auto self-start select-none"
          draggable={false}
        />

        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            Intelligent Data Transformation and Assessment Platform
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-ink-300">
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