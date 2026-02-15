import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import Home from '@/pages/Home'
import Onboarding from '@/pages/Onboarding'
import Recommendations from '@/pages/Recommendations'
import Browse from '@/pages/Browse'
import Profile from '@/pages/Profile'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Onboarding is full-screen, outside the main Layout */}
        <Route path="/onboarding" element={<Onboarding />} />

        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/browse" element={<Browse />} />
          <Route path="/profile" element={<Profile />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
