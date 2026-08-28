import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

// ── Design tokens shared with the rest of the app ──
// Soft amber/blue, never harsh red — matches the same choice already
// made for hard-word highlighting on the Reading page.
const COLORS = {
  wpm: '#2563eb',       // blue-600, matches primary CTA colour
  errorRate: '#F59E0B', // amber-500 — mirrors --leximind-highlight-hard
  difficult: '#FBBF24', // same amber used for hard-word tokens
  grid: '#E5E7EB',
}

const CHART_TICK = { fontSize: 14, fill: '#4B5563' }

// F41: click a difficult-word bar to hear it read aloud.
// Reuses M1's existing POST /tts/word — no second TTS integration.
function playWord(word) {
  api.post('/tts/word', { word }).catch(err => console.error('Could not play word:', err))
}

/* ── Big-number summary card, matches HomePage's benefit-card style ── */
function StatCard({ icon, label, value }) {
  return (
    <div
      className="flex items-center gap-4 rounded-2xl border border-gray-100 bg-white p-5
                 shadow-sm dark:border-gray-700 dark:bg-[#2A2A2A]"
    >
      <span
        className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-blue-50
                   text-2xl dark:bg-blue-950/40"
        aria-hidden="true"
      >
        {icon}
      </span>
      <div>
        <p className="text-2xl font-bold tracking-tight text-gray-950 dark:text-white">
          {value}
        </p>
        <p className="text-sm text-gray-600 dark:text-gray-300">{label}</p>
      </div>
    </div>
  )
}

/* ── Section wrapper: consistent card, heading, and icon for every chart ── */
function Section({ icon, title, subtitle, children }) {
  return (
    <section
      className="mt-6 rounded-2xl border border-gray-100 bg-white p-6 shadow-sm
                 dark:border-gray-700 dark:bg-[#2A2A2A]"
      aria-labelledby={`${title.replace(/\s+/g, '-').toLowerCase()}-heading`}
    >
      <div className="mb-4 flex items-start gap-3">
        <span className="text-2xl" aria-hidden="true">{icon}</span>
        <div>
          <h2
            id={`${title.replace(/\s+/g, '-').toLowerCase()}-heading`}
            className="text-lg font-bold text-gray-950 dark:text-white"
          >
            {title}
          </h2>
          {subtitle && (
            <p className="text-sm text-gray-600 dark:text-gray-300">{subtitle}</p>
          )}
        </div>
      </div>
      {children}
    </section>
  )
}

/* ── Friendly empty state: an invitation to act, not a bare error line ── */
function EmptyState({ icon, message, actionLabel, actionTo }) {
  return (
    <div
      className="flex flex-col items-center gap-3 rounded-2xl bg-gray-50 px-6 py-10
                 text-center dark:bg-[#333]"
    >
      <span className="text-3xl" aria-hidden="true">{icon}</span>
      <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">{message}</p>
      {actionLabel && actionTo && (
        <a
          href={actionTo}
          className="mt-1 rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white
                     hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2
                     focus-visible:outline-blue-500"
        >
          {actionLabel}
        </a>
      )}
    </div>
  )
}

/* ── Tooltip cards styled to match the rest of the app, not Recharts defaults ── */
function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-xl border border-gray-100 bg-white px-4 py-3 shadow-lg
                 dark:border-gray-700 dark:bg-[#2A2A2A]"
    >
      <p className="text-sm font-semibold text-gray-950 dark:text-white">{label}</p>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        {formatter ? formatter(payload[0].value) : payload[0].value}
      </p>
    </div>
  )
}

export default function AnalyticsPage() {
  const { isAuthenticated } = useAuth()

  const [summary, setSummary] = useState(null)
  const [reading, setReading] = useState([])
  const [writing, setWriting] = useState([])
  const [difficultWords, setDifficultWords] = useState([])

  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

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

  // Charts read oldest -> newest left to right; API returns newest-first.
  const readingChartData = [...reading].reverse().map(s => ({
    date: s.date ? s.date.slice(0, 10) : '',
    wpm: s.wpm,
  }))

  const writingChartData = [...writing].reverse().map(s => ({
    date: s.date ? s.date.slice(0, 10) : '',
    errorRate: s.error_rate ?? 0,
  }))

  const difficultWordsChartData = [...difficultWords].reverse() // biggest bar at top

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 py-20 text-center">
          <span
            className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200
                       border-t-blue-600 dark:border-gray-700 dark:border-t-blue-400"
            role="status"
            aria-label="Loading"
          />
          <p className="text-lg text-gray-600 dark:text-gray-300">Loading your analytics…</p>
        </div>
      </main>
    )
  }

  if (loadError) {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
        <div
          className="mx-auto flex max-w-4xl flex-col items-center gap-3 rounded-2xl
                     border border-amber-200 bg-amber-50 px-6 py-10 text-center
                     dark:border-amber-900 dark:bg-amber-950/30"
        >
          <span className="text-3xl" aria-hidden="true">⚠️</span>
          <p className="text-lg font-semibold text-gray-950 dark:text-white">
            We couldn&apos;t load your analytics
          </p>
          <p className="max-w-sm text-base text-gray-600 dark:text-gray-300">
            {loadError} Try reloading the page — if it keeps happening, log out and back in.
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-12 dark:bg-[#1E1E1E] sm:px-6">
      <div className="mx-auto max-w-4xl">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">
          Your progress
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-950 dark:text-white">
          Analytics
        </h1>
        <p className="mt-2 text-base text-gray-600 dark:text-gray-300">
          A simple look at how your reading and writing are going.
        </p>

        {/* ── Summary cards — GET /analytics/summary ── */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon="📚" label="Reading sessions" value={summary?.total_sessions ?? 0} />
          <StatCard icon="🔤" label="Words read" value={summary?.total_words ?? 0} />
          <StatCard icon="⚡" label="Average speed (wpm)" value={summary?.avg_wpm ?? 0} />
          <StatCard icon="🏆" label="Best speed (wpm)" value={summary?.best_wpm ?? 0} />
        </div>

        {/* F39: WPM trend */}
        <Section
          icon="📈"
          title="Reading speed over time"
          subtitle="How fast you're reading, session by session."
        >
          {readingChartData.length === 0 ? (
            <EmptyState
              icon="📖"
              message="No reading sessions yet. Read something to see your speed here."
              actionLabel="Start reading"
              actionTo="/reading"
            />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={readingChartData} margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
                <XAxis dataKey="date" tick={CHART_TICK} />
                <YAxis tick={CHART_TICK} width={40} />
                <Tooltip content={<ChartTooltip formatter={(v) => `${v} words per minute`} />} />
                <Line
                  type="monotone"
                  dataKey="wpm"
                  stroke={COLORS.wpm}
                  strokeWidth={3}
                  dot={{ r: 5, fill: COLORS.wpm }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Section>

        {/* F40: Writing error-rate chart */}
        <Section
          icon="✍️"
          title="Writing accuracy over time"
          subtitle="Errors per 100 words — lower means fewer mistakes."
        >
          {writingChartData.length === 0 ? (
            <EmptyState
              icon="📝"
              message="No writing sessions yet. Write something to see your progress here."
              actionLabel="Start writing"
              actionTo="/writing"
            />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={writingChartData} margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
                <XAxis dataKey="date" tick={CHART_TICK} />
                <YAxis tick={CHART_TICK} width={40} />
                <Tooltip content={<ChartTooltip formatter={(v) => `${v} errors per 100 words`} />} />
                <Bar dataKey="errorRate" fill={COLORS.errorRate} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Section>

        {/* F41: Difficult words — click a bar to hear it read aloud via M1's /tts/word */}
        <Section
          icon="🔎"
          title="Your most challenging words"
          subtitle="Tap a bar to hear the word read aloud."
        >
          {difficultWordsChartData.length === 0 ? (
            <EmptyState
              icon="✨"
              message="No challenging words yet. They'll show up here as you read."
            />
          ) : (
            <ResponsiveContainer
              width="100%"
              height={Math.max(200, difficultWordsChartData.length * 48)}
            >
              <BarChart
                data={difficultWordsChartData}
                layout="vertical"
                margin={{ left: 8, right: 24 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
                <XAxis type="number" allowDecimals={false} tick={CHART_TICK} />
                <YAxis type="category" dataKey="word" width={130} tick={CHART_TICK} />
                <Tooltip content={<ChartTooltip formatter={(v) => `Seen ${v} time${v === 1 ? '' : 's'}`} />} />
                <Bar
                  dataKey="repeat_count"
                  fill={COLORS.difficult}
                  radius={[0, 8, 8, 0]}
                  cursor="pointer"
                  onClick={(data) => playWord(data.word)}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Section>

        {/* Word Bank stats card (F51) intentionally omitted here —
            depends on GET /wordbank/stats, which is Phase 6 work and
            does not exist yet. Disclosed deviation from Task 5.8's
            full spec, per Pragathi's sign-off. Add as a small additive
            card once Phase 6 lands. */}
      </div>
    </main>
  )
}
