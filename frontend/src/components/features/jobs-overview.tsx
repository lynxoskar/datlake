'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useSSE } from '@/hooks/use-sse'
import { Job, JobEvent } from '@/types'
import { Database, Play, CheckCircle, XCircle, Clock, Zap } from 'lucide-react'

interface JobsOverviewProps {
  initialJobs: Job[]
}

function getStatusIcon(status: Job['status']) {
  switch (status) {
    case 'running':
      return <Zap className="h-4 w-4 text-synthwave-cyan animate-pulse" />
    case 'completed':
      return <CheckCircle className="h-4 w-4 text-synthwave-green" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-synthwave-pink" />
    default:
      return <Clock className="h-4 w-4 text-synthwave-yellow animate-pulse" />
  }
}

function getStatusColor(status: Job['status']) {
  switch (status) {
    case 'running':
      return 'bg-synthwave-cyan/20 text-synthwave-cyan border-synthwave-cyan/50'
    case 'completed':
      return 'bg-synthwave-green/20 text-synthwave-green border-synthwave-green/50'
    case 'failed':
      return 'bg-synthwave-pink/20 text-synthwave-pink border-synthwave-pink/50'
    default:
      return 'bg-synthwave-yellow/20 text-synthwave-yellow border-synthwave-yellow/50'
  }
}

export function JobsOverview({ initialJobs }: JobsOverviewProps) {
  const [jobs, setJobs] = useState<Job[]>(initialJobs)

  // Real-time updates via SSE
  useSSE(`${process.env.NEXT_PUBLIC_API_URL}/jobs/events`, {
    onMessage: (event) => {
      try {
        const jobEvent: JobEvent = JSON.parse(event.data)
        setJobs(prev => {
          const updated = [...prev]
          const existingIndex = updated.findIndex(j => j.id === jobEvent.job_id)
          
          if (existingIndex >= 0) {
            updated[existingIndex] = jobEvent.data as Job
          } else {
            updated.push(jobEvent.data as Job)
          }
          
          return updated
        })
      } catch (error) {
        console.error('Error parsing job event:', error)
      }
    },
    onError: (error) => {
      console.error('SSE connection error:', error)
    }
  })

  const statusCounts = jobs.reduce((acc, job) => {
    acc[job.status] = (acc[job.status] || 0) + 1
    return acc
  }, {} as Record<Job['status'], number>)

  return (
    <div className="synthwave-card col-span-1 loading-border">
      <CardHeader className="border-b border-synthwave-cyan/30">
        <CardTitle className="flex items-center gap-2 text-synthwave-cyan font-cyber">
          <Database className="h-5 w-5 animate-pulse" />
          JOBS CONTROL
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <div className="space-y-6">
          {/* Status summary */}
          <div className="grid grid-cols-2 gap-3">
            <div className="terminal p-4 rounded-lg text-center">
              <div className="terminal-content">
                <div className="text-3xl font-black font-cyber text-synthwave-cyan animate-pulse-neon">
                  {statusCounts.running || 0}
                </div>
                <div className="text-sm text-synthwave-cyan/70 font-mono">RUNNING</div>
              </div>
            </div>
            <div className="terminal p-4 rounded-lg text-center">
              <div className="terminal-content">
                <div className="text-3xl font-black font-cyber text-synthwave-green animate-pulse-neon">
                  {statusCounts.completed || 0}
                </div>
                <div className="text-sm text-synthwave-green/70 font-mono">COMPLETED</div>
              </div>
            </div>
          </div>
          
          {/* Recent jobs */}
          <div className="space-y-3">
            <h4 className="font-cyber font-bold text-synthwave-pink text-sm tracking-wider">
              ACTIVE PROCESSES
            </h4>
            <div className="space-y-2">
              {jobs.slice(0, 5).map((job) => (
                <div 
                  key={job.id}
                  className="flex items-center justify-between p-3 bg-synthwave-dark/50 border border-synthwave-cyan/30 rounded-lg hover:border-synthwave-pink/50 transition-all duration-300 group"
                >
                  <div className="flex items-center gap-3">
                    {getStatusIcon(job.status)}
                    <div>
                      <span className="text-sm font-mono font-bold text-synthwave-cyan group-hover:text-synthwave-pink transition-colors">
                        {job.name.toUpperCase()}
                      </span>
                      <div className="text-xs text-synthwave-cyan/50 font-mono">
                        PID: {job.id.slice(0, 8)}
                      </div>
                    </div>
                  </div>
                  <Badge className={`${getStatusColor(job.status)} border font-mono text-xs font-bold`}>
                    {job.status.toUpperCase()}
                  </Badge>
                </div>
              ))}
              {jobs.length === 0 && (
                <div className="terminal p-4 rounded-lg">
                  <div className="terminal-content text-center">
                    <p className="text-sm text-synthwave-cyan/50 font-mono">
                      NO ACTIVE PROCESSES
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </div>
  )
} 