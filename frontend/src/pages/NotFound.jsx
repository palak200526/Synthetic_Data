import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 p-6">
      <div className="text-center">
        <p className="text-5xl font-semibold tracking-tight text-ink-900">404</p>
        <p className="mt-2 text-sm text-ink-500">This page does not exist.</p>
        <Link to="/dashboard" className="dx-btn-primary mt-5">
          Go to Dashboard
        </Link>
      </div>
    </div>
  )
}