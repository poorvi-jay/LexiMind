import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute.jsx'

import HomePage from './pages/HomePage.jsx'
import NavBar from './components/NavBar.jsx'
import ReadingPage from './pages/ReadingPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import WritingPage from './pages/WritingPage.jsx'
import AnalyticsPage from './pages/AnalyticsPage.jsx'
import WordBankDrillPage from './pages/WordBankDrillPage.jsx'
import LoginPage from './pages/LoginPage.jsx'

export default function App() {
  return (
    <div className="min-h-screen">
      <NavBar />
      <Routes>
        <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
        <Route path="/reading" element={<ProtectedRoute><ReadingPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/writing" element={<ProtectedRoute><WritingPage /></ProtectedRoute>} />
        <Route path="/analytics" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
        <Route path="/wordbank/drill" element={<ProtectedRoute><WordBankDrillPage /></ProtectedRoute>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}