import { useCallback, useState } from 'react'

export function useToast() {
  const [toast, setToast] = useState(null)
  const showToast = useCallback((message, type) => {
    setToast({ message, type: type || 'info' })
  }, [])
  const hideToast = useCallback(() => setToast(null), [])

  return { toast, showToast, hideToast }
}
