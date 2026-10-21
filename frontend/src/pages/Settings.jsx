import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  UserRound, Mail, AtSign, ShieldCheck, CalendarDays, LogOut, ChevronRight,
  CircleCheck, Camera, Trash2, Pencil, Save, X, KeyRound, Clock3, UploadCloud,
  RefreshCw, Activity, CheckCircle2, AlertCircle, Eye, EyeOff,
} from 'lucide-react'

import PageHeader from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { authApi } from '../api/authApi.js'

const PROFILE_PHOTO_KEY = 'datrixa_profile_photo'

function DetailRow({ icon: Icon, label, value, hint }) {
  return (
    <div className="flex items-center gap-3 border-b border-ink-100 px-5 py-4 last:border-b-0">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ink-50 text-ink-500 ring-1 ring-inset ring-ink-100">
        <Icon size={17} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-ink-500">{label}</p>
        <p className="mt-1 break-words text-sm font-semibold text-ink-900">{value || 'Not provided'}</p>
        {hint && <p className="mt-1 text-xs text-ink-400">{hint}</p>}
      </div>
    </div>
  )
}

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
}

function formatDate(value) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString()
}

export default function Settings() {
  const navigate = useNavigate()
  const { user, logout, refreshUser } = useAuth()
  const photoInputRef = useRef(null)
  const [profilePhoto, setProfilePhoto] = useState(() => {
    try { return window.localStorage.getItem(PROFILE_PHOTO_KEY) || '' } catch { return '' }
  })
  const [photoError, setPhotoError] = useState('')

  const [editingProfile, setEditingProfile] = useState(false)
  const [username, setUsername] = useState(user?.username || user?.name || '')
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileMessage, setProfileMessage] = useState('')
  const [profileError, setProfileError] = useState('')

  const [activity, setActivity] = useState([])
  const [activityLoading, setActivityLoading] = useState(true)
  const [activityError, setActivityError] = useState('')

  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [passwordBusy, setPasswordBusy] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    setUsername(user?.username || user?.name || '')
  }, [user?.username, user?.name])

  const loadActivity = useCallback(async () => {
    setActivityLoading(true)
    setActivityError('')
    try {
      const response = await authApi.recentActivity(5)
      const items = Array.isArray(response?.data?.items) ? response.data.items : []
      const latestFive = [...items]
        .sort((a, b) => {
          const timeA = new Date(a?.occurred_at || 0).getTime()
          const timeB = new Date(b?.occurred_at || 0).getTime()
          return timeB - timeA
        })
        .slice(0, 5)
      setActivity(latestFive)
    } catch (error) {
      setActivityError(getErrorMessage(error, 'Could not load recent activity.'))
    } finally {
      setActivityLoading(false)
    }
  }, [])

  useEffect(() => { loadActivity() }, [loadActivity])

  const handlePhotoChange = (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setPhotoError('Please choose an image file.')
      return
    }
    if (file.size > 2 * 1024 * 1024) {
      setPhotoError('Please choose an image smaller than 2 MB.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      try {
        window.localStorage.setItem(PROFILE_PHOTO_KEY, dataUrl)
        setProfilePhoto(dataUrl)
        window.dispatchEvent(new CustomEvent('datrixa-profile-photo-updated', { detail: dataUrl }))
        setPhotoError('')
      } catch {
        setPhotoError('Could not save this photo in browser storage. Try a smaller image.')
      }
    }
    reader.onerror = () => setPhotoError('Could not read that image. Please try another one.')
    reader.readAsDataURL(file)
  }

  const handleRemovePhoto = () => {
    try { window.localStorage.removeItem(PROFILE_PHOTO_KEY) } catch { /* ignore storage errors */ }
    setProfilePhoto('')
    window.dispatchEvent(new CustomEvent('datrixa-profile-photo-updated', { detail: '' }))
    setPhotoError('')
  }

  const displayName = user?.username || user?.name || user?.email?.split('@')[0] || 'Datrixa User'
  const initials = useMemo(() => {
    const words = String(displayName).trim().split(/[\s._-]+/).filter(Boolean)
    return (words.length > 1 ? `${words[0][0]}${words[1][0]}` : String(words[0] || 'D').slice(0, 2)).toUpperCase()
  }, [displayName])

  const handleSaveProfile = async (event) => {
    event.preventDefault()
    setProfileError('')
    setProfileMessage('')
    const nextUsername = username.trim()
    if (nextUsername.length < 3) {
      setProfileError('Username must contain at least 3 characters.')
      return
    }
    setProfileBusy(true)
    try {
      await authApi.updateProfile({ username: nextUsername })
      await refreshUser?.()
      setProfileMessage('Profile updated successfully.')
      setEditingProfile(false)
    } catch (error) {
      setProfileError(getErrorMessage(error, 'Could not update profile.'))
    } finally {
      setProfileBusy(false)
    }
  }

  const handleChangePassword = async (event) => {
    event.preventDefault()
    setPasswordError('')
    setPasswordMessage('')
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New password and confirmation do not match.')
      return
    }
    setPasswordBusy(true)
    try {
      const response = await authApi.changePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordMessage(response?.data?.message || 'Password updated successfully.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setShowPasswordForm(false)
    } catch (error) {
      setPasswordError(getErrorMessage(error, 'Could not change password.'))
    } finally {
      setPasswordBusy(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <PageHeader title="My Account" subtitle="Manage your profile, recent activity and account security." />

      <div className="mx-auto max-w-5xl space-y-6">
        <section className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-sm">
          <div className="px-5 pt-6 sm:px-7 sm:pt-7">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-4">
                <div className="relative shrink-0">
                  <div className="grid h-20 w-20 place-items-center overflow-hidden rounded-full border border-ink-200 bg-ink-50 text-2xl font-bold text-brand-700 ring-4 ring-white">
                    {profilePhoto ? <img src={profilePhoto} alt="Profile" className="h-full w-full object-cover" /> : initials}
                  </div>
                  <button type="button" onClick={() => photoInputRef.current?.click()} className="absolute -bottom-1 -right-1 grid h-8 w-8 place-items-center rounded-full border-2 border-white bg-brand-600 text-white shadow-sm transition hover:bg-brand-700" aria-label="Change profile photo" title="Change photo">
                    <Camera size={15} />
                  </button>
                  <input ref={photoInputRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoChange} />
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-xl font-bold text-ink-900">{displayName}</h2>
                  <p className="mt-1 truncate text-sm text-ink-500">{user?.email || 'Email not available'}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <button type="button" onClick={() => photoInputRef.current?.click()} className="text-xs font-semibold text-brand-700 hover:text-brand-800">{profilePhoto ? 'Change photo' : 'Upload photo'}</button>
                    {profilePhoto && <button type="button" onClick={handleRemovePhoto} className="inline-flex items-center gap-1 text-xs font-medium text-rose-600 hover:text-rose-700"><Trash2 size={12} /> Remove</button>}
                  </div>
                  {photoError && <p role="alert" className="mt-2 max-w-md text-xs text-rose-600">{photoError}</p>}
                </div>
              </div>
              <div className="inline-flex w-fit items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200"><CircleCheck size={14} /> Account active</div>
            </div>
            <div className="mt-6 grid grid-cols-1 gap-3 border-t border-ink-100 pt-5 sm:grid-cols-3">
              <div className="rounded-xl bg-ink-50 px-4 py-3"><p className="text-xs font-medium text-ink-500">Account type</p><p className="mt-1 text-sm font-semibold text-ink-900">Datrixa user</p></div>
              <div className="rounded-xl bg-ink-50 px-4 py-3"><p className="text-xs font-medium text-ink-500">User ID</p><p className="mt-1 text-sm font-semibold text-ink-900">{user?.id ?? user?.user_id ?? '—'}</p></div>
              <div className="rounded-xl bg-ink-50 px-4 py-3"><p className="text-xs font-medium text-ink-500">Workspace</p><p className="mt-1 text-sm font-semibold text-ink-900">Synthetic Data Platform</p></div>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <section className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-sm lg:col-span-3">
            <div className="flex items-center justify-between gap-3 border-b border-ink-100 px-5 py-4">
              <div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-600"><UserRound size={17} /></div><div><h3 className="text-sm font-bold text-ink-900">Personal information</h3><p className="mt-0.5 text-xs text-ink-500">Your registered account details</p></div></div>
              {!editingProfile && <button type="button" onClick={() => { setUsername(user?.username || user?.name || ''); setProfileError(''); setProfileMessage(''); setEditingProfile(true) }} className="dx-btn-outline text-xs"><Pencil size={14} /> Edit profile</button>}
            </div>
            {editingProfile ? (
              <form onSubmit={handleSaveProfile} className="space-y-4 p-5">
                <label className="block"><span className="mb-1.5 block text-xs font-semibold text-ink-600">Username</span><input value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} maxLength={100} autoComplete="username" required className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2.5 text-sm text-ink-900 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100" /></label>
                <label className="block"><span className="mb-1.5 block text-xs font-semibold text-ink-600">Email address</span><input value={user?.email || ''} readOnly className="w-full cursor-not-allowed rounded-xl border border-ink-200 bg-ink-50 px-3 py-2.5 text-sm text-ink-500" /><span className="mt-1 block text-[11px] text-ink-400">Email is used for login and cannot be changed here.</span></label>
                {profileError && <p role="alert" className="text-xs text-rose-600">{profileError}</p>}
                <div className="flex flex-wrap gap-2"><button type="submit" disabled={profileBusy} className="dx-btn-primary text-xs"><Save size={14} /> {profileBusy ? 'Saving…' : 'Save changes'}</button><button type="button" onClick={() => { setEditingProfile(false); setProfileError('') }} className="dx-btn-outline text-xs"><X size={14} /> Cancel</button></div>
              </form>
            ) : <><DetailRow icon={UserRound} label="Full name / username" value={user?.username || user?.name} /> <DetailRow icon={Mail} label="Email address" value={user?.email} hint="Used for account identification" /> <DetailRow icon={AtSign} label="User ID" value={user?.id ?? user?.user_id} />{profileMessage && <p role="status" className="px-5 py-3 text-xs font-medium text-emerald-700">{profileMessage}</p>}</>}
          </section>

          <section className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-sm lg:col-span-2">
            <div className="flex items-center gap-3 border-b border-ink-100 px-5 py-4"><div className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><ShieldCheck size={17} /></div><div><h3 className="text-sm font-bold text-ink-900">Account security</h3><p className="mt-0.5 text-xs text-ink-500">Password and session access</p></div></div>
            <div className="px-5 py-4"><div className="flex items-start gap-3"><div className="mt-0.5 text-emerald-600"><CircleCheck size={17} /></div><div><p className="text-sm font-semibold text-ink-900">You’re signed in</p><p className="mt-1 text-xs leading-5 text-ink-500">Your account session is active on this browser.</p></div></div>
              {passwordMessage && <p role="status" className="mt-3 text-xs font-medium text-emerald-700">{passwordMessage}</p>}
              {!showPasswordForm ? <button type="button" onClick={() => { setShowPasswordForm(true); setPasswordError(''); setPasswordMessage('') }} className="dx-btn-outline mt-4 w-full justify-center text-xs"><KeyRound size={14} /> Change password</button> : (
                <form onSubmit={handleChangePassword} className="mt-4 space-y-3">
                  {[['Current password', currentPassword, setCurrentPassword, 'current-password'], ['New password', newPassword, setNewPassword, 'new-password'], ['Confirm new password', confirmPassword, setConfirmPassword, 'new-password-confirm']].map(([label, value, setter, autoComplete]) => <label key={label} className="block"><span className="mb-1.5 block text-xs font-semibold text-ink-600">{label}</span><input type={showPasswords ? 'text' : 'password'} value={value} onChange={(event) => setter(event.target.value)} autoComplete={autoComplete} required minLength={label === 'Current password' ? 1 : 8} maxLength={128} className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2.5 text-sm text-ink-900 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100" /></label>)}
                  <button type="button" onClick={() => setShowPasswords((value) => !value)} className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-500 hover:text-ink-700">{showPasswords ? <EyeOff size={13} /> : <Eye size={13} />}{showPasswords ? 'Hide passwords' : 'Show passwords'}</button>
                  <p className="text-[11px] text-ink-400">Use at least 8 characters. Your current password is verified securely on the server.</p>
                  {passwordError && <p role="alert" className="text-xs text-rose-600">{passwordError}</p>}
                  <div className="flex flex-wrap gap-2"><button type="submit" disabled={passwordBusy} className="dx-btn-primary text-xs"><KeyRound size={13} /> {passwordBusy ? 'Updating…' : 'Update password'}</button><button type="button" onClick={() => { setShowPasswordForm(false); setPasswordError(''); setCurrentPassword(''); setNewPassword(''); setConfirmPassword('') }} className="dx-btn-outline text-xs">Cancel</button></div>
                </form>
              )}
              <div className="my-4 border-t border-ink-100" />
              <button type="button" onClick={handleLogout} className="flex w-full items-center justify-between rounded-xl border border-rose-200 px-4 py-3 text-left text-sm font-semibold text-rose-700 transition hover:bg-rose-50"><span className="flex items-center gap-2"><LogOut size={16} /> Sign out of this browser</span><ChevronRight size={16} /></button>
            </div>
          </section>
        </div>

        <section className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-5 py-4"><div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-600"><Activity size={17} /></div><div><h3 className="text-sm font-bold text-ink-900">Recent activity</h3><p className="mt-0.5 text-xs text-ink-500">Your recent dataset uploads and generation jobs</p></div></div><button type="button" onClick={loadActivity} disabled={activityLoading} className="dx-btn-outline text-xs"><RefreshCw size={13} className={activityLoading ? 'animate-spin' : ''} /> Refresh</button></div>
          {activityError && <div role="alert" className="flex items-start gap-2 px-5 py-4 text-xs text-rose-600"><AlertCircle size={15} className="mt-0.5 shrink-0" />{activityError}</div>}
          {activityLoading ? <div className="flex items-center gap-2 px-5 py-6 text-sm text-ink-500"><RefreshCw size={15} className="animate-spin" /> Loading recent activity…</div> : activity.length === 0 ? <div className="px-5 py-8 text-center"><div className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-ink-50 text-ink-400"><Clock3 size={18} /></div><p className="mt-3 text-sm font-semibold text-ink-800">No recent activity yet</p><p className="mt-1 text-xs text-ink-500">Dataset uploads and generation jobs will appear here.</p></div> : <div className="divide-y divide-ink-100">{activity.map((item) => <div key={item.id} className="flex items-start gap-3 px-5 py-4"><div className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl ${item.type === 'dataset' ? 'bg-sky-50 text-sky-700' : 'bg-violet-50 text-violet-700'}`}>{item.type === 'dataset' ? <UploadCloud size={16} /> : <Activity size={16} />}</div><div className="min-w-0 flex-1"><p className="break-words text-sm font-semibold text-ink-900">{item.title}</p><p className="mt-1 text-xs text-ink-500">{formatDate(item.occurred_at)}</p></div><span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-ink-50 px-2.5 py-1 text-[11px] font-medium text-ink-600"><CheckCircle2 size={12} />{item.status}</span></div>)}</div>}
        </section>

        <div className="flex flex-col gap-2 rounded-xl border border-ink-200 bg-ink-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-2 text-xs text-ink-500"><CalendarDays size={15} /><span>Account created: {formatDate(user?.created_at)}</span></div><span className="text-xs font-medium text-ink-400">Datrixa · Intelligent Data Transformation and Assessment Platform</span></div>
      </div>
    </>
  )
}
