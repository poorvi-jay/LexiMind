import { useEffect, useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

const READING_COLOR = '#2563eb'

/* ── Count-up hook: numbers arrive by counting from 0, once, on load ── */
function useCountUp(target, durationMs = 700) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const effectiveDuration = prefersReduced ? 0 : durationMs

    let start
    let frame
    function tick(ts) {
      if (start === undefined) start = ts
      const progress = effectiveDuration === 0 ? 1 : Math.min((ts - start) / effectiveDuration, 1)
      setValue(Math.round(progress * (target || 0)))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs])
  return value
}

/* ── Card wrapper: same rounded/shadow language throughout the app ── */
function Card({ icon, title, children, className = '' }) {
  return (
    <section className={`rounded-2xl border border-gray-100 bg-white p-6 shadow-sm
                          dark:border-gray-700 dark:bg-[#2A2A2A] ${className}`}>
      {title && (
        <div className="mb-4 flex items-center gap-3">
          <span className="text-2xl" aria-hidden="true">{icon}</span>
          <h2 className="text-lg font-bold text-gray-950 dark:text-white">{title}</h2>
        </div>
      )}
      {children}
    </section>
  )
}

/* ── Friendly empty state: an invitation to act, not a bare error line ── */
function EmptyState({ icon, message, actionLabel, actionTo }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl bg-gray-50 px-6 py-16
                     text-center dark:bg-[#333]">
      <span className="text-4xl" aria-hidden="true">{icon}</span>
      <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">{message}</p>
      {actionLabel && actionTo && (
        <a
          href={actionTo}
          className="mt-1 rounded-2xl bg-blue-600 px-5 py-2.5 text-base font-semibold text-white
                     hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                     focus-visible:outline-blue-500"
        >
          {actionLabel}
        </a>
      )}
    </div>
  )
}

/* ── A single stat tile for the side rail ── */
function StatTile({ icon, label, value }) {
  return (
    <div className="rounded-2xl bg-gray-50 px-5 py-4 text-center dark:bg-[#333]">
      <span className="text-2xl" aria-hidden="true">{icon}</span>
      <p className="mt-1 text-2xl font-bold text-gray-950 dark:text-white">{value}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  )
}

/* ── Two big plain bars, side by side: "Last time" vs "Today".
     No axis, no gridlines, no dates — just two numbers to compare. ── */
function CompareBars({ beforeLabel, beforeValue, nowLabel, nowValue, unit, color }) {
  const max = Math.max(beforeValue, nowValue, 1)
  const beforeHeight = Math.max(12, (beforeValue / max) * 100)
  const nowHeight = Math.max(12, (nowValue / max) * 100)

  return (
    <div className="flex items-end justify-center gap-10 px-4 py-6">
      <div className="flex flex-col items-center gap-2">
        <div className="flex h-40 w-20 items-end">
          <div
            className="w-full rounded-t-xl bg-gray-300 dark:bg-gray-600"
            style={{ height: `${beforeHeight}%` }}
          />
        </div>
        <p className="text-xl font-bold text-gray-700 dark:text-gray-200">{beforeValue}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{beforeLabel}</p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <div className="flex h-40 w-20 items-end">
          <div
            className="w-full rounded-t-xl"
            style={{ height: `${nowHeight}%`, backgroundColor: color }}
          />
        </div>
        <p className="text-xl font-bold text-gray-950 dark:text-white">
          {nowValue} <span className="text-sm font-normal text-gray-500 dark:text-gray-400">{unit}</span>
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{nowLabel}</p>
      </div>
    </div>
  )
}

/* ── Plain-language verdict, no percentages, no jargon ── */
function PlainVerdict({ direction, goodText, sameText, firstText, badText }) {
  if (direction === 'first') {
    return <p className="text-center text-lg font-medium text-blue-700 dark:text-blue-300">✨ {firstText}</p>
  }
  if (direction === 'up') {
    return <p className="text-center text-lg font-medium text-emerald-700 dark:text-emerald-300">✅ {goodText}</p>
  }
  if (direction === 'down') {
    return <p className="text-center text-lg font-medium text-amber-700 dark:text-amber-300">💪 {badText}</p>
  }
  return <p className="text-center text-lg font-medium text-gray-600 dark:text-gray-300">{sameText}</p>
}

function computeDirection(prev, latest, higherIsBetter) {
  if (prev == null) return 'first'
  if (prev === latest) return 'same'
  const improved = higherIsBetter ? latest > prev : latest < prev
  return improved ? 'up' : 'down'
}

