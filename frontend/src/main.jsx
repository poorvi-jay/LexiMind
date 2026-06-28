import './index.css'

import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'
import { PreferencesProvider } from './context/PreferencesContext.jsx'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <PreferencesProvider>
        <App />
      </PreferencesProvider>
    </BrowserRouter>
  </StrictMode>
)