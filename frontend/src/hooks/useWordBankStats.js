import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

/**
 * F51: fetches /wordbank/stats and the first few due words on mount
 * (and on window focus, so the badge/card stay accurate if a drill
 * was completed in another tab). Silently no-ops when signed out or
 * on fetch failure — a stale/missing badge is a minor cosmetic issue,
 * not worth surfacing as an app-wide error.
 */
export function useWordBankStats() {
  const { isAuthenticated } = useAuth()
  const [dueCount, setDueCount] = useState(0)
  const [totalWords, setTotalWords] = useState(0)
  const [dueWords, setDueWords] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    let cancelled = false

    function load() {
      Promise.all([api.get('/wordbank/stats'), api.get('/wordbank/drill')])
        .then(([stats, drillWords]) => {
          if (cancelled) return
          setDueCount(stats.due_count ?? 0)
          setTotalWords(stats.total_words ?? 0)
          setDueWords((drillWords ?? []).slice(0, 5))
        })
        .catch(() => { /* badge/card just stay at last-known values */ })
        .finally(() => { if (!cancelled) setIsLoading(false) })
    }

    load()
    window.addEventListener('focus', load)
    window.addEventListener('wordbank-updated', load)
    return () => {
      cancelled = true
      window.removeEventListener('focus', load)
      window.removeEventListener('wordbank-updated', load)
    }
  }, [isAuthenticated])

  return { dueCount, totalWords, dueWords, isLoading: isAuthenticated ? isLoading : false }
}