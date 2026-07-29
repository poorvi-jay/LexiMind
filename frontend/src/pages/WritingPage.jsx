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
  const [predictions, setPredictions] = useState({ suggestions: [], phrase_suggestion: '' })
  const [saveStatus, setSaveStatus] = useState(null) // null | 'saving' | 'saved' | 'error'
  const checkDebounce = useRef(null)
  const predictDebounce = useRef(null)
  const textareaRef = useRef(null)
  const contentRef = useRef(content) // always-current content for the interval closure
  const [documents, setDocuments] = useState([])
  const [showDocs, setShowDocs] = useState(false)
  const [saveTitle, setSaveTitle] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)

  useEffect(() => {
    contentRef.current = content
  }, [content])

  useEffect(() => {
    if (showDocs && isAuthenticated) loadDocuments()
  }, [showDocs, isAuthenticated])

  // ── Load existing draft on mount (F31: survives refresh/browser close) ──
  useEffect(() => {
    if (!isAuthenticated) return
    api.get('/writing/autosave')
      .then(data => setContent(data.content || ''))
      .catch(() => { /* no draft yet, or not logged in - fine, start blank */ })
  }, [isAuthenticated])

  // ── Auto-save every 30s, with retry (F31) ──
  useEffect(() => {
    if (!isAuthenticated) return

    async function saveWithRetry(retriesLeft = 3) {
      setSaveStatus('saving')
      try {
        await api.patch('/writing/autosave', { content: contentRef.current })
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus(null), 2000)
      } catch (err) {
        if (retriesLeft > 0) {
          setTimeout(() => saveWithRetry(retriesLeft - 1), 2000)
        } else {
          setSaveStatus('error')
        }
      }
    }

    const interval = setInterval(() => saveWithRetry(), 30000)
    return () => clearInterval(interval)
  }, [isAuthenticated])

  // ── /nlp/check (unchanged from Task 12) ──
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
    if (checkDebounce.current) clearTimeout(checkDebounce.current)
    checkDebounce.current = setTimeout(async () => {
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
    return () => clearTimeout(checkDebounce.current)
  }, [content, isAuthenticated])

  // ── /nlp/predict (unchanged from Task 13) ──
  useEffect(() => {
    if (!isAuthenticated) {
      setPredictions({ suggestions: [], phrase_suggestion: '' })
      return
    }
    if (predictDebounce.current) clearTimeout(predictDebounce.current)
    predictDebounce.current = setTimeout(async () => {
      const cursorPos = textareaRef.current?.selectionStart ?? content.length
      const prefix = content.slice(0, cursorPos)
      const atWordBoundary = prefix === '' || /\s$/.test(prefix)
      if (!prefix.trim() || !atWordBoundary) {
        setPredictions({ suggestions: [], phrase_suggestion: '' })
        return
      }
      try {
        const data = await api.post('/nlp/predict', { prefix })
        setPredictions(data)
      } catch {
        setPredictions({ suggestions: [], phrase_suggestion: '' })
      }
    }, 300)
    return () => clearTimeout(predictDebounce.current)
  }, [content, isAuthenticated])

  function insertAtCursor(text) {
    const textarea = textareaRef.current
    if (!textarea) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const newContent = content.slice(0, start) + text + content.slice(end)
    setContent(newContent)
    requestAnimationFrame(() => {
      const newPos = start + text.length
      textarea.focus()
      textarea.setSelectionRange(newPos, newPos)
    })
  }

  async function loadDocuments() {
    try {
      const docs = await api.get('/writing/documents')
      setDocuments(docs)
    } catch {
      setDocuments([])
    }
  }

  async function handleSaveAs() {
    if (!saveTitle.trim()) return

    const duplicate = documents.some(
      doc => doc.title.toLowerCase() === saveTitle.trim().toLowerCase()
    )
    if (duplicate && !window.confirm(
      `A document named "${saveTitle}" already exists. Save as a separate copy anyway?`
    )) {
      return
    }

    try {
      await api.post('/writing/documents', { title: saveTitle, content })
      setSaveTitle('')
      setShowSaveDialog(false)
      loadDocuments()
    } catch {
      /* could add error UI here later */
    }
  }

  async function handleLoadDocument(docId) {
    try {
      const doc = await api.get(`/writing/documents/${docId}`)
      setContent(doc.content)
      setShowDocs(false)
    } catch {
      /* could add error UI here later */
    }
  }

  async function handleDeleteDocument(docId, e) {
    e.stopPropagation() // don't trigger loadDocument when clicking delete
    try {
      await api.delete(`/writing/documents/${docId}`)
      loadDocuments()
    } catch {
      /* could add error UI here later */
    }
  }

  async function handleNewDocument() {
    if (content.trim() && !window.confirm('Start a new document? Your current unsaved draft will be cleared.')) {
      return
    }
    setContent('')
    try {
      await api.patch('/writing/autosave', { content: '' })
    } catch {
      /* if this fails, the next 30s autosave cycle will still catch up */
    }
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
    })
  }

  const totalIssues =
    results.spelling.length + results.grammar.length + results.homophones.length

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-gray-950 dark:text-white">
          Writing
        </h1>
        {saveStatus && (
          <span className="text-xs font-medium text-gray-400 dark:text-gray-500">
            {saveStatus === 'saving' && 'Saving...'}
            {saveStatus === 'saved' && '✓ Saved'}
            {saveStatus === 'error' && 'Could not save'}
          </span>
        )}
      </div>

      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setShowSaveDialog(true)}
          className="rounded-xl border border-gray-200 px-3 py-1.5 text-sm font-medium
                    text-gray-700 hover:bg-gray-50
                    dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          Save As...
        </button>
        <button
          onClick={() => setShowDocs(v => !v)}
          className="rounded-xl border border-gray-200 px-3 py-1.5 text-sm font-medium
                    text-gray-700 hover:bg-gray-50
                    dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          My Documents
        </button>
        <button
          onClick={handleNewDocument}
          className="rounded-xl border border-gray-200 px-3 py-1.5 text-sm font-medium
                    text-gray-700 hover:bg-gray-50
                    dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          New
        </button>
      </div>

      {showSaveDialog && (
        <div className="mb-4 flex gap-2">
          <input
            type="text"
            value={saveTitle}
            onChange={e => setSaveTitle(e.target.value)}
            placeholder="Document title..."
            className="flex-1 rounded-xl border border-gray-200 p-2 text-sm
                      dark:border-gray-700 dark:bg-[#1E1E1E] dark:text-white"
          />
          <button
            onClick={handleSaveAs}
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Save
          </button>
        </div>
      )}

      {showDocs && (
        <div className="mb-4 rounded-2xl border border-gray-200 p-3 dark:border-gray-800">
          {documents.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400">No saved documents yet.</p>
          )}
          {documents.map(doc => (
            <div
              key={doc.id}
              onClick={() => handleLoadDocument(doc.id)}
              className="flex cursor-pointer items-center justify-between rounded-lg px-2 py-2
                        text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <span className="text-gray-800 dark:text-gray-200">{doc.title}</span>
              <button
                onClick={e => handleDeleteDocument(doc.id, e)}
                className="text-xs text-red-500 hover:text-red-700 dark:text-red-400"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">
        Draft your writing here. Grammar, spelling, and homophone
        suggestions appear automatically as you pause typing.
      </p>

      <textarea
        ref={textareaRef}
        value={content}
        onChange={e => setContent(e.target.value)}
        onClick={() => setContent(c => c)}
        onKeyUp={() => setContent(c => c)}
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

      {(predictions.suggestions.length > 0 || predictions.phrase_suggestion) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {predictions.suggestions.map((word, i) => (
            <button
              key={`w-${i}-${word}`}
              onClick={() => insertAtCursor(word + ' ')}
              className="rounded-full border border-gray-200 bg-white px-4 py-1.5 text-sm
                         font-medium text-gray-700 hover:bg-gray-50
                         dark:border-gray-700 dark:bg-[#2A2A2A] dark:text-gray-200
                         dark:hover:bg-gray-800"
            >
              {word}
            </button>
          ))}
          {predictions.phrase_suggestion && predictions.phrase_suggestion.trim() !== '' && (
            <button
              onClick={() => insertAtCursor(predictions.phrase_suggestion + ' ')}
              className="rounded-full border border-purple-300 bg-purple-50 px-4 py-1.5 text-sm
                         font-medium text-purple-700 hover:bg-purple-100
                         dark:border-purple-800 dark:bg-purple-950/40 dark:text-purple-200
                         dark:hover:bg-purple-950/70"
            >
              {predictions.phrase_suggestion}
            </button>
          )}
        </div>
      )}

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