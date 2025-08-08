# Frontend System Plan

## 1. Overview

The frontend is a modern web application built with Next.js 15 and the App Router, providing a comprehensive interface for the DuckLake data platform. It features a dashboard-style landing page that displays jobs, datasets, and tables with real-time updates via Server-Sent Events (SSE) and efficient data streaming using Arrow media types.

## 2. Core Technologies

### 2.1. Framework & Runtime
- **Framework:** Next.js 15.3.4+ with App Router
- **Runtime:** React 19.1+ with concurrent features
- **TypeScript:** 5.6+ for full type safety
- **Node.js:** 22+ for optimal performance

### 2.2. State Management & Data
- **Global UI State:** Zustand with per-request stores (SSR-safe)
- **Server State:** TanStack Query v5 for server state caching
- **Data Fetching:** Server Components for initial data, Server Actions for mutations
- **Real-time Updates:** EventSource API for SSE connections

### 2.3. Styling & UI
- **CSS Framework:** Tailwind CSS for utility-first styling
- **Component Library:** Radix UI primitives with custom design system
- **Icons:** Lucide React for consistent iconography
- **Animations:** Framer Motion for smooth transitions

### 2.4. Data Processing
- **Arrow Integration:** Apache Arrow JS for efficient data rendering
- **Data Visualization:** Observable Plot for charts and graphs
- **Table Virtualization:** TanStack Table v8 for large datasets
- **Search:** Fuse.js for client-side fuzzy search

## 3. Application Architecture

### 3.1. File Structure
```
frontend/
├── src/
│   ├── app/                    # App Router - pages and layouts
│   │   ├── (dashboard)/        # Route group for main app
│   │   │   ├── jobs/          # Jobs management pages
│   │   │   ├── datasets/      # Dataset browser pages  
│   │   │   ├── tables/        # Table viewer pages
│   │   │   └── page.tsx       # Landing page dashboard
│   │   ├── globals.css        # Global styles
│   │   └── layout.tsx         # Root layout
│   ├── components/            # Reusable components
│   │   ├── ui/               # Design system primitives
│   │   ├── layout/           # Layout components
│   │   └── features/         # Domain-specific components
│   ├── lib/                  # Core utilities
│   │   ├── api/              # API client and types
│   │   ├── arrow/            # Arrow data processing
│   │   ├── sse/              # Server-sent events utilities
│   │   └── utils/            # Helper functions
│   ├── stores/               # Zustand stores
│   ├── hooks/                # Custom React hooks
│   └── types/                # TypeScript type definitions
├── public/                   # Static assets
├── next.config.ts           # Next.js configuration
├── tailwind.config.ts       # Tailwind configuration
└── package.json            # Dependencies
```

### 3.2. API Client Generation
```typescript
// Generated from backend OpenAPI schema
import createClient from 'openapi-fetch'
import type { paths } from './generated/api'

export const apiClient = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL,
  credentials: 'include',
})
```

## 4. Landing Page Dashboard

### 4.1. Dashboard Layout
The landing page provides a comprehensive overview of the DuckLake system with real-time updates:

```typescript
// app/(dashboard)/page.tsx
export default async function DashboardPage() {
  // Fetch initial data in Server Component
  const [jobs, datasets, tables] = await Promise.all([
    apiClient.GET('/jobs'),
    apiClient.GET('/datasets'), 
    apiClient.GET('/tables')
  ])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6">
      <JobsOverview initialJobs={jobs.data} />
      <DatasetsOverview initialDatasets={datasets.data} />
      <TablesOverview initialTables={tables.data} />
      <LogsStream />
      <SystemHealth />
    </div>
  )
}
```

### 4.2. Real-time Components
Each dashboard section maintains real-time updates via SSE:

```typescript
// components/features/jobs-overview.tsx
'use client'
export function JobsOverview({ initialJobs }: { initialJobs: Job[] }) {
  const [jobs, setJobs] = useState(initialJobs)
  
  useSSE('/jobs/events', {
    onMessage: (event) => {
      const jobEvent = JSON.parse(event.data)
      setJobs(prev => updateJobsFromEvent(prev, jobEvent))
    }
  })

  return (
    <Card className="col-span-1">
      <CardHeader>
        <CardTitle>Jobs Overview</CardTitle>
      </CardHeader>
      <CardContent>
        <JobsTable jobs={jobs} />
      </CardContent>
    </Card>
  )
}
```

### 4.3. Search & Filtering
Universal search across jobs, datasets, and tables:

