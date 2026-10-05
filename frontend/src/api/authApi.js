import apiClient from './client.js'

// ─────────────────────────────────────────────────────────────
// Backend contract (confirmed from /docs):
//   POST /auth/signup               { username, email, password }
//   POST /auth/login                { email, password }
//   POST /auth/login/verify-otp     { email, otp }
//   GET  /auth/me                   Bearer token
// /auth/login ALWAYS issues an OTP on success — it never returns
// a token. The token is only issued by /auth/login/verify-otp.
// ─────────────────────────────────────────────────────────────

export function buildSignupPayload({ username, email, password }) {
  return { username, email, password }
}

export function buildLoginPayload({ email, password }) {
  return { email, password }
}

export function buildOtpPayload({ email, otp }) {
  return { email, otp }
}

export function extractToken(data) {
  if (!data || typeof data !== 'object') return null
  const candidates = [data, data.data, data.result, data.payload].filter(Boolean)
  for (const c of candidates) {
    const t = c.access_token || c.token || c.jwt || c.accessToken
    if (t) return t
  }
  return null
}

export const authApi = {
  signup: (payload) => apiClient.post('/auth/signup', buildSignupPayload(payload)),
  login: (payload) => apiClient.post('/auth/login', buildLoginPayload(payload)),
  verifyOtp: (payload) =>
    apiClient.post('/auth/login/verify-otp', buildOtpPayload(payload)),
  me: () => apiClient.get('/auth/me'),
}