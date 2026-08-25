import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '../components/layout/AppLayout'
import { HomePage } from '../pages/HomePage'
import { Dashboard } from '../pages/Dashboard'
import { Claims } from '../pages/Claims'
import { ClaimDetail } from '../pages/ClaimDetail'
import { AIAssistant } from '../pages/AIAssistant'
import { Settings } from '../pages/Settings'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/claims" element={<Claims />} />
        <Route path="/claims/:claimId" element={<ClaimDetail />} />
        <Route path="/ai-assistant" element={<AIAssistant />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
