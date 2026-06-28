/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext } from 'react'

import { usePreferences } from '../hooks/usePreferences'

const PreferencesContext = createContext(null)

export function PreferencesProvider({ children }) {
  const preferences = usePreferences()
  return (
    <PreferencesContext.Provider value={preferences}>
      {children}
    </PreferencesContext.Provider>
  )
}

export function usePrefs() {
  const context = useContext(PreferencesContext)
  if (!context) throw new Error('usePrefs must be used inside PreferencesProvider')
  return context
}