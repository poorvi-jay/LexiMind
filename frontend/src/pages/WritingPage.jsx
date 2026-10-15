import { useEffect, useRef, useState } from 'react'
import { usePrefs } from '../context/PreferencesContext'
import { useAuth } from '../context/AuthContext'
import { api } from '../utils/api'

const TEMPLATES = {
  essay: { label: 'Essay' },
  email: { label: 'Email' },
  report: { label: 'Report' },
}

const TEMPLATE_TITLES = {
  essay: 'ESSAY WRITING',
  email: 'EMAIL DRAFT',
  report: 'REPORT WRITING',
}

// Stage 2: every template is a list of fields.
//   heading  -> printed as its own heading line, then the text   (essay / report sections)
//   inline   -> printed as "Label: text" on one line              (Subject, Title)
//   single   -> one-line <input> instead of a multi-line <textarea>
//   tight    -> no gap above it in the preview (name under sign-off)
const TEMPLATE_FIELDS = {
  essay: [
    { key: 'introduction', heading: 'Introduction', rows: 4, placeholder: 'State your main idea or argument here.' },
    { key: 'body1', heading: 'Body Paragraph 1', rows: 5, placeholder: 'Explain your first supporting point here.' },
    { key: 'body2', heading: 'Body Paragraph 2', rows: 5, placeholder: 'Explain your second supporting point here.' },
    { key: 'conclusion', heading: 'Conclusion', rows: 4, placeholder: 'Summarize your argument and restate your main idea.' },
  ],
  email: [
    { key: 'subject', label: 'Subject', inline: 'Subject: ', single: true, placeholder: 'What is this email about?' },
    { key: 'greeting', label: 'Greeting', single: true, placeholder: 'Dear [Name],' },
    { key: 'body', label: 'Message', rows: 8, placeholder: 'I am writing to ...' },
    { key: 'signoff', label: 'Sign-off', single: true, placeholder: 'Best regards,' },
    { key: 'name', label: 'Your name', single: true, tight: true, placeholder: '[Your Name]' },
  ],
  report: [
    { key: 'title', label: 'Title', inline: 'Title: ', single: true, placeholder: 'Report title' },
    { key: 'summary', heading: 'Summary', rows: 4, placeholder: 'Briefly summarize the purpose of this report.' },
    { key: 'findings', heading: 'Findings', rows: 5, placeholder: 'Describe what you found or observed.' },
    { key: 'recommendations', heading: 'Recommendations', rows: 4, placeholder: 'Suggest next steps or conclusions.' },
  ],
}

// sections -> one plain string. This string is still what gets autosaved,
// saved, spell-checked, etc., so nothing outside this file has to change.
function serializeSections(templateKey, s) {
  const g = k => s[k] || ''
  if (templateKey === 'email') {
    return `Subject: ${g('subject')}\n\n${g('greeting')}\n\n${g('body')}\n\n${g('signoff')}\n${g('name')}`
  }
  return TEMPLATE_FIELDS[templateKey]
    .map(f => (f.inline ? `${f.inline}${g(f.key)}` : `${f.heading}\n\n${g(f.key)}`))
    .join('\n\n')
}

// string -> sections. Only used when LOADING (saved doc, autosaved draft,
// page refresh) - never while typing, so typing can't re-split your text.
function parseSections(templateKey, text) {
  const fields = TEMPLATE_FIELDS[templateKey]
  const out = Object.fromEntries(fields.map(f => [f.key, '']))
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n')

  if (templateKey === 'email') {
    let rest = lines
    if (/^subject:/i.test(lines[0] || '')) {
      out.subject = lines[0].replace(/^subject: ?/i, '')
      rest = lines.slice(1)
    }
    const blocks = rest.join('\n').replace(/^\n/, '').split('\n\n')
    if (blocks.length >= 3) {
      out.greeting = blocks[0]
      out.body = blocks.slice(1, -1).join('\n\n')
      const [signoff, ...nameParts] = blocks[blocks.length - 1].split('\n')
      out.signoff = signoff
      out.name = nameParts.join('\n')
    } else {
      out.greeting = blocks[0] || ''
      out.body = blocks.slice(1).join('\n\n')
    }
    return out
  }

  // essay / report: inline fields first (Title: ...)
  fields.filter(f => f.inline).forEach(f => {
    const label = f.inline.trim()
    const line = lines.find(l => l.toLowerCase().startsWith(label.toLowerCase()))
    if (line) out[f.key] = line.slice(label.length).replace(/^ /, '')
  })

  // then headed sections, found in order
  const headed = fields.filter(f => f.heading)
  const idxs = []
  let from = 0
  for (const f of headed) {
    const i = lines.findIndex((l, n) => n >= from && l.trim() === f.heading)
    idxs.push(i)
    if (i !== -1) from = i + 1
  }
  if (idxs.some(i => i === -1)) {
    // Unrecognised layout: keep everything in the first section rather than lose it.
    out[headed[0].key] = lines.join('\n')
    return out
  }
  headed.forEach((f, n) => {
    const start = idxs[n] + 1
    const isLast = n + 1 >= headed.length
    const end = isLast ? lines.length : idxs[n + 1]
    let raw = lines.slice(start, end).join('\n').replace(/^\n/, '')
    if (!isLast) raw = raw.replace(/\n$/, '')
    out[f.key] = raw
  })
  return out
}

