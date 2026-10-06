import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { tokenStore } from '../api/client.js'
import { authApi, extractToken } from '../api/authApi.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => tokenStore.get())
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(() => !!tokenStore.get())
  const [userLoading, setUserLoading] = useState(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const setToken = useCallback((t) => {
    if (t) tokenStore.set(t)
    else tokenStore.clear()
    setTokenState(t || null)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [setToken])

  const fetchMe = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null)
      return null
    }
    setUserLoading(true)
    try {
      const res = await authApi.me()
      if (mounted.current) setUser(res.data)
      return res.data
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) {
        // Token really is rejected — drop it. ProtectedRoute will
        // bounce via React Router on the next render.
        if (mounted.current) {
          setToken(null)
          setUser(null)
        }
      } else {
        // Network / 500 / etc. Keep the token, log quietly.
        console.error('[auth/me] failed:', err?.message)
      }
      return null
    } finally {
      if (mounted.current) setUserLoading(false)
    }
  }, [setToken])

  // On mount: if a token exists, resolve the current user.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (tokenStore.get()) await fetchMe()
      if (!cancelled) setBooting(false)
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * Login. Backend contract: /auth/login ALWAYS sends an OTP on
   * correct credentials and does not return a token. So the only
   * outcomes are 'otp_required' or an exception.
   */
  const login = useCallback(async (credentials) => {
    const res = await authApi.login(credentials)

    // Defensive: honor a token if a backend variant ever returns one.
    const t = extractToken(res.data)
    if (t) {
      setToken(t)
      await fetchMe()
      return { status: 'authenticated' }
    }

    return { status: 'otp_required' }
  }, [setToken, fetchMe])

  const signup = useCallback(async (payload) => {
    const res = await authApi.signup(payload)
    const t = extractToken(res.data)
    if (t) {
      setToken(t)
      await fetchMe()
      return { status: 'authenticated' }
    }
    return { status: 'created' }
  }, [setToken, fetchMe])

  /**
   * Verify OTP. Expects the token to come back in the response body.
   * If /auth/me subsequently 401s, we keep the token and let the
   * caller navigate — ProtectedRoute will decide what to do.
   */
  const verifyOtp = useCallback(async ({ email, otp }) => {
    const res = await authApi.verifyOtp({ email, otp })
    const t = extractToken(res.data)
    if (!t) {
      throw new Error(
        'OTP verification did not return a token. ' +
          'Check the /auth/login/verify-otp response shape.',
      )
    }
    setToken(t)
    // Populate the user; failure here does not abort the flow.
    await fetchMe()
    return { status: 'authenticated' }
  }, [setToken, fetchMe])

  const value = useMemo(
    () => ({
      token,
      user,
      booting,
      userLoading,
      isAuthenticated: !!token,
      login,
      signup,
      verifyOtp,
      logout,
      refreshUser: fetchMe,
    }),
    [token, user, booting, userLoading, login, signup, verifyOtp, logout, fetchMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}