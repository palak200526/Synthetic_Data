import { useEffect, useState } from 'react'
import { LogOut, UserCircle2, Moon, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import '../styles/dark-mode.css'

const PROFILE_PHOTO_KEY = 'datrixa_profile_photo'
const THEME_KEY = 'datrixa_theme'

function readTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export default function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [profilePhoto, setProfilePhoto] = useState(() => {
    try {
      return window.localStorage.getItem(PROFILE_PHOTO_KEY) || ''
    } catch {
      return ''
    }
  })
  const [theme, setTheme] = useState(readTheme)

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.dataset.theme = theme
    try {
      window.localStorage.setItem(THEME_KEY, theme)
    } catch {
      // Theme still works for the current session when storage is unavailable.
    }
  }, [theme])

  useEffect(() => {
    const syncProfilePhoto = (event) => {
      if (event?.detail !== undefined) {
        setProfilePhoto(event.detail || '')
        return
      }
      try {
        setProfilePhoto(window.localStorage.getItem(PROFILE_PHOTO_KEY) || '')
      } catch {
        setProfilePhoto('')
      }
    }

    window.addEventListener('datrixa-profile-photo-updated', syncProfilePhoto)
    window.addEventListener('storage', syncProfilePhoto)
    return () => {
      window.removeEventListener('datrixa-profile-photo-updated', syncProfilePhoto)
      window.removeEventListener('storage', syncProfilePhoto)
    }
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const toggleTheme = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))

  return (
    <header className="flex h-16 items-center justify-between gap-4 border-b border-ink-200 bg-white px-5 transition-colors">
      <div className="flex items-center gap-2 md:hidden" aria-label="Datrixa">
        <img
          src="/datrixa-logo.png"
          alt="Datrixa"
          className="datrixa-logo-light block h-8 w-auto max-w-[145px] object-contain"
          draggable={false}
        />
        <img
          src="/datrixa-logo-white.png"
          alt=""
          aria-hidden="true"
          className="datrixa-logo-dark hidden h-8 w-auto max-w-[145px] object-contain"
          draggable={false}
        />
      </div>

      <div className="hidden md:block text-sm text-ink-500">
        Intelligent Data Transformation and Assessment Platform
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggleTheme}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-ink-200 bg-white text-ink-600 transition hover:border-brand-200 hover:bg-brand-50"
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-pressed={theme === 'dark'}
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>

        <button
          type="button"
          onClick={() => navigate('/settings')}
          className="inline-flex max-w-[220px] items-center gap-2 rounded-lg border border-ink-200 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 transition hover:border-brand-200 hover:bg-brand-50"
          title="Open account"
          aria-label="Open account"
        >
          {profilePhoto ? (
            <img src={profilePhoto} alt="" className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-ink-200" />
          ) : (
            <UserCircle2 size={18} className="shrink-0 text-ink-400" />
          )}
          <span className="truncate">Account</span>
        </button>

        <button onClick={handleLogout} className="dx-btn-ghost text-xs" title="Sign out">
          <LogOut size={14} />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  )
}