/* ── Left side: one box per section ── */
function TemplateForm({ templateKey, sections, onChange, onFieldFocus, textStyle, background }) {
  return (
    <div className="space-y-4">
      {TEMPLATE_FIELDS[templateKey].map(f => {
        const id = `tpl-${templateKey}-${f.key}`
        const label = f.label || f.heading
        const common = {
          id,
          value: sections[f.key] || '',
          placeholder: f.placeholder,
          style: { ...textStyle, backgroundColor: background },
          onChange: e => onChange(f.key, e.target.value),
          onFocus: e => onFieldFocus(e.target, f.key),
          className:
            'w-full rounded-2xl border border-gray-200 p-4 text-gray-900 shadow-sm outline-none ' +
            'transition-colors focus-visible:border-blue-500 focus-visible:ring-2 ' +
            'focus-visible:ring-blue-200 dark:border-gray-800 dark:text-gray-100 ' +
            'dark:focus-visible:ring-blue-900',
        }
        return (
          <div key={f.key}>
            <label
              htmlFor={id}
              className="mb-1 block text-sm font-semibold text-gray-700 dark:text-gray-300"
            >
              {label}
            </label>
            {f.single ? (
              <input type="text" {...common} />
            ) : (
              <textarea rows={f.rows || 4} {...common} className={common.className + ' resize-y'} />
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ── Right side: formatted "paper" built from the same sections ── */
function TemplatePreview({ templateKey, sections, style }) {
  const fields = TEMPLATE_FIELDS[templateKey]

  return (
    <article
      aria-label="Formatted preview"
      style={style}
      className="min-h-[400px] rounded-2xl border border-gray-200 p-6 shadow-md text-gray-900
                 dark:border-gray-800 dark:text-gray-100
                 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:self-start lg:overflow-y-auto"
    >
      <h2 className="mb-4 border-b border-gray-300 pb-2 text-center text-lg font-bold
                     uppercase tracking-wide dark:border-gray-700">
        {TEMPLATE_TITLES[templateKey]}
      </h2>

      {fields.map(f => {
        const text = sections[f.key] || ''
        const label = f.label || f.heading

        if (f.inline) {
          return (
            <p key={f.key} className="m-0 mb-2 font-semibold">
              <span className="mr-2 text-xs font-medium uppercase tracking-wide text-gray-400">
                {label}
              </span>
              {text || <span className="font-normal italic text-gray-400">{f.placeholder}</span>}
            </p>
          )
        }

        return (
          <section key={f.key} className={f.tight ? 'mt-0' : 'mt-3'}>
            {f.heading && (
              <h3 className="mb-1 text-base font-bold text-blue-700 dark:text-blue-300">
                {f.heading}
              </h3>
            )}
            {text ? (
              text.split('\n').map((line, i) =>
                line.trim() ? (
                  <p key={i} className="m-0 whitespace-pre-wrap">{line}</p>
                ) : (
                  <div key={i} className="h-3" />
                )
              )
            ) : (
              <p className="m-0 italic text-gray-400">{f.placeholder}</p>
            )}
          </section>
        )
      })}
    </article>
  )
}

export default function WritingPage() {
  const { prefs } = usePrefs()
  const { isAuthenticated } = useAuth()
  const [content, setContent] = useState('')
  const [sections, setSections] = useState({}) // Stage 2: per-field text while a template is active
  const [results, setResults] = useState({ spelling: [], grammar: [], homophones: [] })
  const [checking, setChecking] = useState(false)
  const [checkError, setCheckError] = useState(null)
  const [predictions, setPredictions] = useState({ suggestions: [], phrase_suggestion: '' })
  const [saveStatus, setSaveStatus] = useState(null) // null | 'saving' | 'saved' | 'error'
  const checkDebounce = useRef(null)
  const predictDebounce = useRef(null)
  const textareaRef = useRef(null) // the plain textarea (no template)
  const activeFieldRef = useRef(null) // the template field the cursor is in
  const activeFieldKeyRef = useRef(null)
  const contentRef = useRef(content) // always-current content for the interval closure
  const loadedDocIdRef = useRef(null) // always-current loaded-document id for the interval closure
  const [documents, setDocuments] = useState([])
  const [showDocs, setShowDocs] = useState(false)
  const [saveTitle, setSaveTitle] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [loadedDocId, setLoadedDocId] = useState(null) // id of the currently-open named document, or null (unsaved/new)
  const [isReading, setIsReading] = useState(false)
  const [isReadPaused, setIsReadPaused] = useState(false)
  const [isReadLoading, setIsReadLoading] = useState(false)
  const [readError, setReadError] = useState(null)
  const audioRef = useRef(null)
  const readRequestRef = useRef(0)
  const [showTemplates, setShowTemplates] = useState(false)
  const [activeTemplate, setActiveTemplate] = useState(
    () => localStorage.getItem('leximind-active-template') || null
  )

  useEffect(() => {
    contentRef.current = content
  }, [content])

  useEffect(() => {
    loadedDocIdRef.current = loadedDocId
  }, [loadedDocId])

  const activeTemplateRef = useRef(activeTemplate)
  useEffect(() => {
    activeTemplateRef.current = activeTemplate
  }, [activeTemplate])

  const resultsRef = useRef(results)
  useEffect(() => {
    resultsRef.current = results
  }, [results])

  // B9: load the list on mount (and when the panel opens) so the
  // duplicate-title check in handleSaveAs always has real data
  useEffect(() => {
    if (isAuthenticated) loadDocuments()
  }, [showDocs, isAuthenticated])

  useEffect(() => {
    if (activeTemplate) {
      localStorage.setItem('leximind-active-template', activeTemplate)
    } else {
      localStorage.removeItem('leximind-active-template')
    }
  }, [activeTemplate])

  // ── Load existing draft on mount (F31: survives refresh/browser close) ──
  useEffect(() => {
    if (!isAuthenticated) return
    api.get('/writing/autosave')
      .then(data => applyContent(data.content || '', activeTemplateRef.current))
      .catch(() => { /* no draft yet, or not logged in - fine, start blank */ })
  }, [isAuthenticated])

  // ── Auto-save every 30s, with retry (F31) ──

  useEffect(() => {
    if (!isAuthenticated) return

    async function saveWithRetry(retriesLeft = 3) {
      setSaveStatus('saving')
      try {
        // B6 follow-up: if a named document is currently open, keep
        // autosaving into THAT document instead of the separate draft
        // row - otherwise edits silently fork into the draft and the
        // open document goes stale. No document open -> unchanged
        // behaviour, autosave the draft as before.
        if (loadedDocIdRef.current) {
          await api.put(`/writing/documents/${loadedDocIdRef.current}`, {
            title: saveTitle,
            content: contentRef.current,
            template: activeTemplateRef.current,
          })
        } else {
          await api.patch('/writing/autosave', { content: contentRef.current })
        }
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus(null), 2000)
      } catch (err) {
        if (err.status === 404 && loadedDocIdRef.current) {
          // Loaded document was deleted elsewhere. Retrying the same
          // PUT would 404 every time - fall back to the draft instead
          // of burning all 3 retries and losing 30s+ of typing.
          loadedDocIdRef.current = null
          setLoadedDocId(null)
          saveWithRetry(retriesLeft)
          return
        }
        if (retriesLeft > 0) {
          setTimeout(() => saveWithRetry(retriesLeft - 1), 2000)
        } else {
          setSaveStatus('error')
        }
      }
    }

    const interval = setInterval(() => saveWithRetry(), 30000)
    return () => clearInterval(interval)
  }, [isAuthenticated, saveTitle])

  // ── Log writing session on tab-close/hide (F38, Task 4.8) ──
  useEffect(() => {
    if (!isAuthenticated) return

    function handleVisibilityChange() {
      if (document.visibilityState !== 'hidden') return
      const wordCount = contentRef.current.trim().split(/\s+/).filter(Boolean).length
      if (wordCount === 0) return

      const r = resultsRef.current
      api.post('/sessions/writing', {
        word_count: wordCount,
        spell_error_count: r.spelling.length,
        grammar_error_count: r.grammar.length,
        homophone_flag_count: r.homophones.length,
      }).catch(err => console.error('Could not log writing session:', err))
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
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

  // ── /nlp/predict (Stage 2: reads the focused box, not the whole document) ──
  useEffect(() => {
    if (!isAuthenticated) {
      setPredictions({ suggestions: [], phrase_suggestion: '' })
      return
    }
    if (predictDebounce.current) clearTimeout(predictDebounce.current)
    predictDebounce.current = setTimeout(async () => {
      const el = getEditor()
      if (activeTemplate && !el) {
        setPredictions({ suggestions: [], phrase_suggestion: '' })
        return
      }
      const text = el ? el.value : content
      const cursorPos = el?.selectionStart ?? text.length
      const prefix = text.slice(0, cursorPos)
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

  // ── Alt+R: read last complete sentence (F47) ──
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.altKey && e.key.toLowerCase() === 'r') {
        e.preventDefault()

        // Template mode: read from the box you are typing in, so section
        // headings are not read out as part of a sentence.
        const el = getEditor()
        const source = activeTemplate && el ? el.value : content

        const sentences = source.match(/[^.!?]+[.!?]+/g) || []
        const matchedLength = sentences.join('').length
        const trailing = source.slice(matchedLength).trim()

        let last
        if (trailing) {
          last = trailing
        } else if (sentences.length > 0) {
          last = sentences[sentences.length - 1].trim()
        } else {
          last = source.trim()
        }

        if (last) playText(last)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [content, activeTemplate])

  /* ── Stage 2 helpers ── */

  // The element the user is currently typing in (plain textarea or template field).
  function getEditor() {
    const el = activeTemplate ? activeFieldRef.current : textareaRef.current
    return el && el.isConnected ? el : null
  }

  // Set the document text and keep the per-section state in step with it.
  function applyContent(text, templateKey) {
    setContent(text)
    setSections(templateKey ? parseSections(templateKey, text) : {})
  }

  // Typing in one template box: update that section, rebuild the single string.
  function updateSection(key, value) {
    const next = { ...sections, [key]: value }
    setSections(next)
    setContent(serializeSections(activeTemplate, next))
  }

  function handleFieldFocus(el, key) {
    activeFieldRef.current = el
    activeFieldKeyRef.current = key
    // pills from the previous box must not be inserted into this one
    setPredictions({ suggestions: [], phrase_suggestion: '' })
  }

  // Has the user typed anything of their own? (headings alone don't count)
  function hasUserText() {
    return activeTemplate
      ? Object.values(sections).some(v => v.trim())
      : content.trim().length > 0
  }

  function insertAtCursor(text) {
    const el = getEditor()
    if (!el) return
    const start = el.selectionStart
    const end = el.selectionEnd
    const newValue = el.value.slice(0, start) + text + el.value.slice(end)
    if (activeTemplate) {
      updateSection(activeFieldKeyRef.current, newValue)
    } else {
      setContent(newValue)
    }
    requestAnimationFrame(() => {
      const newPos = start + text.length
      el.focus()
      el.setSelectionRange(newPos, newPos)
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

    // Only warn about a duplicate title when this save would create a
    // NEW row. Updating the document that's already open is expected
    // to keep matching its own title - that's not a duplicate.
    if (!loadedDocId) {
      const duplicate = documents.some(
        doc => doc.title.toLowerCase() === saveTitle.trim().toLowerCase()
      )
      if (duplicate && !window.confirm(
        `A document named "${saveTitle}" already exists. Save as a separate copy anyway?`
      )) {
        return
      }
    }

    setSaveStatus('saving')
    try {
      if (loadedDocId) {
        await api.put(`/writing/documents/${loadedDocId}`, {
          title: saveTitle,
          content,
          template: activeTemplate,
        })
      } else {
        // B10: send the template so it is stored with the document
        const result = await api.post('/writing/documents', {
          title: saveTitle,
          content,
          template: activeTemplate,
        })
        setLoadedDocId(result.id)
      }
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(null), 2000)
      setShowSaveDialog(false)
      loadDocuments()
    } catch (err) {
      if (loadedDocId && err.status === 404) {
        // The loaded document no longer exists - most likely deleted
        // from My Documents while still open here. Retrying the same
        // update would just 404 again, so offer to save as new instead
        // of just reporting failure.
        if (window.confirm(
          'This document no longer exists (it may have been deleted). Save as a new document instead?'
        )) {
          try {
            const result = await api.post('/writing/documents', {
              title: saveTitle,
              content,
              template: activeTemplate,
            })
            setLoadedDocId(result.id)
            setSaveStatus('saved')
            setTimeout(() => setSaveStatus(null), 2000)
            setShowSaveDialog(false)
            loadDocuments()
          } catch {
            setSaveStatus('error')
          }
          return
        }
      }
      setSaveStatus('error')
    }
  }

  async function handleLoadDocument(docId) {
    try {
      const doc = await api.get(`/writing/documents/${docId}`)
      // B10: restore the document's template (if it has a valid one) so the
      // next save/autosave doesn't overwrite it with null
      const tpl = TEMPLATES[doc.template] ? doc.template : null
      setActiveTemplate(tpl)
      applyContent(doc.content, tpl)
      setLoadedDocId(docId)
      setSaveTitle(doc.title)
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

  function releaseReadAudio() {
    const audio = audioRef.current
    if (!audio) return

    audio.onended = null
    audio.onerror = null
    audio.pause()

    if (audio.src) {
      URL.revokeObjectURL(audio.src)
    }

    audioRef.current = null
  }

  useEffect(() => {
    return () => {
      // B21: invalidate any pending TTS request and release the final
      // audio Blob URL when the Writing page unmounts.
      readRequestRef.current += 1
      releaseReadAudio()
    }
  }, [])

  async function playText(text) {
    if (!text.trim()) return

    const requestId = ++readRequestRef.current

    releaseReadAudio()
    setReadError(null)
    setIsReadLoading(true)
    setIsReading(false)
    setIsReadPaused(false)

    try {
      const data = await api.post('/tts/generate', { text })

      // The page may have unmounted or another reading may have started.
      if (requestId !== readRequestRef.current) return

      const byteChars = atob(data.audio_b64)
      const byteNumbers = new Array(byteChars.length)
      for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i)
      }

      const byteArray = new Uint8Array(byteNumbers)
      const blob = new Blob([byteArray], { type: 'audio/mpeg' })
      const url = URL.createObjectURL(blob)

      const audio = new Audio(url)
      audioRef.current = audio

      audio.onended = () => {
        if (audioRef.current !== audio) return
        URL.revokeObjectURL(url)
        audioRef.current = null
        setIsReading(false)
        setIsReadPaused(false)
        setIsReadLoading(false)
      }

      audio.onerror = () => {
        if (audioRef.current !== audio) return
        URL.revokeObjectURL(url)
        audioRef.current = null
        setReadError('Could not play audio.')
        setIsReading(false)
        setIsReadPaused(false)
        setIsReadLoading(false)
      }

      setIsReadLoading(false)
      await audio.play()

      if (requestId !== readRequestRef.current || audioRef.current !== audio) {
        audio.pause()
        URL.revokeObjectURL(url)
        if (audioRef.current === audio) {
          audioRef.current = null
        }
        return
      }

      setIsReading(true)
      setIsReadPaused(false)
    } catch (err) {
      if (requestId !== readRequestRef.current) return

      releaseReadAudio()
      setReadError('Could not read text right now.')
      setIsReading(false)
      setIsReadPaused(false)
      setIsReadLoading(false)
    }
  }

  async function handleReadBack() {
    if (isReadLoading) return

    if (isReading && audioRef.current) {
      audioRef.current.pause()
      setIsReading(false)
      setIsReadPaused(true)
      return
    }

    if (isReadPaused && audioRef.current) {
      try {
        await audioRef.current.play()
        setIsReading(true)
        setIsReadPaused(false)
      } catch {
        setReadError('Could not resume audio.')
        releaseReadAudio()
        setIsReading(false)
        setIsReadPaused(false)
      }
      return
    }

    const el = getEditor()
    if (!el) {
      setReadError('Select some text first to read it back.')
      return
    }

    const selected = el.value.slice(el.selectionStart, el.selectionEnd)
    if (!selected.trim()) {
      setReadError('Select some text first to read it back.')
      return
    }

    playText(selected)
  }

  async function handleNewDocument() {
    if (hasUserText() && !window.confirm('Start a new document? Your current unsaved draft will be cleared.')) {
      return
    }
    setContent('')
    setSections({})
    activeFieldRef.current = null
    setActiveTemplate(null)
    setLoadedDocId(null)
    setSaveTitle('')
    try {
      await api.patch('/writing/autosave', { content: '' })
    } catch {
      /* if this fails, the next 30s autosave cycle will still catch up */
    }
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
    })
  }

  async function handleUseTemplate(templateKey) {
    if (hasUserText() && !window.confirm(
      loadedDocId
        ? 'Start a new document from this template? The document you have open stays saved, but changes from the last 30 seconds may not be.'
        : 'Load this template? Your current unsaved draft will be cleared.'
    )) {
      return
    }

    // A template replaces the whole text, so this is a NEW document,
    // not an edit of the one that was open.
    loadedDocIdRef.current = null // stop autosave writing into the old document immediately
    setLoadedDocId(null)
    setSaveTitle('')

    activeFieldRef.current = null
    setSections({})
    setContent(serializeSections(templateKey, {}))
    setActiveTemplate(templateKey)

    try {
      await api.post('/writing/template-used', { template: templateKey })
    } catch {
      /* logging failure shouldn't block the user from using the template */
    }

    requestAnimationFrame(() => {
      document.getElementById(`tpl-${templateKey}-${TEMPLATE_FIELDS[templateKey][0].key}`)?.focus()
    })
  }

  const totalIssues =
    results.spelling.length + results.grammar.length + results.homophones.length

  const textStyle = {
    fontFamily: `'${prefs.font}', Arial, Verdana, sans-serif`,
    fontSize: `${prefs.fontSize}px`,
    lineHeight: prefs.lineSpacing,
    wordSpacing: `${prefs.wordSpacing}px`,
  }

  return (
    <main className={`mx-auto px-6 py-10 ${activeTemplate ? 'max-w-6xl' : 'max-w-4xl'}`}>
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

      <div className="mb-4 flex flex-wrap gap-2">
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
        <button
          onClick={handleReadBack}
          disabled={isReadLoading}
          className="rounded-xl border border-gray-200 px-3 py-1.5 text-sm font-medium
                    text-gray-700 hover:bg-gray-50 disabled:opacity-50
                    dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          {isReadLoading
            ? 'Loading...'
            : isReading
              ? 'Pause'
              : isReadPaused
                ? 'Resume'
                : 'Read Selection'}
        </button>
        <button
          onClick={() => setShowTemplates(v => !v)}
          className="rounded-xl border border-gray-200 px-3 py-1.5 text-sm font-medium
                    text-gray-700 hover:bg-gray-50
                    dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          Templates
        </button>
      </div>

      {showSaveDialog && (
        <div className="mb-4 flex gap-2">
          <input
            type="text"
            value={saveTitle}
            onChange={e => setSaveTitle(e.target.value)}
            maxLength={150}
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

      {showTemplates && (
        <div className="mb-4 flex gap-2 rounded-2xl border border-gray-200 p-3 dark:border-gray-800">
          {Object.entries(TEMPLATES).map(([key, tpl]) => (
            <button
              key={key}
              onClick={() => {
                handleUseTemplate(key)
                setShowTemplates(false)
              }}
              className="rounded-xl border border-gray-200 px-4 py-1.5 text-sm font-medium
                         text-gray-700 hover:bg-gray-50
                         dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              {tpl.label}
            </button>
          ))}
        </div>
      )}

      {readError && (
        <p className="mb-2 text-xs text-amber-600 dark:text-amber-400">{readError}</p>
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

      <p className="mb-2 text-sm text-gray-500 dark:text-gray-400">
        Draft your writing here. Grammar, spelling, and homophone
        suggestions appear automatically as you pause typing.
      </p>

      {activeTemplate ? (
        /* Template mode: a box per section on the left, formatted preview on the right */
        <div className="grid gap-4 lg:grid-cols-2">
          <TemplateForm
            key={activeTemplate}
            templateKey={activeTemplate}
            sections={sections}
            onChange={updateSection}
            onFieldFocus={handleFieldFocus}
            textStyle={textStyle}
            background={prefs.darkMode ? '#1E1E1E' : prefs.overlay}
          />
          <TemplatePreview
            templateKey={activeTemplate}
            sections={sections}
            style={{ ...textStyle, backgroundColor: prefs.darkMode ? '#2A2A2A' : prefs.overlay }}
          />
        </div>
      ) : (
        <textarea
          ref={textareaRef}
          value={content}
          onChange={e => setContent(e.target.value)}
          onClick={() => setContent(c => c)}
          onKeyUp={() => setContent(c => c)}
          placeholder="Start typing..."
          style={{
            ...textStyle,
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
      )}

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