/* ── Consecutive-day streak from combined reading + writing session dates ── */
function computeStreak(readingSessions, writingSessions) {
  const days = new Set()
  for (const s of [...readingSessions, ...writingSessions]) {
    if (s.date) days.add(s.date.slice(0, 10))
  }
  if (days.size === 0) return 0

  const sorted = [...days].sort().reverse()
  let streak = 1
  let cursor = new Date(sorted[0])

  for (let i = 1; i < sorted.length; i++) {
    const prevDay = new Date(cursor)
    prevDay.setDate(prevDay.getDate() - 1)
    const expected = prevDay.toISOString().slice(0, 10)
    if (sorted[i] === expected) {
      streak += 1
      cursor = prevDay
    } else {
      break
    }
  }
  return streak
}

/* ── "Your biggest win": picks the single most meaningful improvement
     to date, rather than showing every metric. Returns null when
     there isn't enough data for a genuine insight — never fabricates
     one just to fill the space (per brief section 16/30). ── */
function computeBiggestWin(reading, writing, difficultWords) {
  if (reading.length >= 2) {
    const first = reading[reading.length - 1].wpm
    const best = Math.max(...reading.map(r => r.wpm))
    const gain = best - first
    if (gain > 0) {
      return `You improved your reading speed by ${gain} words per minute since you started.`
    }
  }
  if (writing.length >= 2) {
    const totals = writing.map(w => (w.spell_error_count ?? 0) + (w.grammar_error_count ?? 0) + (w.homophone_flag_count ?? 0))
    const first = totals[totals.length - 1]
    const fewest = Math.min(...totals)
    const drop = first - fewest
    if (drop > 0) {
      return `You've cut your writing mistakes from ${first} down to ${fewest}.`
    }
  }
  if (difficultWords.length >= 3) {
    return `You've been practicing ${difficultWords.length} tricky words — every one is a step forward.`
  }
  return null
}

/* ── "Progress Coach": one short, human observation drawn from real
     data, not a generic motivational line. Kept to 1-2 sentences per
     brief section 17 — this is a nudge, not a report. ── */
function computeCoachText(readingDirection, writingDirection) {
  if (readingDirection === 'up' && writingDirection === 'up') {
    return "You're doing especially well with reading speed, and your writing mistakes have gone down too."
  }
  if (readingDirection === 'up') {
    return "You're doing especially well with reading speed lately."
  }
  if (writingDirection === 'up') {
    return "Your writing accuracy has been improving — keep it up."
  }
  return 'A little practice today goes a long way.'
}

function playWord(word) {
  api.post('/tts/word', { word }).catch(err => console.error('Could not play word:', err))
}

const TABS = [
  { id: 'reading', label: 'Reading', icon: '📖' },
  { id: 'writing', label: 'Writing', icon: '✍️' },
  { id: 'words', label: 'Words', icon: '🔎' },
]

