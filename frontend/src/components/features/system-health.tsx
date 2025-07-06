'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SystemHealth as SystemHealthType } from '@/types'
import { 
  Activity, 
  CheckCircle, 
  AlertCircle, 
  XCircle, 
  Server, 
  Database, 
  HardDrive, 
  Zap 
} from 'lucide-react'

export function SystemHealth() {
  const [health, setHealth] = useState<SystemHealthType>({
    status: 'healthy',
    services: {
      api: true,
      database: true,
      storage: true,
      cache: true,
    },
    metrics: {
      active_jobs: 0,
      total_datasets: 0,
      total_tables: 0,
      storage_usage: 0,
    },
  })

  useEffect(() => {
    const checkHealth = async () => {
      try {
        // In a real implementation, this would call a health check endpoint
        // For now, we'll simulate the health check
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`).catch(() => null)
        
        if (response && response.ok) {
          const healthData = await response.json()
          setHealth(healthData)
        } else {
          // Fallback to mock healthy status when backend is not running
          setHealth(prev => ({
            ...prev,
            status: 'degraded',
            services: {
              api: false,
              database: true,
              storage: true,
              cache: true,
            },
          }))
        }
      } catch (error) {
        console.error('Health check failed:', error)
        setHealth(prev => ({
          ...prev,
          status: 'unhealthy',
          services: {
            api: false,
            database: false,
            storage: false,
            cache: false,
          },
        }))
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30 seconds

    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status: SystemHealthType['status']) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'degraded':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />
      case 'unhealthy':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <Activity className="h-5 w-5 text-gray-500" />
    }
  }

  const getStatusColor = (status: SystemHealthType['status']) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-800'
      case 'degraded':
        return 'bg-yellow-100 text-yellow-800'
      case 'unhealthy':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const services = [
    { name: 'API', key: 'api' as const, icon: Server },
    { name: 'Database', key: 'database' as const, icon: Database },
    { name: 'Storage', key: 'storage' as const, icon: HardDrive },
    { name: 'Cache', key: 'cache' as const, icon: Zap },
  ]

  return (
    <Card className="col-span-1">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          System Health
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Overall status */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2">
              {getStatusIcon(health.status)}
              <span className="font-medium">Overall Status</span>
            </div>
            <Badge className={getStatusColor(health.status)}>
              {health.status}
            </Badge>
          </div>
          
          {/* Services status */}
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900">Services</h4>
            {services.map((service) => (
              <div 
                key={service.name}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-2">
                  <service.icon className="h-4 w-4 text-gray-500" />
                  <span className="text-sm font-medium">{service.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {health.services[service.key] ? (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span className="text-sm text-gray-500">
                    {health.services[service.key] ? 'Online' : 'Offline'}
                  </span>
                </div>
              </div>
            ))}
          </div>
          
          {/* Key metrics */}
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900">Key Metrics</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="p-2 bg-blue-50 rounded-lg">
                <div className="text-blue-600 font-medium">Active Jobs</div>
                <div className="text-blue-800 font-bold">{health.metrics.active_jobs}</div>
              </div>
              <div className="p-2 bg-purple-50 rounded-lg">
                <div className="text-purple-600 font-medium">Datasets</div>
                <div className="text-purple-800 font-bold">{health.metrics.total_datasets}</div>
              </div>
              <div className="p-2 bg-cyan-50 rounded-lg">
                <div className="text-cyan-600 font-medium">Tables</div>
                <div className="text-cyan-800 font-bold">{health.metrics.total_tables}</div>
              </div>
              <div className="p-2 bg-orange-50 rounded-lg">
                <div className="text-orange-600 font-medium">Storage</div>
                <div className="text-orange-800 font-bold">
                  {Math.round(health.metrics.storage_usage / 1024 / 1024)} MB
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
} 