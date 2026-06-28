import { Navigate, Route, Routes } from 'react-router-dom'

import HomePage from './pages/HomePage.jsx'
import NavBar from './components/NavBar.jsx'
import ReadingPage from './pages/ReadingPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'

export default function App() {
  return (
    <div className="min-h-screen">
      <NavBar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/reading" element={<ReadingPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}