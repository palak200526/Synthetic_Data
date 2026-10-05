import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { getErrorMessage } from '../utils/errors.js'
import FormField from '../components/FormField.jsx'

export default function Signup() {
  const { signup, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true })
  }, [isAuthenticated, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')

    if (!username.trim() || !email.trim() || !password) {
      setError('Username, email, and password are required.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setLoading(true)
    try {
      const result = await signup({
        username: username.trim(),
        email: email.trim(),
        password,
      })

      if (result.status === 'authenticated') {
        navigate('/dashboard', { replace: true })
        return
      }

      // Backend created the account but did not issue a token.
      // Send the user to login with their email pre-filled.
      navigate('/login', {
        replace: true,
        state: { email: email.trim(), justSignedUp: true },
      })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold tracking-tight text-ink-900">
        Create your Datrixa account
      </h1>
      <p className="mt-1 text-sm text-ink-500">
        Start generating and evaluating synthetic data.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <FormField
          label="Username"
          value={username}
          onChange={setUsername}
          placeholder="janedoe"
          autoComplete="username"
          disabled={loading}
        />
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
          placeholder="At least 8 characters"
          autoComplete="new-password"
          disabled={loading}
          hint="Use a mix of letters, numbers, and symbols."
        />

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
        {info && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            {info}
          </div>
        )}

        <button
          type="submit"
          className="dx-btn-primary w-full"
          disabled={loading}
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      <p className="mt-6 text-xs text-ink-500">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-brand-600 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  )
}