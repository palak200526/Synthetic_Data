import axios from 'axios'

const TOKEN_KEY = 'datrixa.token'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

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

// No 401 handling here anymore.
// AuthContext.fetchMe() is the single place that reacts to 401,
// and ProtectedRoute performs the redirect through React Router
// (client-side, no full page reload).
apiClient.interceptors.response.use(
  (res) => res,
  (error) => Promise.reject(error),
)

export default apiClient