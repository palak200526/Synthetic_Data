import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Loader2, ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { getErrorMessage } from '../utils/errors.js'
import FormField from '../components/FormField.jsx'

export default function OtpVerify() {
  const { verifyOtp } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const email = location.state?.email
  const from = location.state?.from || '/dashboard'

  const [otp, setOtp] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!email) {
      navigate('/login', { replace: true })
      return
    }
    if (!otp || otp.trim().length < 4) {
      setError('Enter the verification code.')
      return
    }

    setLoading(true)
    try {
      await verifyOtp({ email, otp: otp.trim() })
      navigate(from, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center gap-2 text-brand-600">
        <ShieldCheck size={18} />
        <span className="text-xs font-semibold uppercase tracking-wider">
          Two-step verification
        </span>
      </div>

      <h1 className="text-xl font-semibold tracking-tight text-ink-900">
        Verify your sign-in
      </h1>
      <p className="mt-1 text-sm text-ink-500">
        We sent a verification code to{' '}
        <span className="font-medium text-ink-700">
          {email || 'your email'}
        </span>
        .
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div ref={inputRef}>
          <FormField
            label="Verification code"
            type="text"
            value={otp}
            onChange={(v) => setOtp(v.replace(/\s/g, ''))}
            placeholder="Enter code"
            autoComplete="one-time-code"
            disabled={loading}
            error={error}
            hint="Check your inbox for the one-time code."
          />
        </div>

        <button
          type="submit"
          className="dx-btn-primary w-full"
          disabled={loading}
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          {loading ? 'Verifying…' : 'Verify and continue'}
        </button>
      </form>

      <div className="mt-6 flex items-center justify-between text-xs">
        <Link
          to="/login"
          className="font-medium text-brand-600 hover:underline"
        >
          Use a different account
        </Link>
      </div>
    </div>
  )
}