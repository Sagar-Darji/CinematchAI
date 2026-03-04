import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { UserTour } from '@/components/tour/UserTour'

export function Layout() {
  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <Sidebar />
      <main
        className="flex-1 ml-16 md:ml-56 min-h-screen"
        style={{ paddingRight: 'env(safe-area-inset-right, 0px)' }}
      >
        <Outlet />
      </main>
      <UserTour />
    </div>
  )
}
