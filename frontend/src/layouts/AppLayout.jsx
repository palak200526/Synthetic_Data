import { Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar.jsx'
import Header from '../components/Header.jsx'

export default function AppLayout() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-ink-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl px-5 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}