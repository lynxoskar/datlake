'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { useSSE } from '@/hooks/use-sse'
import { Dataset, DatasetEvent } from '@/types'
import { FolderOpen, File, HardDrive } from 'lucide-react'

interface DatasetsOverviewProps {
  initialDatasets: Dataset[]
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export function DatasetsOverview({ initialDatasets }: DatasetsOverviewProps) {
  const [datasets, setDatasets] = useState<Dataset[]>(initialDatasets)

  // Real-time updates via SSE
  useSSE(`${process.env.NEXT_PUBLIC_API_URL}/datasets/events`, {
    onMessage: (event) => {
      try {
        const datasetEvent: DatasetEvent = JSON.parse(event.data)
        setDatasets(prev => {
          const updated = [...prev]
          const existingIndex = updated.findIndex(d => 
            d.bucket_name === datasetEvent.bucket_name && 
            d.name === datasetEvent.object_name
          )
          
          if (datasetEvent.type === 'dataset_deleted') {
            return updated.filter(d => 
              !(d.bucket_name === datasetEvent.bucket_name && d.name === datasetEvent.object_name)
            )
          }
          
          if (existingIndex >= 0) {
            updated[existingIndex] = datasetEvent.data
          } else {
            updated.push(datasetEvent.data)
          }
          
          return updated
        })
      } catch (error) {
        console.error('Error parsing dataset event:', error)
      }
    },
    onError: (error) => {
      console.error('SSE connection error:', error)
    }
  })

  const totalSize = datasets.reduce((sum, dataset) => sum + dataset.size, 0)
  const buckets = new Set(datasets.map(d => d.bucket_name)).size

  return (
    <Card className="col-span-1">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FolderOpen className="h-5 w-5" />
          Datasets Overview
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Storage summary */}
          <div className="grid grid-cols-2 gap-2">
            <div className="text-center p-3 bg-purple-50 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">
                {datasets.length}
              </div>
              <div className="text-sm text-purple-600">Files</div>
            </div>
            <div className="text-center p-3 bg-orange-50 rounded-lg">
              <div className="text-2xl font-bold text-orange-600">
                {buckets}
              </div>
              <div className="text-sm text-orange-600">Buckets</div>
            </div>
          </div>
          
          {/* Storage usage */}
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <HardDrive className="h-4 w-4 text-gray-500" />
              <span className="text-sm font-medium">Total Storage</span>
            </div>
            <div className="text-lg font-bold text-gray-900">
              {formatFileSize(totalSize)}
            </div>
          </div>
          
          {/* Recent datasets */}
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900">Recent Files</h4>
            {datasets.slice(0, 5).map((dataset) => (
              <div 
                key={`${dataset.bucket_name}/${dataset.name}`}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-2">
                  <File className="h-4 w-4 text-gray-500" />
                  <div>
                    <div className="text-sm font-medium">{dataset.name}</div>
                    <div className="text-xs text-gray-500">{dataset.bucket_name}</div>
                  </div>
                </div>
                <div className="text-xs text-gray-500">
                  {formatFileSize(dataset.size)}
                </div>
              </div>
            ))}
            {datasets.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">
                No datasets found
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
} 