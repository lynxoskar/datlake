import { Table, tableFromIPC } from 'apache-arrow'

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

    return tableFromIPC(buffer)
  }

  static convertToDisplayData(table: Table): any[] {
    return table.toArray().map(row => row.toJSON())
  }

  static getTableSchema(table: Table): Record<string, string> {
    const schema: Record<string, string> = {}
    table.schema.fields.forEach(field => {
      schema[field.name] = field.type.toString()
    })
    return schema
  }

  static async fetchArrowData(url: string, options: RequestInit = {}): Promise<Table> {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Accept': 'application/vnd.apache.arrow.stream',
        ...options.headers,
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch Arrow data: ${response.statusText}`)
    }

    return this.processStreamResponse(response)
  }
} 