import { useNavigate } from 'react-router-dom'
import {
  Settings as SettingsIcon,
  UserCircle2,
  LogOut,
  Server,
  Info,
  ShieldCheck,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { API_BASE_URL } from '../api/client.js'

function Row({ icon: Icon, label, value, mono }) {
  return (
    <div className="flex items-start gap-3 border-b border-ink-100 px-5 py-3 last:border-b-0">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ink-100 text-ink-500">
        <Icon size={14} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">
          {label}
        </p>
        <p
          className={[
            'mt-0.5 truncate text-sm text-ink-900',
            mono ? 'font-mono text-xs' : '',
          ].join(' ')}
        >
          {value || '—'}
        </p>
      </div>
    </div>
  )
}

export default function Settings() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Account and application preferences."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <div className="dx-card overflow-hidden">
            <div className="flex items-center gap-2 border-b border-ink-100 px-5 py-3">
              <UserCircle2 size={16} className="text-ink-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-600">
                Account
              </span>
            </div>
            <Row
              icon={UserCircle2}
              label="Email"
              value={user?.email}
            />
            <Row
              icon={UserCircle2}
              label="Username"
              value={user?.username || user?.name}
            />
            <Row
              icon={UserCircle2}
              label="User ID"
              value={user?.id ?? user?.user_id}
              mono
            />
          </div>

          <div className="dx-card overflow-hidden">
            <div className="flex items-center gap-2 border-b border-ink-100 px-5 py-3">
              <Server size={16} className="text-ink-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-600">
                Backend
              </span>
            </div>
            <Row
              icon={Server}
              label="API base URL"
              value={API_BASE_URL}
              mono
            />
            <Row
              icon={ShieldCheck}
              label="Auth"
              value="Bearer token (JWT)"
            />
          </div>

          <div className="dx-card overflow-hidden">
            <div className="flex items-center gap-2 border-b border-ink-100 px-5 py-3">
              <Info size={16} className="text-ink-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-600">
                Session
              </span>
            </div>
            <div className="px-5 py-4 flex items-center justify-between gap-3">
              <p className="text-xs text-ink-500">
                Sign out of Datrixa on this browser.
              </p>
              <button
                type="button"
                onClick={handleLogout}
                className="dx-btn-outline text-xs text-rose-600 border-rose-200 hover:bg-rose-50"
              >
                <LogOut size={14} /> Sign out
              </button>
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="dx-card p-5">
            <div className="flex items-center gap-2 text-brand-600">
              <SettingsIcon size={16} />
              <span className="text-xs font-semibold uppercase tracking-wider">
                About Datrixa
              </span>
            </div>
            <p className="mt-3 text-xs text-ink-600">
              Intelligent Data Transformation and Assessment Platform.
            </p>
            <p className="mt-2 text-[11px] text-ink-500">
              Synthetic data generation, LLM-assisted column analysis, and
              statistical, utility, and privacy-focused evaluation.
            </p>
            <p className="mt-3 text-[11px] text-ink-400">
              Frontend v0.1.0
            </p>
          </div>
        </aside>
      </div>
    </>
  )
}