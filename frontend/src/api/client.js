import axios from 'axios'

const TOKEN_KEY = 'datrixa.token'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || '/api'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  // Default for cheap calls (auth, configs, dashboard, lists).
  // Heavy endpoints override this with a longer budget.
  timeout: 30000000000, // 6 minutes
})

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Sliding session: when the backend renews the login it sends the new token
// in the X-New-Token header. Keep it so active users are never signed out.
//
// No 401 handling here anymore.
// AuthContext.fetchMe() is the single place that reacts to 401,
// and ProtectedRoute performs the redirect through React Router
// (client-side, no full page reload).
apiClient.interceptors.response.use(
  (res) => {
    const fresh = res?.headers?.['x-new-token']
    if (fresh) tokenStore.set(fresh)
    return res
  },
  (error) => Promise.reject(error),
)

/**
 * Ask the backend to pause every running generation of this user.
 *
 * Used on sign-out. It reads the token up front and uses fetch(keepalive)
 * so the request still goes out with the CURRENT token even though the
 * token is cleared immediately afterwards (an axios call would pick the
 * token up too late) and even if the page is unloading.
 */
export function pauseActiveGenerationsKeepalive() {
  const token = tokenStore.get()
  if (!token) return
  try {
    fetch(`${API_BASE_URL}/generation/jobs/pause-active`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      keepalive: true,
    }).catch(() => {})
  } catch {
    /* best effort - the server also pauses on its own when we go silent */
  }
}

export default apiClient