import { JobsOverview } from '@/components/features/jobs-overview'
import { DatasetsOverview } from '@/components/features/datasets-overview'
import { TablesOverview } from '@/components/features/tables-overview'
import { SystemHealth } from '@/components/features/system-health'
import { LogsStream } from '@/components/features/logs-stream'
import { api } from '@/lib/api/client'

export default async function DashboardPage() {
  // Fetch initial data in Server Component
  const [jobs, datasets, tables] = await Promise.allSettled([
    api.getJobs().catch(() => []),
    api.getDatasets().catch(() => []),
    api.getTables().catch(() => []),
  ])

  // Extract the data from the settled promises
  const jobsData = jobs.status === 'fulfilled' ? jobs.value : []
  const datasetsData = datasets.status === 'fulfilled' ? datasets.value : []
  const tablesData = tables.status === 'fulfilled' ? tables.value : []

  return (
    <div className="space-y-8 relative">
      {/* Terminal header */}
      <div className="relative">
        <div className="terminal p-6 rounded-lg">
          <div className="terminal-content">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 bg-synthwave-green rounded-full animate-pulse"></div>
              <span className="text-xs font-mono text-synthwave-green/70">
                ducklake@system:~$
              </span>
            </div>
            <h1 className="text-4xl font-cyber font-black text-synthwave-cyan animate-pulse-neon mb-2">
              DUCKLAKE CONTROL
            </h1>
            <p className="text-synthwave-cyan/60 font-mono text-lg">
              &gt; DATA PLATFORM OPERATIONAL STATUS
            </p>
          </div>
        </div>
      </div>
      
      {/* Main dashboard grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <JobsOverview initialJobs={jobsData} />
        <DatasetsOverview initialDatasets={datasetsData} />
        <TablesOverview initialTables={tablesData} />
      </div>
      
      {/* System monitoring */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SystemHealth />
        <LogsStream />
      </div>
      
      {/* Terminal footer */}
      <div className="terminal p-4 rounded-lg">
        <div className="terminal-content">
          <div className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-4">
              <span className="text-synthwave-green">
                UPTIME: {Math.floor(Date.now() / 1000 / 60)} MINUTES
              </span>
              <span className="text-synthwave-cyan">
                MEMORY: 2.4GB / 8GB
              </span>
              <span className="text-synthwave-pink">
                CPU: 15.7%
              </span>
            </div>
            <div className="text-synthwave-cyan/50">
              PRESS [ESC] TO EXIT
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 