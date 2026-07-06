import { useState } from 'react'
import { usePrefs } from '../context/PreferencesContext'

export default function WritingPage() {
  const { prefs } = usePrefs()
  const [content, setContent] = useState('')

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="mb-2 text-2xl font-bold tracking-tight text-gray-950 dark:text-white">
        Writing
      </h1>
      <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">
        Draft your writing here. Grammar, spelling, and word suggestions
        will appear as you type once this page is fully wired up.
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
    </main>
  )
}