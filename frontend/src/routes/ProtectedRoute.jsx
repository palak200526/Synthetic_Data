import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import LoadingState from '../components/LoadingState.jsx'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, booting } = useAuth()
  const location = useLocation()

  if (booting) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-50">
        <LoadingState label="Restoring session…" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  }

  return children
}