/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext } from 'react'
import { useAuthState } from '../hooks/useAuthState'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const auth = useAuthState()
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}