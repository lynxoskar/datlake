// Core data types matching the backend API

export interface Job {
  id: string
  name: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

export interface JobRun {
  id: string
  job_id: string
  job_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at?: string
  error_message?: string
  metadata?: Record<string, any>
}

export interface Dataset {
  bucket_name: string
  name: string
  size: number
  last_modified: string
  content_type?: string
  metadata?: Record<string, any>
}

export interface Table {
  name: string
  schema: Record<string, string>
  row_count: number
  size_bytes: number
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

export interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'debug'
  message: string
  job_id?: string
  run_id?: string
  metadata?: Record<string, any>
}

// Event types for SSE
export interface JobEvent {
  type: 'job_created' | 'job_updated' | 'job_deleted' | 'run_started' | 'run_completed' | 'run_failed'
  job_id: string
  run_id?: string
  data: Job | JobRun
  timestamp: string
}

export interface DatasetEvent {
  type: 'dataset_created' | 'dataset_updated' | 'dataset_deleted'
  bucket_name: string
  object_name: string
  data: Dataset
  timestamp: string
}

export interface TableEvent {
  type: 'table_created' | 'table_updated' | 'table_deleted' | 'data_appended'
  table_name: string
  data: Table
  timestamp: string
}

// UI State types
export interface SearchResult {
  id: string
  type: 'job' | 'dataset' | 'table'
  name: string
  description?: string
  score: number
  data: Job | Dataset | Table
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  services: {
    api: boolean
    database: boolean
    storage: boolean
    cache: boolean
  }
  metrics: {
    active_jobs: number
    total_datasets: number
    total_tables: number
    storage_usage: number
  }
} 