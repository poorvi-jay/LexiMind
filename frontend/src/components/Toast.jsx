import { useEffect } from 'react'

const styles = {
  error:   'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-100',
  success: 'border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-100',
  warning: 'border-yellow-200 bg-yellow-50 text-yellow-800 dark:border-yellow-900 dark:bg-yellow-950 dark:text-yellow-100',
  info:    'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-100',
}

export function Toast({ message, type = 'info', onClose }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <div
      className={`fixed bottom-6 left-6 z-50 flex max-w-sm items-start gap-3 rounded-xl
                   border px-4 py-3 text-sm shadow-xl ${styles[type] || styles.info}`}
      role="alert"
      aria-live="assertive"
    >
      <p className="m-0 flex-1">{message}</p>
      <button
        type="button"
        onClick={onClose}
        className="font-semibold focus-visible:outline-2 focus-visible:outline-blue-500"
        aria-label="Dismiss notification"
      >
        Close
      </button>
    </div>
  )
}