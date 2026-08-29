import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

// Same quality mapping the backend's update_sm2() expects (0-5).
// Framed as plain-language buttons rather than raw numbers — nobody
// wants to mentally convert "quality 4" while trying to recall a word.
const RATINGS = [
  { quality: 1, label: "Didn't know it", color: 'bg-red-50 text-red-700 hover:bg-red-100 dark:bg-red-950/30 dark:text-red-300' },
  { quality: 3, label: 'Knew it, but slow', color: 'bg-amber-50 text-amber-700 hover:bg-amber-100 dark:bg-amber-950/30 dark:text-amber-300' },
  { quality: 4, label: 'Knew it well', color: 'bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-950/30 dark:text-blue-300' },
  { quality: 5, label: 'Instantly knew it', color: 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-300' },
]

function playWord(word) {
  api.post('/tts/word', { word }).catch(err => console.error('Could not play word:', err))
}

export default function WordBankDrillPage() {
  const { isAuthenticated } = useAuth()

  const [words, setWords] = useState(null) // null = not loaded yet
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [completedCount, setCompletedCount] = useState(0)

  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false

    api.get('/wordbank/drill')
      .then(data => { if (!cancelled) setWords(data) })
      .catch(() => { if (!cancelled) setLoadError('Could not load your drill words right now.') })

    return () => { cancelled = true }
  }, [isAuthenticated])

  const currentWord = words?.[index]
  const isFinished = words && index >= words.length

  async function handleRate(quality) {
    if (!currentWord || submitting) return
    setSubmitting(true)
    try {
      await api.post('/wordbank/drill/result', { word: currentWord.word, quality })
      setCompletedCount(c => c + 1)
      setIndex(i => i + 1)
      setRevealed(false)
    } catch {
      setLoadError('Could not save that answer. Your progress on this word was not recorded.')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Loading ──
  if (words === null && !loadError) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 py-20 text-center">
          <span
            className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200
                       border-t-blue-600 dark:border-gray-700 dark:border-t-blue-400"
            role="status"
            aria-label="Loading"
          />
          <p className="text-lg text-gray-600 dark:text-gray-300">Loading your words to review…</p>
        </div>
      </main>
    )
  }

  // ── Error ──
  if (loadError && !words?.length) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 rounded-2xl
                         border border-amber-200 bg-amber-50 px-6 py-10 text-center
                         dark:border-amber-900 dark:bg-amber-950/30">
          <span className="text-3xl" aria-hidden="true">⚠️</span>
          <p className="text-lg font-semibold text-gray-950 dark:text-white">
            We couldn&apos;t load your review words
          </p>
          <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">{loadError}</p>
        </div>
      </main>
    )
  }

  // ── Nothing due today ──
  if (words && words.length === 0) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 rounded-2xl
                         bg-white px-6 py-16 text-center shadow-sm dark:bg-[#2A2A2A]">
          <span className="text-4xl" aria-hidden="true">✨</span>
          <h1 className="text-2xl font-bold text-gray-950 dark:text-white">
            You&apos;re all caught up
          </h1>
          <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">
            No words are due for review today. Keep reading — new words are added here as you go.
          </p>
          <a
            href="/reading"
            className="mt-2 rounded-2xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white
                       hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                       focus-visible:outline-blue-500"
          >
            Go read something
          </a>
        </div>
      </main>
    )
  }

  // ── Session complete ──
  if (isFinished) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 rounded-2xl
                         bg-white px-6 py-16 text-center shadow-sm dark:bg-[#2A2A2A]">
          <span className="text-4xl" aria-hidden="true">🎉</span>
          <h1 className="text-2xl font-bold text-gray-950 dark:text-white">
            Nice work!
          </h1>
          <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">
            You reviewed {completedCount} word{completedCount === 1 ? '' : 's'}. Come back tomorrow for more.
          </p>
          <a
            href="/"
            className="mt-2 rounded-2xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white
                       hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                       focus-visible:outline-blue-500"
          >
            Back to home
          </a>
        </div>
      </main>
    )
  }

  // ── Active drill card ──
  return (
    <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
      <div className="mx-auto max-w-2xl">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">
            Word review
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {index + 1} of {words.length}
          </p>
        </div>

        {/* Progress bar */}
        <div className="mb-6 h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${(index / words.length) * 100}%` }}
          />
        </div>

        <div className="rounded-2xl bg-white p-10 text-center shadow-sm dark:bg-[#2A2A2A]">
          <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">
            Do you remember what this word means?
          </p>

          <button
            type="button"
            onClick={() => { playWord(currentWord.word); setRevealed(true) }}
            className="mx-auto flex flex-col items-center gap-3 rounded-2xl px-6 py-4
                       focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          >
            <span className="text-4xl font-bold tracking-tight text-gray-950 dark:text-white">
              {currentWord.word}
            </span>
            <span className="flex items-center gap-1 text-sm font-medium text-blue-600 dark:text-blue-300">
              🔊 Tap to hear it
            </span>
          </button>

          {!revealed ? (
            <button
              type="button"
              onClick={() => setRevealed(true)}
              className="mt-8 rounded-2xl bg-blue-600 px-6 py-3 text-base font-semibold text-white
                         hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                         focus-visible:outline-blue-500"
            >
              Show my answer
            </button>
          ) : (
            <div className="mt-8">
              <p className="mb-4 text-sm text-gray-600 dark:text-gray-300">
                How well did you know it?
              </p>
              <div className="grid grid-cols-2 gap-3">
                {RATINGS.map(r => (
                  <button
                    key={r.quality}
                    type="button"
                    disabled={submitting}
                    onClick={() => handleRate(r.quality)}
                    className={`rounded-2xl px-4 py-3 text-sm font-semibold transition-colors
                                disabled:cursor-not-allowed disabled:opacity-50 ${r.color}`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {loadError && (
          <p className="mt-4 text-center text-sm text-amber-700 dark:text-amber-300">{loadError}</p>
        )}
      </div>
    </main>
  )
}