export default function AnalyticsPage() {
  const { isAuthenticated, user } = useAuth()

  const [summary, setSummary] = useState(null)
  const [reading, setReading] = useState([])
  const [writing, setWriting] = useState([])
  const [difficultWords, setDifficultWords] = useState([])

  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [activeTab, setActiveTab] = useState('reading')

  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false

    async function loadAnalytics() {
      setIsLoading(true)
      setLoadError(null)
      try {
        const [summaryData, readingData, writingData, difficultData] = await Promise.all([
          api.get('/analytics/summary'),
          api.get('/analytics/reading'),
          api.get('/analytics/writing'),
          api.get('/analytics/difficult-words'),
        ])
        if (cancelled) return
        setSummary(summaryData)
        setReading(readingData)
        setWriting(writingData)
        setDifficultWords(difficultData)
      } catch {
        if (!cancelled) setLoadError('Could not load analytics right now.')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    loadAnalytics()
    return () => { cancelled = true }
  }, [isAuthenticated])

  const readingChartData = useMemo(
    () => [...reading].reverse().map(s => ({ date: s.date ? s.date.slice(0, 10) : '', wpm: s.wpm })),
    [reading]
  )

  const readingDirection = useMemo(() => {
    if (reading.length < 2) return reading.length === 1 ? 'first' : 'none'
    return computeDirection(reading[1].wpm, reading[0].wpm, true)
  }, [reading])

  const writingDirection = useMemo(() => {
    if (writing.length < 2) return writing.length === 1 ? 'first' : 'none'
    return computeDirection(writing[1].error_rate ?? 0, writing[0].error_rate ?? 0, false)
  }, [writing])

  const streak = useMemo(() => computeStreak(reading, writing), [reading, writing])

  const overallMood = useMemo(() => {
    if (readingDirection === 'up' || writingDirection === 'up') {
      return { icon: '🌟', text: "You're doing great! Keep it up." }
    }
    if (!summary?.total_sessions) {
      return { icon: '👋', text: 'Read or write something to get started.' }
    }
    return { icon: '💪', text: 'Keep practicing — you can do this!' }
  }, [readingDirection, writingDirection, summary])

  const biggestWin = useMemo(
    () => computeBiggestWin(reading, writing, difficultWords),
    [reading, writing, difficultWords]
  )
  const coachText = useMemo(
    () => computeCoachText(readingDirection, writingDirection),
    [readingDirection, writingDirection]
  )
  const [simpleView, setSimpleView] = useState(false)

  const totalSessionsAnim = useCountUp(summary?.total_sessions ?? 0)
  const totalWordsAnim = useCountUp(summary?.total_words ?? 0)
  const bestWpmAnim = useCountUp(summary?.best_wpm ?? 0)
  const avgWpmAnim = useCountUp(summary?.avg_wpm ?? 0)

  const totalWritingSessions = writing.length
  const avgMistakes = useMemo(() => {
    if (writing.length === 0) return 0
    const totals = writing.map(w => (w.spell_error_count ?? 0) + (w.grammar_error_count ?? 0) + (w.homophone_flag_count ?? 0))
    return Math.round((totals.reduce((a, b) => a + b, 0) / totals.length) * 10) / 10
  }, [writing])
  const bestMistakes = useMemo(() => {
    if (writing.length === 0) return 0
    return Math.min(...writing.map(w => (w.spell_error_count ?? 0) + (w.grammar_error_count ?? 0) + (w.homophone_flag_count ?? 0)))
  }, [writing])

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 py-20 text-center">
          <span
            className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200
                       border-t-blue-600 dark:border-gray-700 dark:border-t-blue-400"
            role="status"
            aria-label="Loading"
          />
          <p className="text-lg text-gray-600 dark:text-gray-300">Getting your progress ready…</p>
        </div>
      </main>
    )
  }

  if (loadError) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 rounded-2xl
                         border border-amber-200 bg-amber-50 px-6 py-10 text-center
                         dark:border-amber-900 dark:bg-amber-950/30">
          <span className="text-3xl" aria-hidden="true">⚠️</span>
          <p className="text-lg font-semibold text-gray-950 dark:text-white">
            We couldn&apos;t load your progress
          </p>
          <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">
            {loadError} Try again in a moment.
          </p>
        </div>
      </main>
    )
  }

  const firstName = user?.name?.split(' ')[0] || 'there'

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-8 dark:bg-[#1E1E1E] sm:px-8">
      <div className="mx-auto max-w-6xl">

        {/* ── Greeting + mood, full width ── */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-950 dark:text-white">
              Hi {firstName}! 👋
            </h1>
            <p className="mt-1 text-lg text-gray-600 dark:text-gray-300">Here&apos;s how you&apos;re doing.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <p className="flex items-center gap-2 rounded-2xl bg-blue-50 px-5 py-3 text-base font-medium
                          text-blue-900 dark:bg-blue-950/30 dark:text-blue-100">
              <span aria-hidden="true">{overallMood.icon}</span> {overallMood.text}
            </p>
            {streak > 0 && (
              <p className="flex items-center gap-2 rounded-2xl bg-white px-5 py-3 text-base font-semibold
                            text-gray-800 shadow-sm dark:bg-[#2A2A2A] dark:text-gray-100">
                🔥 {streak} day{streak === 1 ? '' : 's'} in a row
              </p>
            )}
            <button
              type="button"
              onClick={() => setSimpleView(v => !v)}
              aria-pressed={simpleView}
              className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm font-semibold
                         text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-[#2A2A2A]
                         dark:text-gray-300 dark:hover:bg-gray-700
                         focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
            >
              {simpleView ? '📋 Show more' : '🌿 Simple view'}
            </button>
          </div>
        </div>

        {simpleView ? (
          <div className="mt-6 rounded-2xl bg-white p-8 text-center shadow-sm dark:bg-[#2A2A2A]">
            <p className="text-2xl font-medium text-gray-950 dark:text-white">
              {overallMood.icon} {overallMood.text}
            </p>
            {summary?.best_wpm > 0 && (
              <p className="mt-4 text-xl text-gray-700 dark:text-gray-200">
                Your reading speed is <span className="font-bold">{summary.best_wpm} words per minute</span>.
              </p>
            )}
            {readingDirection === 'up' && (
              <p className="mt-2 text-xl text-gray-700 dark:text-gray-200">That&apos;s faster than last time!</p>
            )}
            {difficultWords.length > 0 && (
              <a
                href="/wordbank/drill"
                className="mt-6 inline-block rounded-2xl bg-blue-600 px-6 py-3 text-lg font-semibold text-white
                           hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                           focus-visible:outline-blue-500"
              >
                Practice tricky words
              </a>
            )}
          </div>
        ) : (
        <>

        {/* ── Segmented toggle: Reading / Writing / Words ── */}
        <div
          role="tablist"
          aria-label="Choose what to view"
          className="mt-6 inline-flex rounded-2xl bg-white p-1.5 shadow-sm dark:bg-[#2A2A2A]"
        >
          {TABS.map(tab => (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 rounded-xl px-6 py-3 text-base font-semibold transition-colors
                ${activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}`}
            >
              <span aria-hidden="true">{tab.icon}</span> {tab.label}
            </button>
          ))}
        </div>

        {/* ── Reading tab: hero chart + full stat rail, uses the full width ── */}
        {activeTab === 'reading' && (
          <div className="mt-6 grid gap-4 lg:grid-cols-[2fr_1fr]">
            <Card icon="📖" title="Your reading speed">
              {readingChartData.length === 0 ? (
                <EmptyState
                  icon="📖"
                  message="Read something to see your speed here."
                  actionLabel="Start reading"
                  actionTo="/reading"
                />
              ) : (
                <>
                  <div className="mb-4 text-center">
                    <span className="text-5xl font-bold tracking-tight text-gray-950 dark:text-white">
                      {bestWpmAnim}
                    </span>
                    <span className="ml-2 text-lg text-gray-500 dark:text-gray-400">
                      words per minute, your best
                    </span>
                  </div>
                  <p className="sr-only">
                    Your reading speed chart. Current best speed is {summary?.best_wpm ?? 0} words per
                    minute. {readingDirection === 'up' ? 'Your speed has improved since your last session.' :
                      readingDirection === 'down' ? 'Your speed has changed since your last session.' :
                      'Read more sessions to see how your speed changes over time.'}
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={readingChartData} margin={{ top: 8, left: 0, right: 8, bottom: 0 }}>
                      <XAxis dataKey="date" tick={{ fontSize: 13, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                      <YAxis hide domain={['dataMin - 10', 'dataMax + 10']} />
                      <Tooltip
                        formatter={(value) => [`${value} words per minute`, '']}
                        labelFormatter={() => ''}
                        contentStyle={{ borderRadius: 12, border: '1px solid #E5E7EB', fontSize: 14 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="wpm"
                        stroke={READING_COLOR}
                        strokeWidth={4}
                        dot={{ r: 6, fill: READING_COLOR, strokeWidth: 0 }}
                        activeDot={{ r: 8 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="mt-4">
                    <PlainVerdict
                      direction={readingDirection}
                      firstText="Great start! Keep reading to see your progress here."
                      goodText="You're reading faster than last time!"
                      sameText="You're reading at the same speed as last time."
                      badText="Keep practicing — reading gets easier with time."
                    />
                  </div>
                </>
              )}
            </Card>

            <div className="grid grid-cols-2 gap-4 content-start lg:grid-cols-1">
              <StatTile icon="📚" label="Reading sessions" value={totalSessionsAnim} />
              <StatTile icon="🔤" label="Words read" value={totalWordsAnim} />
              <StatTile icon="⚡" label="Average speed" value={`${avgWpmAnim} wpm`} />
              <StatTile icon="🏆" label="Best speed" value={`${bestWpmAnim} wpm`} />
            </div>
          </div>
        )}

        {/* ── Writing tab: comparison + full stat rail, uses the full width ── */}
        {activeTab === 'writing' && (
          <div className="mt-6 grid gap-4 lg:grid-cols-[2fr_1fr]">
            <Card icon="✍️" title="How well you write">
              {writing.length === 0 ? (
                <EmptyState
                  icon="✍️"
                  message="Write something to see your progress here."
                  actionLabel="Start writing"
                  actionTo="/writing"
                />
              ) : writing.length === 1 ? (
                <div className="py-8">
                  <p className="text-center text-xl text-gray-700 dark:text-gray-200">
                    You made <span className="font-bold">
                      {(writing[0].spell_error_count ?? 0) + (writing[0].grammar_error_count ?? 0) + (writing[0].homophone_flag_count ?? 0)}
                    </span> mistake(s) in your last writing.
                  </p>
                  <div className="mt-4">
                    <PlainVerdict direction="first" firstText="Great start! Keep writing to see your progress here." />
                  </div>
                </div>
              ) : (
                <>
                  <CompareBars
                    beforeLabel="Last time"
                    beforeValue={(writing[1].spell_error_count ?? 0) + (writing[1].grammar_error_count ?? 0) + (writing[1].homophone_flag_count ?? 0)}
                    nowLabel="Today"
                    nowValue={(writing[0].spell_error_count ?? 0) + (writing[0].grammar_error_count ?? 0) + (writing[0].homophone_flag_count ?? 0)}
                    unit="mistakes"
                    color="#F59E0B"
                  />
                  <div className="mt-2">
                    <PlainVerdict
                      direction={writingDirection}
                      goodText="Great job — fewer mistakes today!"
                      sameText="You made the same number of mistakes as last time."
                      badText="Keep practicing — you'll get there!"
                    />
                  </div>
                </>
              )}
            </Card>

            <div className="grid grid-cols-2 gap-4 content-start lg:grid-cols-1">
              <StatTile icon="✍️" label="Writing sessions" value={totalWritingSessions} />
              <StatTile icon="📊" label="Average mistakes" value={avgMistakes} />
              <StatTile icon="🏆" label="Fewest mistakes" value={bestMistakes} />
            </div>
          </div>
        )}

        {/* ── Words tab: full-width tappable pill grid ── */}
        {activeTab === 'words' && (
          <div className="mt-6">
            <Card icon="🔎" title="Words you're learning">
              {difficultWords.length === 0 ? (
                <EmptyState icon="✨" message="Words you find tricky will show up here as you read." />
              ) : (
                <>
                  <div className="flex flex-wrap gap-3">
                    {difficultWords.map(w => (
                      <button
                        key={w.word}
                        type="button"
                        onClick={() => playWord(w.word)}
                        className="flex items-center gap-2 rounded-2xl bg-amber-50 px-6 py-4 text-xl
                                   font-semibold text-amber-900 hover:bg-amber-100
                                   dark:bg-amber-950/30 dark:text-amber-100 dark:hover:bg-amber-950/50
                                   focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500"
                      >
                        {w.word} <span aria-hidden="true">🔊</span>
                      </button>
                    ))}
                  </div>
                  <p className="mt-6 text-center text-base text-gray-500 dark:text-gray-400">
                    Tap any word to hear it
                  </p>
                </>
              )}
            </Card>
          </div>
        )}

        {/* ── Biggest Win: one dynamically-computed insight, omitted
            entirely when there isn't enough data for a real one ── */}
        {biggestWin && (
          <Card icon="✨" title="Your biggest win" className="mt-4">
            <p className="text-lg text-gray-800 dark:text-gray-100">{biggestWin}</p>
          </Card>
        )}

        {/* ── Progress Coach: a short observation plus a direct link
            into the existing Word Bank drill (Phase 6), connecting
            analytics to something the user can actually go do next ── */}
        <Card icon="🧠" title="Your Progress Coach" className="mt-4">
          <p className="text-lg text-gray-800 dark:text-gray-100">{coachText}</p>
          {difficultWords.length > 0 && (
            <>
              <p className="mt-4 text-sm font-semibold text-gray-500 dark:text-gray-400">Try this next</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {difficultWords.slice(0, 3).map(w => (
                  <button
                    key={w.word}
                    type="button"
                    onClick={() => playWord(w.word)}
                    className="flex items-center gap-2 rounded-2xl bg-amber-50 px-4 py-2 text-base
                               font-semibold text-amber-900 hover:bg-amber-100
                               dark:bg-amber-950/30 dark:text-amber-100 dark:hover:bg-amber-950/50
                               focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500"
                  >
                    <span aria-hidden="true">🔊</span> {w.word}
                  </button>
                ))}
              </div>
              <a
                href="/wordbank/drill"
                className="mt-4 inline-block rounded-2xl bg-blue-600 px-5 py-2.5 text-base font-semibold text-white
                           hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                           focus-visible:outline-blue-500"
              >
                Practice my tricky words →
              </a>
            </>
          )}
        </Card>
        </>
        )}
      </div>
    </main>
  )
}
