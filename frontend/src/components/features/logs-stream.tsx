'use client'

import { useState, useRef, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useSSE } from '@/hooks/use-sse'
import { LogEntry } from '@/types'
import { ScrollText, Pause, Play, Trash2 } from 'lucide-react'

export function LogsStream() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isPaused, setIsPaused] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Mock SSE connection for logs - in real implementation, this would connect to the logs endpoint
  useSSE(`${process.env.NEXT_PUBLIC_API_URL}/logs/events`, {
    enabled: !isPaused,
    onMessage: (event) => {
      try {
        const logEntry: LogEntry = JSON.parse(event.data)
        setLogs(prev => {
          const updated = [...prev, logEntry]
          // Keep only the last 100 logs to prevent memory issues
          return updated.slice(-100)
        })
      } catch (error) {
        console.error('Error parsing log event:', error)
      }
    },
    onError: (error) => {
      console.error('Logs SSE connection error:', error)
    }
  })

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  // Detect when user scrolls up to disable auto-scroll
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 5
      setAutoScroll(isAtBottom)
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'text-red-400'
      case 'warning':
        return 'text-yellow-400'
      case 'info':
        return 'text-blue-400'
      case 'debug':
        return 'text-gray-400'
      default:
        return 'text-gray-400'
    }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString()
    } catch {
      return timestamp
    }
  }

  const clearLogs = () => {
    setLogs([])
  }

  // Add some mock logs if there are none (for demonstration)
  useEffect(() => {
    if (logs.length === 0) {
      const mockLogs: LogEntry[] = [
        {
          timestamp: new Date().toISOString(),
          level: 'info',
          message: 'DuckLake system started successfully',
          metadata: { component: 'system' }
        },
        {
          timestamp: new Date(Date.now() - 1000).toISOString(),
          level: 'info',
          message: 'Connected to MinIO storage',
          metadata: { component: 'storage' }
        },
        {
          timestamp: new Date(Date.now() - 2000).toISOString(),
          level: 'info',
          message: 'DuckDB database initialized',
          metadata: { component: 'database' }
        }
      ]
      setLogs(mockLogs)
    }
  }, [logs.length])

  return (
    <Card className="col-span-1">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ScrollText className="h-5 w-5" />
            Live Logs
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsPaused(!isPaused)}
            >
              {isPaused ? (
                <Play className="h-4 w-4" />
              ) : (
                <Pause className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearLogs}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          ref={containerRef}
          className="bg-black text-green-400 p-4 rounded-lg font-mono text-sm max-h-96 overflow-y-auto"
        >
          {logs.length === 0 ? (
            <div className="text-gray-500 text-center py-4">
              {isPaused ? 'Logs paused' : 'Waiting for logs...'}
            </div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="mb-1 break-words">
                <span className="text-gray-500">
                  [{formatTimestamp(log.timestamp)}]
                </span>
                <span className={`ml-2 font-medium ${getLevelColor(log.level)}`}>
                  {log.level.toUpperCase()}
                </span>
                <span className="ml-2 text-green-400">
                  {log.message}
                </span>
                {log.job_id && (
                  <span className="ml-2 text-blue-400">
                    (job: {log.job_id})
                  </span>
                )}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
        {!autoScroll && (
          <div className="mt-2 text-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setAutoScroll(true)
                logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
              }}
              className="text-xs"
            >
              Scroll to bottom
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
} 