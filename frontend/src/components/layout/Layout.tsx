import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { BottomTabBar } from './BottomTabBar'
import { UserTour } from '@/components/tour/UserTour'

export function Layout() {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <TopBar />
      <Sidebar />
      <main
        className="flex-1 lg:ml-56 pb-20 lg:pb-0"
        style={{ paddingRight: 'env(safe-area-inset-right, 0px)' }}
      >
        <Outlet />
      </main>
      <BottomTabBar />
      <UserTour />
    </div>
  )
}