```typescript
// components/features/global-search.tsx
'use client'
export function GlobalSearch() {
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState([])
  
  const fuse = useMemo(() => new Fuse(
    [...jobs, ...datasets, ...tables],
    { 
      keys: ['name', 'description', 'tags'],
      threshold: 0.3 
    }
  ), [jobs, datasets, tables])

  const handleSearch = useDebouncedCallback((term: string) => {
    if (term.length > 2) {
      setSearchResults(fuse.search(term))
    }
  }, 300)

  return (
    <div className="relative">
      <Input
        placeholder="Search jobs, datasets, tables..."
        value={searchTerm}
        onChange={(e) => {
          setSearchTerm(e.target.value)
          handleSearch(e.target.value)
        }}
      />
      <SearchResults results={searchResults} />
    </div>
  )
}
```

## 5. Real-time Updates with SSE

### 5.1. SSE Hook Implementation
```typescript
// hooks/use-sse.ts
import { useEffect, useRef } from 'react'

export function useSSE(url: string, options: {
  onMessage?: (event: MessageEvent) => void
  onError?: (error: Event) => void
  onOpen?: (event: Event) => void
}) {
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    if (options.onOpen) {
      eventSource.onopen = options.onOpen
    }

    if (options.onMessage) {
      eventSource.onmessage = options.onMessage
    }

    if (options.onError) {
      eventSource.onerror = options.onError
    }

    return () => {
      eventSource.close()
    }
  }, [url])

  return {
    close: () => eventSourceRef.current?.close(),
    readyState: eventSourceRef.current?.readyState
  }
}
```

### 5.2. Live Job Logs
```typescript
// components/features/live-logs.tsx
'use client'
export function LiveLogs({ jobId, runId }: { jobId: string, runId: string }) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  
  useSSE(`/jobs/${jobId}/runs/${runId}/events`, {
    onMessage: (event) => {
      const logEvent = JSON.parse(event.data)
      setLogs(prev => [...prev, logEvent])
    }
  })

  return (
    <div className="bg-black text-green-400 p-4 rounded-lg font-mono text-sm">
      <div className="max-h-96 overflow-y-auto">
        {logs.map((log, index) => (
          <div key={index} className="mb-1">
            <span className="text-gray-500">{log.timestamp}</span>
            <span className="ml-2">{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

## 6. Arrow Media Type Integration

### 6.1. Arrow Data Processing
```typescript
// lib/arrow/processor.ts
import { Table, RecordBatch } from 'apache-arrow'

export class ArrowProcessor {
  static async processStreamResponse(response: Response): Promise<Table> {
    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const chunks: Uint8Array[] = []
    let done = false
    
    while (!done) {
      const { value, done: readerDone } = await reader.read()
      done = readerDone
      if (value) chunks.push(value)
    }

    const buffer = new Uint8Array(
      chunks.reduce((acc, chunk) => acc + chunk.length, 0)
    )
    let offset = 0
    for (const chunk of chunks) {
      buffer.set(chunk, offset)
      offset += chunk.length
    }

    return Table.from(buffer)
  }

