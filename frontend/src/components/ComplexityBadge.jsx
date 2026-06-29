const LEVEL_COLORS = {
  'Easy':      'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-200',
  'Moderate':  'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-200',
  'Hard':      'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-200',
  'Very Hard': 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-200',
}

/**
 * CHANGE #8: Descriptive stat labels instead of bare numbers
 * CHANGE #9: Estimated reading time clearly shown
 */
export default function ComplexityBadge({ complexity }) {
  if (!complexity) return null

  const color = LEVEL_COLORS[complexity.level_label] || 'bg-gray-100 text-gray-700'
  const mins  = Math.ceil(complexity.est_reading_time_s / 60)

  const stats = [
    {
      label: 'Hard words',
      value: `${complexity.hard_word_pct}%`,
      description: 'of words may be challenging',
    },
    {
      label: 'Estimated time',
      value: mins === 1 ? '~1 minute' : `~${mins} minutes`,
      description: 'to read at a comfortable pace',
    },
    {
      label: 'Word count',
      value: complexity.word_count.toLocaleString(),
      description: 'total words in this text',
    },
  ]

  return (
    <div
      className="surface flex flex-col gap-4 rounded-xl border border-gray-200 bg-white
                  p-4 shadow-sm dark:border-gray-700"
      role="status"
      aria-label={`Text difficulty: ${complexity.level_label}`}
    >
      {/* ── CHANGE #8: Clear "Reading Difficulty" header ── */}
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
          Reading difficulty
        </p>
        <span className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${color}`}>
          {complexity.level_label}
        </span>
      </div>

      {/* ── CHANGE #8 + #9: Descriptive stat rows ── */}
      <div className="space-y-2.5">
        {stats.map(stat => (
          <div key={stat.label} className="flex items-baseline justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-300">
                {stat.label}
              </p>
              <p className="text-[10px] text-gray-400 dark:text-gray-500">
                {stat.description}
              </p>
            </div>
            <p className="shrink-0 text-sm font-bold tabular-nums text-gray-800 dark:text-gray-100">
              {stat.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}