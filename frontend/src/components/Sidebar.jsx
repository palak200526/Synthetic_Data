import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  UploadCloud,
  Database,
  Cpu,
  GitBranch,
  ShieldCheck,
  FileText,
  Settings as SettingsIcon,
  LogOut,
  Sparkles,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { listLocalDatasets } from '../utils/batchStore.js'

const NAV_SECTIONS = [
  {
    items: [
      {
        type: 'link',
        to: '/dashboard',
        label: 'Dashboard',
        icon: LayoutDashboard,
      },
    ],
  },
  {
    label: 'Data',
    items: [
      {
        type: 'link',
        to: '/upload',
        label: 'Upload Dataset',
        icon: UploadCloud,
      },
      {
        type: 'link',
        to: '/datasets',
        label: 'My Datasets',
        icon: Database,
        end: true,
      },
    ],
  },
  {
    label: 'Generation',
    items: [
      { type: 'action', action: 'generate', label: 'Generate Data', icon: Cpu },
      {
        type: 'link',
        to: '/relationships',
        label: 'Multi-Table',
        icon: GitBranch,
      },
    ],
  },
  {
    label: 'Evaluation',
    items: [
      {
        type: 'link',
        to: '/evaluations',
        label: 'Evaluation',
        icon: ShieldCheck,
      },
      {
        type: 'link',
        to: '/reports',
        label: 'Reports',
        icon: FileText,
      },
    ],
  },
]

function linkClasses(isActive) {
  return [
    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive
      ? 'bg-brand-50 text-brand-700'
      : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
  ].join(' ')
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, user } = useAuth()

  const handleGenerateData = () => {
    const datasets = listLocalDatasets()
    const last = datasets[0] // already sorted newest first
    if (last?.id) {
      const qs = last.session_id ? `?session=${last.session_id}` : ''
      navigate(`/datasets/${last.id}/generate${qs}`)
    } else {
      navigate('/datasets')
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const generateActive = location.pathname.includes('/generate')

  return (
    <aside className="hidden md:flex md:w-60 md:flex-col md:shrink-0 border-r border-ink-200 bg-white">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 px-5 border-b border-ink-200">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-brand-600 text-white">
          <Sparkles size={15} strokeWidth={2.4} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight text-ink-900">
            Datrixa
          </div>
          <div className="text-[10px] uppercase tracking-wider text-ink-400">
            Data Platform
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {NAV_SECTIONS.map((section, si) => (
          <div key={si}>
            {section.label && (
              <div className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-ink-400">
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item, ii) => {
                const Icon = item.icon

                if (item.type === 'action' && item.action === 'generate') {
                  return (
                    <button
                      key={ii}
                      type="button"
                      onClick={handleGenerateData}
                      className={[
                        'w-full',
                        linkClasses(generateActive),
                      ].join(' ')}
                    >
                      <Icon size={16} strokeWidth={2} />
                      <span>{item.label}</span>
                    </button>
                  )
                }

                return (
                  <NavLink
                    key={ii}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) => linkClasses(isActive)}
                  >
                    <Icon size={16} strokeWidth={2} />
                    <span>{item.label}</span>
                  </NavLink>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-ink-200 px-3 py-3 space-y-0.5">
        <NavLink
          to="/settings"
          className={({ isActive }) => linkClasses(isActive)}
        >
          <SettingsIcon size={16} strokeWidth={2} />
          <span>Settings</span>
        </NavLink>

        <button
          type="button"
          onClick={handleLogout}
          className="w-full flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-ink-600 hover:bg-rose-50 hover:text-rose-700 transition-colors"
        >
          <LogOut size={16} strokeWidth={2} />
          <span>Logout</span>
        </button>

        {user?.email && (
          <div className="mt-2 px-3 pt-2 border-t border-ink-100">
            <p className="text-[10px] uppercase tracking-wider text-ink-400">
              Signed in as
            </p>
            <p className="mt-0.5 truncate text-[11px] text-ink-600" title={user.email}>
              {user.email}
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}