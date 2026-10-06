import { LogOut, UserCircle2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b border-ink-200 bg-white px-5">
      <div className="hidden md:block text-sm text-ink-500">
        Intelligent Data Transformation and Assessment Platform
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden sm:flex items-center gap-2 rounded-lg border border-ink-200 bg-white px-3 py-1.5">
          <UserCircle2 size={16} className="text-ink-400" />
          <span className="text-sm font-medium text-ink-700 truncate max-w-[160px]">
            {user?.email || user?.name || 'Account'}
          </span>
        </div>

        <button
          onClick={handleLogout}
          className="dx-btn-ghost text-xs"
          title="Sign out"
        >
          <LogOut size={14} />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  )
}