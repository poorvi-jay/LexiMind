import { PRESETS } from '../hooks/usePreferences'
import { usePrefs } from '../context/PreferencesContext'

const FONTS = ['Lexend', 'Arial', 'Verdana', 'OpenDyslexic']

const OVERLAYS = [
  { label: 'White', value: '#FFFFFF' },
  { label: 'Cream', value: '#FFF9E6' },
  { label: 'Light Yellow', value: '#FFFACD' },
  { label: 'Light Green', value: '#E8F5E9' },
  { label: 'Light Blue', value: '#E3F2FD' },
  { label: 'Soft Pink', value: '#FCE4EC' },
  { label: 'Light Grey', value: '#F5F5F5' },
]

const HIGHLIGHT_COLORS = [
  { label: 'Gold', value: '#FFD700' },
  { label: 'Green', value: '#90EE90' },
  { label: 'Blue', value: '#87CEEB' },
  { label: 'Pink', value: '#FFB6C1' },
  { label: 'Orange', value: '#FFA500' },
]

/* ═══════════════════════════════════════════════
   ACCESSIBILITY SUMMARY
   ═══════════════════════════════════════════════ */
function AccessibilitySummary({ prefs }) {
  const checks = [
    { ok: prefs.lineSpacing >= 1.8, label: 'Comfortable line spacing' },
    { ok: prefs.fontSize >= 16, label: 'Accessible font size' },
    {
      ok: ['Lexend', 'OpenDyslexic', 'Verdana'].includes(prefs.font),
      label: 'Reader-friendly font',
    },
    { ok: prefs.wordSpacing >= 2, label: 'Adequate word spacing' },
    { ok: prefs.focusRuler, label: 'Focus ruler enabled' },
    { ok: prefs.phrasePauses, label: 'Natural phrase pauses' },
  ]

  return (
    <div
      className="rounded-2xl border border-green-100 bg-green-50 p-5
                  dark:border-green-900 dark:bg-green-950/30"
      role="status"
      aria-label="Accessibility profile summary"
    >
      <h2 className="mb-3 text-sm font-semibold text-green-800 dark:text-green-200">
        Current reading profile
      </h2>
      <ul className="space-y-1.5">
        {checks.map(c => (
          <li
            key={c.label}
            className={`flex items-center gap-2 text-sm ${
              c.ok
                ? 'text-green-700 dark:text-green-300'
                : 'text-gray-400 dark:text-gray-500'
            }`}
          >
            <span aria-hidden="true">{c.ok ? '✓' : '○'}</span>
            {c.label}
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ═══════════════════════════════════════════════
   TOGGLE
   ═══════════════════════════════════════════════ */
function Toggle({ checked, label, description, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-gray-400">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={onChange}
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors
          focus-visible:outline-2 focus-visible:outline-offset-2
          focus-visible:outline-blue-500
          ${checked ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`}
      >
        <span
          className={`absolute left-1 top-1 h-5 w-5 rounded-full bg-white shadow transition-transform
            ${checked ? 'translate-x-5' : 'translate-x-0'}`}
        />
      </button>
    </div>
  )
}

/* ═══════════════════════════════════════════════
   RANGE SETTING
   ═══════════════════════════════════════════════ */
function RangeSetting({ label, value, min, max, step, unit = '', onChange, onStep }) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wide text-gray-500 dark:text-gray-300">
          {label}
        </h2>
        <span
          className="rounded-md bg-blue-50 px-2 py-1 text-sm font-semibold text-blue-700
                      dark:bg-blue-900/40 dark:text-blue-200"
        >
          {value}{unit}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onStep(-1)}
          className="grid h-10 w-10 place-items-center rounded-full border border-gray-200
                      text-lg font-semibold hover:bg-gray-50
                      focus-visible:outline-2 focus-visible:outline-blue-500
                      dark:border-gray-700 dark:hover:bg-gray-800"
          aria-label={`Decrease ${label.toLowerCase()}`}
        >
          −
        </button>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={onChange}
          className="w-full accent-blue-600"
          aria-label={label}
        />
        <button
          type="button"
          onClick={() => onStep(1)}
          className="grid h-10 w-10 place-items-center rounded-full border border-gray-200
                      text-lg font-semibold hover:bg-gray-50
                      focus-visible:outline-2 focus-visible:outline-blue-500
                      dark:border-gray-700 dark:hover:bg-gray-800"
          aria-label={`Increase ${label.toLowerCase()}`}
        >
          +
        </button>
      </div>
      <div className="mt-1 flex justify-between text-xs text-gray-400">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </section>
  )
}

/* ═══════════════════════════════════════════════
   SETTINGS PAGE
   ═══════════════════════════════════════════════ */
export default function SettingsPage() {
  const { prefs, updatePref, applyPreset, resetPrefs } = usePrefs()
  const previewBackground = prefs.darkMode ? '#1E1E1E' : prefs.overlay
  const previewColor = prefs.darkMode ? '#F2F2F2' : '#1F2937'

  function stepPref(key, direction, min, max, step) {
    const next = Math.min(max, Math.max(min, Number((prefs[key] + direction * step).toFixed(2))))
    updatePref(key, next)
  }

  const selectedOverlayLabel =
    OVERLAYS.find(o => o.value === prefs.overlay)?.label || 'Custom'
  const selectedHighlightLabel =
    HIGHLIGHT_COLORS.find(c => c.value === prefs.highlightColor)?.label || 'Custom'

  return (
    <main className="mx-auto min-h-screen max-w-3xl p-6 sm:p-8">
      {/* ── Page header ── */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Reading settings</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-300">
            Adjust the page until reading feels comfortable.
          </p>
        </div>
        <button
          type="button"
          onClick={resetPrefs}
          className="text-sm text-gray-500 underline hover:text-gray-800
                      focus-visible:outline-2 focus-visible:outline-blue-500
                      dark:text-gray-300 dark:hover:text-white"
        >
          Reset to defaults
        </button>
      </div>

      {/* ── Live preview ── */}
      <div
        className="mb-8 rounded-xl border border-gray-200 p-5 shadow-sm dark:border-gray-600"
        style={{
          backgroundColor: previewBackground,
          color: previewColor,
          fontFamily: `'${prefs.font}', Arial, Verdana, sans-serif`,
          fontSize: `${prefs.fontSize}px`,
          lineHeight: prefs.lineSpacing,
          wordSpacing: `${prefs.wordSpacing}px`,
          position: 'relative',
          overflow: 'hidden',
        }}
        aria-label="Live preview of reading settings"
      >
        <p className="mb-2 text-xs text-gray-400">Live preview</p>

        {/* Focus ruler preview */}
        {prefs.focusRuler && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: `${2.2 * prefs.fontSize}px`,
              height: `${prefs.lineSpacing * prefs.fontSize * 1.1}px`,
              background: 'rgba(255, 215, 0, 0.12)',
              pointerEvents: 'none',
              borderRadius: '4px',
            }}
            aria-hidden="true"
          />
        )}

        <p>
          The quick brown fox jumps over the lazy dog. Dyslexia affects 15–20%
          of the global population.
        </p>
        <p className="mt-2 text-sm">
          Current word:{' '}
          <span
            className="rounded px-1"
            style={{ backgroundColor: prefs.highlightColor, color: '#111827' }}
          >
            reading
          </span>
        </p>
      </div>

      {/* ── Reading presets ── */}
      <section className="mb-8" aria-labelledby="presets-heading">
        <h2
          id="presets-heading"
          className="mb-4 text-sm font-medium uppercase tracking-wide text-gray-500 dark:text-gray-300"
        >
          Quick presets
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(PRESETS).map(([key, preset]) => (
            <button
              key={key}
              type="button"
              onClick={() => applyPreset(key)}
              className="flex items-start gap-3 rounded-2xl border border-gray-200 bg-white
                          p-4 text-left shadow-sm transition-colors hover:border-blue-300
                          hover:bg-blue-50
                          focus-visible:outline-2 focus-visible:outline-offset-2
                          focus-visible:outline-blue-500
                          dark:border-gray-700 dark:bg-[#2A2A2A] dark:hover:border-blue-600
                          dark:hover:bg-blue-950/30"
            >
              <span className="mt-0.5 text-xl" aria-hidden="true">
                {preset.icon}
              </span>
              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                  {preset.label}
                </p>
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                  {preset.description}
                </p>
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* ── Main settings card ── */}
      <div className="surface space-y-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {/* Font selection */}
        <section aria-labelledby="font-heading">
          <h2
            id="font-heading"
            className="mb-3 text-sm font-medium uppercase tracking-wide text-gray-500 dark:text-gray-300"
          >
            Font
          </h2>
          <div className="flex flex-wrap gap-3">
            {FONTS.map(font => (
              <button
                key={font}
                type="button"
                aria-pressed={prefs.font === font}
                onClick={() => updatePref('font', font)}
                className={`rounded-lg border px-4 py-2 text-sm transition-all
                  focus-visible:outline-2 focus-visible:outline-offset-2
                  focus-visible:outline-blue-500
                  ${
                    prefs.font === font
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200'
                      : 'border-gray-200 hover:border-gray-400 dark:border-gray-600'
                  }`}
                style={{ fontFamily: `'${font}', sans-serif` }}
              >
                {font}
              </button>
            ))}
          </div>
        </section>

        {/* Background overlay */}
        <section aria-labelledby="overlay-heading">
          <h2
            id="overlay-heading"
            className="mb-1 text-sm font-medium uppercase tracking-wide text-gray-500 dark:text-gray-300"
          >
            Background overlay
          </h2>
          <p className="mb-3 text-xs text-gray-400">
            Selected:{' '}
            <span className="font-semibold text-gray-600 dark:text-gray-300">
              {selectedOverlayLabel}
            </span>
          </p>
          <div className="flex flex-wrap gap-4">
            {OVERLAYS.map(option => (
              <button
                key={option.value}
                type="button"
                title={option.label}
                aria-label={`${option.label} background`}
                aria-pressed={prefs.overlay === option.value}
                onClick={() => updatePref('overlay', option.value)}
                className="flex flex-col items-center gap-1
                            focus-visible:outline-2 focus-visible:outline-offset-2
                            focus-visible:outline-blue-500"
              >
                <span
                  className={`h-9 w-9 rounded-full border-2 transition-transform
                    ${
                      prefs.overlay === option.value
                        ? 'scale-110 border-blue-500'
                        : 'border-gray-300'
                    }`}
                  style={{ backgroundColor: option.value }}
                />
                <span className="text-[10px] text-gray-500 dark:text-gray-400">
                  {option.label}
                </span>
              </button>
            ))}
          </div>
        </section>

        {/* Range settings */}
        <RangeSetting
          label="Font size"
          value={prefs.fontSize}
          min={14}
          max={28}
          step={1}
          unit="px"
          onChange={event => updatePref('fontSize', Number(event.target.value))}
          onStep={direction => stepPref('fontSize', direction, 14, 28, 1)}
        />
        <RangeSetting
          label="Line spacing"
          value={prefs.lineSpacing}
          min={1.5}
          max={3}
          step={0.1}
          onChange={event => updatePref('lineSpacing', Number(event.target.value))}
          onStep={direction => stepPref('lineSpacing', direction, 1.5, 3, 0.1)}
        />
        <RangeSetting
          label="Word spacing"
          value={prefs.wordSpacing}
          min={0}
          max={8}
          step={1}
          unit="px"
          onChange={event => updatePref('wordSpacing', Number(event.target.value))}
          onStep={direction => stepPref('wordSpacing', direction, 0, 8, 1)}
        />

        {/* Highlight color */}
        <section aria-labelledby="highlight-heading">
          <h2
            id="highlight-heading"
            className="mb-1 text-sm font-medium uppercase tracking-wide text-gray-500 dark:text-gray-300"
          >
            Word highlight colour
          </h2>
          <p className="mb-3 text-xs text-gray-400">
            Selected:{' '}
            <span className="font-semibold text-gray-600 dark:text-gray-300">
              {selectedHighlightLabel}
            </span>
          </p>
          <div className="flex items-center gap-4">
            {HIGHLIGHT_COLORS.map(color => (
              <button
                key={color.value}
                type="button"
                aria-label={`${color.label} highlight`}
                aria-pressed={prefs.highlightColor === color.value}
                onClick={() => updatePref('highlightColor', color.value)}
                className="flex flex-col items-center gap-1
                            focus-visible:outline-2 focus-visible:outline-offset-2
                            focus-visible:outline-blue-500"
              >
                <span
                  className={`h-9 w-9 rounded-full border-2 transition-transform
                    ${
                      prefs.highlightColor === color.value
                        ? 'scale-110 border-blue-500'
                        : 'border-gray-300'
                    }`}
                  style={{ backgroundColor: color.value }}
                />
                <span className="text-[10px] text-gray-500 dark:text-gray-400">
                  {color.label}
                </span>
              </button>
            ))}
          </div>
        </section>

        {/* Toggles */}
        <section className="space-y-5" aria-labelledby="options-heading">
          <h2
            id="options-heading"
            className="text-sm font-medium uppercase tracking-wide text-gray-500 dark:text-gray-300"
          >
            Options
          </h2>
          <Toggle
            checked={prefs.focusRuler}
            label="Focus ruler"
            description="Highlights the line you are reading and dims the rest"
            onChange={() => updatePref('focusRuler', !prefs.focusRuler)}
          />
          <Toggle
            checked={prefs.darkMode}
            label="Dark mode"
            description="Switch to a dark reading background (comfortable, not pure black)"
            onChange={() => updatePref('darkMode', !prefs.darkMode)}
          />
          <Toggle
            checked={prefs.phrasePauses}
            label="Phrase pauses"
            description="Add pauses at commas and clause boundaries during playback"
            onChange={() => updatePref('phrasePauses', !prefs.phrasePauses)}
          />
        </section>
      </div>

      {/* ── Accessibility summary ── */}
      <div className="mt-6">
        <AccessibilitySummary prefs={prefs} />
      </div>
    </main>
  )
}