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

// Fetches one syllable's audio and returns a ready-to-play blob URL,
// without playing it yet. Called for every syllable in parallel up
// front, so there's zero network wait once playback actually starts.
async function fetchClipUrl(text) {
  const data = await api.post('/tts/word', { word: text, voice: 'en-GB-SoniaNeural' })
  const binary = atob(data.audio_b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  const blob = new Blob([bytes], { type: 'audio/mpeg' })
  return URL.createObjectURL(blob)
}

// Plays an already-prepared blob URL, resolving once it finishes.
function playClipUrl(url) {
  return new Promise((resolve, reject) => {
    const audio = new Audio()
    audio.src = url
    audio.onended = resolve
    audio.onerror = () => reject(new Error('Audio playback failed'))
    audio.play().catch(reject)
  })
}

export default function WordBankDrillPage() {
  const { isAuthenticated } = useAuth()

  const [words, setWords] = useState(null) // null = not loaded yet
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [completedCount, setCompletedCount] = useState(0)

  const [syllables, setSyllables] = useState(null) // null while loading for the current word
  const [clipUrls, setClipUrls] = useState(null) // prefetched audio blob URLs, same order as syllables
  const [playingIndex, setPlayingIndex] = useState(-1) // -1 = nothing playing
  const isPlaying = playingIndex !== -1

  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false

    api.get('/wordbank/drill')
      .then(data => { if (!cancelled) setWords(data) })
      .catch(() => { if (!cancelled) setLoadError('Could not load your drill words right now.') })

    return () => { cancelled = true }
  }, [isAuthenticated])

  const currentWord = words?.[index]

  // Fetch the syllable breakdown fresh each time the active word changes.
  useEffect(() => {
    if (!currentWord) return
    let cancelled = false

    api.get(`/wordbank/syllables?word=${encodeURIComponent(currentWord.word)}`)
      .then(data => { if (!cancelled) setSyllables(data.syllables) })
      .catch(() => { if (!cancelled) setSyllables([currentWord.word]) }) // fall back to whole word

    return () => { cancelled = true; setSyllables(null) }
  }, [currentWord])

  // As soon as syllables arrive, prefetch every clip in parallel so
  // there's no per-syllable network wait once the user hits play.
  useEffect(() => {
    if (!syllables?.length) return
    let cancelled = false

    Promise.all(syllables.map(fetchClipUrl))
      .then(urls => { if (!cancelled) setClipUrls(urls) })
      .catch(() => { if (!cancelled) setClipUrls(null) })

    return () => { cancelled = true; setClipUrls(null) }
  }, [syllables])

  // Plays each pre-fetched clip in order, highlighting the active
  // syllable. Guarded by isPlaying so a rapid double-click can't
  // overlap two playback sequences at once.
  async function handleSpeakerClick() {
    if (isPlaying || !clipUrls?.length) return
    for (let i = 0; i < clipUrls.length; i++) {
      setPlayingIndex(i)
      try {
        await playClipUrl(clipUrls[i])
      } catch {
        break
      }
    }
    setPlayingIndex(-1)
  }

  const isFinished = words && index >= words.length

  async function handleRate(quality) {
    if (!currentWord || submitting) return
    setSubmitting(true)
    try {
      await api.post('/wordbank/drill/result', { word: currentWord.word, quality })
      setCompletedCount(c => c + 1)
      setIndex(i => i + 1)
      setRevealed(false)
      setPlayingIndex(-1)
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

          {/* Word broken into syllables, highlighted one at a time as
              its audio plays. Not itself clickable — the speaker icon
              below is the only way to trigger playback, so a click
              on the word never accidentally starts (or restarts)
              audio. */}
          <div className="mb-3 flex flex-wrap items-center justify-center gap-1">
            {(syllables ?? [currentWord.word]).map((syl, i) => (
              <span
                key={`${currentWord.word}-${i}`}
                className={`text-4xl font-bold tracking-tight transition-colors duration-150
                  ${playingIndex === i
                    ? 'rounded-lg bg-amber-200 text-gray-950 dark:bg-amber-500/40 dark:text-white'
                    : 'text-gray-950 dark:text-white'}`}
              >
                {syl}
              </span>
            ))}
          </div>

          <button
            type="button"
            onClick={handleSpeakerClick}
            disabled={isPlaying || !clipUrls}
            aria-label={isPlaying ? 'Playing sound' : 'Hear this word, syllable by syllable'}
            className="mx-auto flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-medium
                       text-blue-600 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60
                       dark:text-blue-300 dark:hover:bg-blue-950/30
                       focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          >
            <span aria-hidden="true">{isPlaying ? '🔈' : '🔊'}</span>
            {isPlaying ? 'Playing…' : 'Tap to hear it, syllable by syllable'}
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
