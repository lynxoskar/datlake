import createClient from 'openapi-fetch'

// For now, we'll use a simple client configuration
// Later, we'll replace this with the generated OpenAPI client

export const apiClient = createClient({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  credentials: 'include',
})

// Basic API functions until we generate the OpenAPI client
export const api = {
  // Jobs API
  async getJobs() {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`)
    if (!response.ok) throw new Error('Failed to fetch jobs')
    return response.json()
  },

  async getJob(jobName: string) {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${jobName}`)
    if (!response.ok) throw new Error('Failed to fetch job')
    return response.json()
  },

  async getJobRuns(jobName: string) {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${jobName}/runs`)
    if (!response.ok) throw new Error('Failed to fetch job runs')
    return response.json()
  },

  // Datasets API
  async getDatasets() {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/datasets`)
    if (!response.ok) throw new Error('Failed to fetch datasets')
    return response.json()
  },

  async getDataset(bucketName: string) {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/datasets/${bucketName}`)
    if (!response.ok) throw new Error('Failed to fetch dataset')
    return response.json()
  },

  // Tables API
  async getTables() {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/tables`)
    if (!response.ok) throw new Error('Failed to fetch tables')
    return response.json()
  },

  async getTable(tableName: string) {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/tables/${tableName}`)
    if (!response.ok) throw new Error('Failed to fetch table')
    return response.json()
  },

  async getTableData(tableName: string, format: 'json' | 'arrow' = 'json') {
    const headers: HeadersInit = {}
    if (format === 'arrow') {
      headers['Accept'] = 'application/vnd.apache.arrow.stream'
    }
    
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/tables/${tableName}/data`, {
      headers,
    })
    if (!response.ok) throw new Error('Failed to fetch table data')
    
    if (format === 'arrow') {
      return response // Return response for Arrow processing
    }
    
    return response.json()
  },
} 