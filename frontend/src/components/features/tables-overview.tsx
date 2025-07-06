'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { useSSE } from '@/hooks/use-sse'
import { Table, TableEvent } from '@/types'
import { Table as TableIcon, Database, BarChart3 } from 'lucide-react'

interface TablesOverviewProps {
  initialTables: Table[]
}

function formatNumber(num: number) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export function TablesOverview({ initialTables }: TablesOverviewProps) {
  const [tables, setTables] = useState<Table[]>(initialTables)

  // Real-time updates via SSE
  useSSE(`${process.env.NEXT_PUBLIC_API_URL}/tables/events`, {
    onMessage: (event) => {
      try {
        const tableEvent: TableEvent = JSON.parse(event.data)
        setTables(prev => {
          const updated = [...prev]
          const existingIndex = updated.findIndex(t => t.name === tableEvent.table_name)
          
          if (tableEvent.type === 'table_deleted') {
            return updated.filter(t => t.name !== tableEvent.table_name)
          }
          
          if (existingIndex >= 0) {
            updated[existingIndex] = tableEvent.data
          } else {
            updated.push(tableEvent.data)
          }
          
          return updated
        })
      } catch (error) {
        console.error('Error parsing table event:', error)
      }
    },
    onError: (error) => {
      console.error('SSE connection error:', error)
    }
  })

  const totalRows = tables.reduce((sum, table) => sum + table.row_count, 0)
  const totalSize = tables.reduce((sum, table) => sum + table.size_bytes, 0)

  return (
    <Card className="col-span-1">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TableIcon className="h-5 w-5" />
          Tables Overview
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Tables summary */}
          <div className="grid grid-cols-2 gap-2">
            <div className="text-center p-3 bg-cyan-50 rounded-lg">
              <div className="text-2xl font-bold text-cyan-600">
                {tables.length}
              </div>
              <div className="text-sm text-cyan-600">Tables</div>
            </div>
            <div className="text-center p-3 bg-indigo-50 rounded-lg">
              <div className="text-2xl font-bold text-indigo-600">
                {formatNumber(totalRows)}
              </div>
              <div className="text-sm text-indigo-600">Total Rows</div>
            </div>
          </div>
          
          {/* Total size */}
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Database className="h-4 w-4 text-gray-500" />
              <span className="text-sm font-medium">Total Size</span>
            </div>
            <div className="text-lg font-bold text-gray-900">
              {formatFileSize(totalSize)}
            </div>
          </div>
          
          {/* Recent tables */}
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900">Recent Tables</h4>
            {tables.slice(0, 5).map((table) => (
              <div 
                key={table.name}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-gray-500" />
                  <div>
                    <div className="text-sm font-medium">{table.name}</div>
                    <div className="text-xs text-gray-500">
                      {Object.keys(table.schema).length} columns
                    </div>
                  </div>
                </div>
                <div className="text-xs text-gray-500">
                  {formatNumber(table.row_count)} rows
                </div>
              </div>
            ))}
            {tables.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">
                No tables found
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
} 