  static convertToDisplayData(table: Table): any[] {
    return table.toArray().map(row => row.toJSON())
  }
}
```

### 6.2. Efficient Data Tables
```typescript
// components/features/arrow-table.tsx
'use client'
export function ArrowTable({ tableName }: { tableName: string }) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(`/api/tables/${tableName}/data`, {
          headers: { 'Accept': 'application/vnd.apache.arrow.stream' }
        })
        
        const arrowTable = await ArrowProcessor.processStreamResponse(response)
        const displayData = ArrowProcessor.convertToDisplayData(arrowTable)
        setData(displayData)
      } catch (error) {
        console.error('Error fetching Arrow data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [tableName])

  if (loading) return <TableSkeleton />

  return (
    <VirtualizedTable 
      data={data}
      columns={Object.keys(data[0] || {})}
      height={400}
    />
  )
}
```

## 7. State Management Architecture

### 7.1. UI State (Zustand)
```typescript
// stores/ui-store.ts
import { createStore } from 'zustand/vanilla'
import { immer } from 'zustand/middleware/immer'

export type UIState = {
  sidebarOpen: boolean
  currentView: 'jobs' | 'datasets' | 'tables'
  searchTerm: string
  selectedItems: Set<string>
}

export type UIActions = {
  toggleSidebar: () => void
  setCurrentView: (view: UIState['currentView']) => void
  setSearchTerm: (term: string) => void
  toggleSelectedItem: (id: string) => void
  clearSelection: () => void
}

export const createUIStore = (initState: Partial<UIState> = {}) => {
  return createStore<UIState & UIActions>()(
    immer((set) => ({
      sidebarOpen: true,
      currentView: 'jobs',
      searchTerm: '',
      selectedItems: new Set(),
      toggleSidebar: () => set(state => {
        state.sidebarOpen = !state.sidebarOpen
      }),
      setCurrentView: (view) => set(state => {
        state.currentView = view
      }),
      setSearchTerm: (term) => set(state => {
        state.searchTerm = term
      }),
      toggleSelectedItem: (id) => set(state => {
        if (state.selectedItems.has(id)) {
          state.selectedItems.delete(id)
        } else {
          state.selectedItems.add(id)
        }
      }),
      clearSelection: () => set(state => {
        state.selectedItems.clear()
      }),
      ...initState,
    }))
  )
}
```

### 7.2. Server State (TanStack Query)
```typescript
// lib/queries/jobs-queries.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

export const jobsQueryKeys = {
  all: ['jobs'] as const,
  lists: () => [...jobsQueryKeys.all, 'list'] as const,
  list: (filters: string) => [...jobsQueryKeys.lists(), filters] as const,
  details: () => [...jobsQueryKeys.all, 'detail'] as const,
  detail: (id: string) => [...jobsQueryKeys.details(), id] as const,
  runs: (id: string) => [...jobsQueryKeys.detail(id), 'runs'] as const,
}

export function useJobs() {
  return useQuery({
    queryKey: jobsQueryKeys.lists(),
    queryFn: async () => {
      const response = await apiClient.GET('/jobs')
      return response.data
    },
  })
}

export function useJobRuns(jobId: string) {
  return useQuery({
    queryKey: jobsQueryKeys.runs(jobId),
    queryFn: async () => {
      const response = await apiClient.GET('/jobs/{job_name}/runs', {
        params: { path: { job_name: jobId } }
      })
      return response.data
    },
  })
}
```

## 8. Performance Optimizations

### 8.1. Next.js 15 Configuration
```typescript
// next.config.ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  experimental: {
    reactCompiler: true,
    ppr: 'incremental',
    typedRoutes: true,
  },
  // Enable faster data fetching
  serverExternalPackages: ['apache-arrow'],
  // Optimize for dashboard workloads
  images: {
    domains: ['localhost'],
  },
  // Enable streaming for large datasets
  httpAgentOptions: {
    keepAlive: true,
  },
}

export default nextConfig
```

### 8.2. Virtualization for Large Data
```typescript
// components/ui/virtualized-table.tsx
import { useVirtualizer } from '@tanstack/react-virtual'

export function VirtualizedTable({ 
  data, 
  columns, 
  height = 400 
}: VirtualizedTableProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  
  const rowVirtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 35,
    overscan: 10,
  })

  return (
    <div ref={parentRef} className="h-96 overflow-auto">
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {rowVirtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <TableRow data={data[virtualRow.index]} columns={columns} />
          </div>
        ))}
      </div>
    </div>
  )
}
```

## 9. Development & Deployment

### 9.1. Development Setup
```bash
# Development commands
npm run dev          # Start development server
npm run build        # Build for production
npm run type-check   # TypeScript checking
npm run lint         # ESLint checking
npm run test         # Run tests
```

### 9.2. Key Dependencies
```json
{
  "dependencies": {
    "next": "^15.3.4",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "zustand": "^5.0.2",
    "@tanstack/react-query": "^5.0.0",
    "@tanstack/react-table": "^8.0.0",
    "@tanstack/react-virtual": "^3.0.0",
    "apache-arrow": "^16.0.0",
    "openapi-fetch": "^0.12.0",
    "tailwindcss": "^3.4.0",
    "@radix-ui/react-*": "^1.0.0",
    "framer-motion": "^11.0.0",
    "lucide-react": "^0.400.0",
    "fuse.js": "^7.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^18.3.0",
    "typescript": "^5.6.0",
    "eslint": "^8.0.0",
    "eslint-config-next": "^15.3.4"
  }
}
```

## 10. User Experience Features

### 10.1. Progressive Enhancement
- **Server-First:** Initial page load with Server Components
- **Client Enhancement:** Real-time updates and interactions
- **Offline Support:** Service Worker for basic offline functionality
- **Error Boundaries:** Graceful error handling at component level

### 10.2. Accessibility
- **ARIA Labels:** Comprehensive screen reader support
- **Keyboard Navigation:** Full keyboard accessibility
- **Focus Management:** Logical focus flow
- **Color Contrast:** WCAG AA compliance

### 10.3. Mobile Responsiveness
- **Responsive Grid:** Adaptive layouts for all screen sizes
- **Touch Optimization:** Mobile-friendly interactions
- **Performance:** Optimized for mobile networks

This comprehensive frontend system plan provides a modern, efficient, and user-friendly interface for the DuckLake data platform, leveraging the latest Next.js 15 features while maintaining excellent performance and developer experience.
