import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

/**
 * F51: fetches /wordbank/stats on mount (and on window focus, so the
 * badge stays accurate if a drill was completed in another tab).
 * Returns { dueCount, totalWords, isLoading }. Silently no-ops when
 * signed out or on fetch failure — a stale/missing badge is a minor
 * cosmetic issue, not worth surfacing as an app-wide error.
 */
export function useWordBankStats() {
  const { isAuthenticated } = useAuth()
  const [dueCount, setDueCount] = useState(0)
  const [totalWords, setTotalWords] = useState(0)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    let cancelled = false

    function load() {
      api.get('/wordbank/stats')
        .then(data => {
          if (cancelled) return
          setDueCount(data.due_count ?? 0)
          setTotalWords(data.total_words ?? 0)
        })
        .catch(() => { /* badge just stays at last-known value */ })
        .finally(() => { if (!cancelled) setIsLoading(false) })
    }

    load()
    window.addEventListener('focus', load)
    return () => {
      cancelled = true
      window.removeEventListener('focus', load)
    }
  }, [isAuthenticated])

  return { dueCount, totalWords, isLoading: isAuthenticated ? isLoading : false }
}
