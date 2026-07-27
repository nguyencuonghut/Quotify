import { getApiBaseUrl } from '@/api/runtime'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions {
  accessToken?: string | null
  body?: BodyInit | null
  headers?: HeadersInit
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
}

function resolveErrorMessage(payload: unknown, fallback: string): string {
  if (
    typeof payload === 'object' &&
    payload !== null &&
    'detail' in payload &&
    typeof payload.detail === 'string'
  ) {
    return payload.detail
  }

  return fallback
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  if (options.accessToken) {
    headers.set('Authorization', `Bearer ${options.accessToken}`)
  }

  if (
    options.body &&
    !headers.has('Content-Type') &&
    !(options.body instanceof FormData)
  ) {
    headers.set('Content-Type', 'application/json')
  }

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: options.method ?? 'GET',
    body: options.body ?? null,
    headers,
    credentials: 'include',
  })

  const hasNoBody = response.status === 204 || response.status === 205
  const contentType = response.headers.get('content-type') ?? ''
  const isJson = contentType.includes('application/json')
  let payload: unknown = null

  if (isJson && !hasNoBody) {
    try {
      const text = await response.text()
      payload = text ? JSON.parse(text) : null
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    throw new ApiError(
      resolveErrorMessage(
        payload,
        response.statusText || 'API request failed.',
      ),
      response.status,
    )
  }

  return payload as T
}
