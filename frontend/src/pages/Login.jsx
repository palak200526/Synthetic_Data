import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Loader2, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { getErrorMessage } from '../utils/errors.js'
import FormField from '../components/FormField.jsx'

export default function Login() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from || '/dashboard'
  const justSignedUp = location.state?.justSignedUp === true
  const prefillEmail = location.state?.email || ''

  const [email, setEmail] = useState(prefillEmail)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true })
  }, [isAuthenticated, from, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!email.trim() || !password) {
      setError('Email and password are required.')
      return
    }

    setLoading(true)

    try {
      const result = await login({
        email: email.trim(),
        password,
      })

      if (result.status === 'otp_required') {
        navigate('/verify-otp', {
          replace: true,
          state: {
            email: email.trim(),
            from,
          },
        })
        return
      }

      navigate(from, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-8 flex items-center gap-2 lg:hidden">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-brand-600 text-white">
          <Sparkles size={14} />
        </div>
        <span className="text-sm font-semibold">Datrixa</span>
      </div>

      <h1 className="text-xl font-semibold tracking-tight text-ink-900">
        Sign in to Datrixa
      </h1>

      <p className="mt-1 text-sm text-ink-500">
        Access your datasets, generations, and evaluations.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <FormField
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="you@company.com"
          autoComplete="email"
          disabled={loading}
        />

        <FormField
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="••••••••"
          autoComplete="current-password"
          disabled={loading}
        />

        {justSignedUp && !error && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            Account created. Sign in to continue.
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          className="dx-btn-primary w-full"
          disabled={loading}
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="mt-6 text-xs text-ink-500">
        No account?{' '}
        <Link
          to="/signup"
          className="font-medium text-brand-600 hover:underline"
        >
          Create one
        </Link>
      </p>
    </div>
  )
}