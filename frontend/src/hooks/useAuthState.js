import { useCallback, useEffect, useState } from 'react'
import { api } from '../utils/api'

const TOKEN_KEY = 'leximind-token'
const USER_KEY = 'leximind-user'

/**
 * Core auth hook — manages token/user state, localStorage persistence.
 * Consumed by AuthContext, same pattern as usePreferences/PreferencesContext.
 */
export function useAuthState() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem(USER_KEY)
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })
  const [error, setError] = useState(null)

  useEffect(() => {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  }, [token])

  useEffect(() => {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  }, [user])

  const login = useCallback(async (email, password) => {
    setError(null)
    try {
      const data = await api.post('/auth/login', { email, password })
      setToken(data.token)
      setUser(data.user)
      return true
    } catch (err) {
      setError(err.message)
      return false
    }
  }, [])

  const register = useCallback(async (name, email, password) => {
    setError(null)
    try {
      const data = await api.post('/auth/register', { name, email, password })
      setToken(data.token)
      setUser(data.user)
      return true
    } catch (err) {
      setError(err.message)
      return false
    }
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  return { token, user, error, login, register, logout, isAuthenticated: !!token }
}