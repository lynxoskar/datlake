import { useEffect, useRef } from 'react'

interface UseSSEOptions {
  onMessage?: (event: MessageEvent) => void
  onError?: (error: Event) => void
  onOpen?: (event: Event) => void
  enabled?: boolean
}

export function useSSE(url: string, options: UseSSEOptions = {}) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const { onMessage, onError, onOpen, enabled = true } = options

  useEffect(() => {
    if (!enabled || !url) return

    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    if (onOpen) {
      eventSource.onopen = onOpen
    }

    if (onMessage) {
      eventSource.onmessage = onMessage
    }

    if (onError) {
      eventSource.onerror = onError
    }

    return () => {
      eventSource.close()
    }
  }, [url, enabled, onOpen, onMessage, onError])

  return {
    close: () => eventSourceRef.current?.close(),
    readyState: eventSourceRef.current?.readyState,
    eventSource: eventSourceRef.current,
  }
} 