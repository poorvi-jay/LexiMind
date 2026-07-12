import { useEffect, useRef, useState } from 'react'
import { usePrefs } from '../context/PreferencesContext'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

export default function WritingPage() {
  const { prefs } = usePrefs()
  const { isAuthenticated } = useAuth()
  const [content, setContent] = useState('')
  const [results, setResults] = useState({ spelling: [], grammar: [], homophones: [] })
  const [checking, setChecking] = useState(false)
  const [checkError, setCheckError] = useState(null)
  const debounceTimer = useRef(null)

  // Debounced /nlp/check call — fires 800ms after the user stops typing,
  // resetting the timer on every keystroke so it never fires mid-typing.
  useEffect(() => {
    if (!content.trim()) {
      setResults({ spelling: [], grammar: [], homophones: [] })
      setCheckError(null)
      return
    }

    if (!isAuthenticated) {
      setCheckError('Log in to enable grammar and spelling checks.')
      return
    }

    if (debounceTimer.current) clearTimeout(debounceTimer.current)

    debounceTimer.current = setTimeout(async () => {
      setChecking(true)
      setCheckError(null)
      try {
        const data = await api.post('/nlp/check', { text: content })
        setResults(data)
      } catch (err) {
        setCheckError(
          err.message === 'Not authenticated'
            ? 'Log in to enable grammar and spelling checks.'
            : 'Could not check text right now.'
        )
      } finally {
        setChecking(false)
      }
    }, 800)

    return () => clearTimeout(debounceTimer.current)
  }, [content, isAuthenticated])

  const totalIssues =
    results.spelling.length + results.grammar.length + results.homophones.length

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="mb-2 text-2xl font-bold tracking-tight text-gray-950 dark:text-white">
        Writing
      </h1>
      <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">
        Draft your writing here. Grammar, spelling, and homophone
        suggestions appear automatically as you pause typing.
      </p>

      <textarea
        value={content}
        onChange={e => setContent(e.target.value)}
        placeholder="Start typing..."
        style={{
          fontFamily: `'${prefs.font}', Arial, Verdana, sans-serif`,
          fontSize: `${prefs.fontSize}px`,
          lineHeight: prefs.lineSpacing,
          wordSpacing: `${prefs.wordSpacing}px`,
          backgroundColor: prefs.darkMode ? '#1E1E1E' : prefs.overlay,
        }}
        className="min-h-[400px] w-full rounded-2xl border border-gray-200 p-5
                   text-gray-900 shadow-sm outline-none transition-colors
                   focus-visible:border-blue-500 focus-visible:ring-2
                   focus-visible:ring-blue-200
                   dark:border-gray-800 dark:text-gray-100
                   dark:focus-visible:ring-blue-900"
        aria-label="Writing area"
      />

      <div className="mt-4 min-h-[24px] text-sm">
        {checking && <span className="text-gray-500 dark:text-gray-400">Checking...</span>}
        {!checking && checkError && (
          <span className="text-amber-600 dark:text-amber-400">{checkError}</span>
        )}
        {!checking && !checkError && totalIssues > 0 && (
          <span className="text-gray-500 dark:text-gray-400">
            {totalIssues} suggestion{totalIssues !== 1 ? 's' : ''} found
          </span>
        )}
        {!checking && !checkError && content.trim() && totalIssues === 0 && (
          <span className="text-gray-500 dark:text-gray-400">No issues found</span>
        )}
      </div>

      {totalIssues > 0 && (
        <div className="mt-4 space-y-3 rounded-2xl border border-gray-200 p-5 dark:border-gray-800">
          {results.grammar.map((issue, i) => (
            <div key={`g-${i}`} className="text-sm">
              <span className="font-semibold text-amber-600 dark:text-amber-400">Grammar: </span>
              <span className="text-gray-700 dark:text-gray-300">{issue.message}</span>
              {issue.suggestions?.length > 0 && (
                <span className="ml-1 text-gray-500 dark:text-gray-400">
                  (suggestions: {issue.suggestions.join(', ')})
                </span>
              )}
            </div>
          ))}
          {results.spelling.map((issue, i) => (
            <div key={`s-${i}`} className="text-sm">
              <span className="font-semibold text-red-600 dark:text-red-400">Spelling: </span>
              <span className="text-gray-700 dark:text-gray-300">
                "{issue.word}" &rarr; "{issue.suggestion}"
              </span>
            </div>
          ))}
          {results.homophones.map((issue, i) => (
            <div key={`h-${i}`} className="text-sm">
              <span className="font-semibold text-blue-600 dark:text-blue-400">Homophone: </span>
              <span className="text-gray-700 dark:text-gray-300">
                "{issue.word}" &rarr; "{issue.suggestion}"
              </span>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}