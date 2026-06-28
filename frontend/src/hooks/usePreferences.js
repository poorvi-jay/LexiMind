import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'leximind-prefs'

const DEFAULTS = {
  font: 'Lexend',
  fontSize: 18,
  lineSpacing: 2.0,
  wordSpacing: 2,
  overlay: '#FFFFFF',
  highlightColor: '#FFD700',
  focusRuler: true,
  darkMode: false,
  phrasePauses: true,
}

/**
 * Reading presets — each one sets multiple preferences at once.
 */
export const PRESETS = {
  comfort: {
    label: 'Comfort Reading',
    description: 'Relaxed spacing and warm background for extended reading.',
    icon: '☕',
    values: {
      font: 'Lexend',
      fontSize: 20,
      lineSpacing: 2.2,
      wordSpacing: 3,
      overlay: '#FFF9E6',
      highlightColor: '#FFD700',
      focusRuler: true,
      phrasePauses: true,
    },
  },
  academic: {
    label: 'Academic Reading',
    description: 'Tighter layout for study materials and textbooks.',
    icon: '🎓',
    values: {
      font: 'Lexend',
      fontSize: 18,
      lineSpacing: 1.8,
      wordSpacing: 2,
      overlay: '#FFFFFF',
      highlightColor: '#87CEEB',
      focusRuler: true,
      phrasePauses: true,
    },
  },
  focus: {
    label: 'Maximum Focus',
    description: 'Large text, high spacing, focus ruler, minimal distractions.',
    icon: '🎯',
    values: {
      font: 'Lexend',
      fontSize: 24,
      lineSpacing: 2.6,
      wordSpacing: 5,
      overlay: '#E8F5E9',
      highlightColor: '#90EE90',
      focusRuler: true,
      phrasePauses: true,
    },
  },
  dyslexic: {
    label: 'OpenDyslexic Mode',
    description: 'OpenDyslexic font with optimised contrast and spacing.',
    icon: '✦',
    values: {
      font: 'OpenDyslexic',
      fontSize: 20,
      lineSpacing: 2.4,
      wordSpacing: 4,
      overlay: '#FFF9E6',
      highlightColor: '#FFD700',
      focusRuler: true,
      phrasePauses: true,
    },
  },
}

/**
 * Core preferences hook — manages state, localStorage, and CSS variable sync.
 * Consumed by PreferencesContext.
 */
export function usePreferences() {
  const [prefs, setPrefs] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Merge with DEFAULTS so new keys are always present
        return { ...DEFAULTS, ...parsed }
      }
    } catch {
      /* ignore corrupt data */
    }
    return { ...DEFAULTS }
  })

  /* ── Persist to localStorage ── */
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
    } catch {
      /* storage full / disabled */
    }
  }, [prefs])

  /* ── Sync CSS custom properties + dark mode class ── */
  useEffect(() => {
    const root = document.documentElement
    const body = document.body

    root.style.setProperty('--leximind-font', `'${prefs.font}', Arial, Verdana, sans-serif`)
    root.style.setProperty('--leximind-overlay', prefs.darkMode ? '#1E1E1E' : prefs.overlay)
    root.style.setProperty('--leximind-font-size', `${prefs.fontSize}px`)
    root.style.setProperty('--leximind-line-spacing', String(prefs.lineSpacing))
    root.style.setProperty('--leximind-highlight', prefs.highlightColor)
    root.style.setProperty('--leximind-word-spacing', `${prefs.wordSpacing}px`)

    body.style.fontFamily = `'${prefs.font}', Arial, Verdana, sans-serif`
    body.style.fontSize = `${prefs.fontSize}px`
    body.style.lineHeight = String(prefs.lineSpacing)
    body.style.wordSpacing = `${prefs.wordSpacing}px`
    body.style.backgroundColor = prefs.darkMode ? '#1E1E1E' : prefs.overlay

    if (prefs.darkMode) {
      root.classList.add('dark')
      body.classList.add('dark')
    } else {
      root.classList.remove('dark')
      body.classList.remove('dark')
    }
  }, [prefs])

  /* ── Update a single preference ── */
  const updatePref = useCallback((key, value) => {
    setPrefs(prev => ({ ...prev, [key]: value }))
  }, [])

  /* ── Apply a full preset ── */
  const applyPreset = useCallback((presetKey) => {
    const preset = PRESETS[presetKey]
    if (preset) {
      setPrefs(prev => ({ ...prev, ...preset.values }))
    }
  }, [])

  /* ── Reset to defaults ── */
  const resetPrefs = useCallback(() => {
    setPrefs({ ...DEFAULTS })
  }, [])

  return { prefs, updatePref, applyPreset, resetPrefs }
}