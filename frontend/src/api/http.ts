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
  keepalive?: boolean
  // Bỏ qua cơ chế tự refresh-và-thử-lại khi gặp 401 — bắt buộc dùng cho
  // chính request login/refresh/logout, nếu không sẽ tạo vòng lặp gọi lại
  // refresh vô hạn khi refresh token cũng đã hết hạn/không hợp lệ.
  skipAuthRetry?: boolean
}

// Đăng ký bởi tầng khởi tạo app (main.ts) sau khi auth store đã sẵn sàng —
// khi 1 request bất kỳ nhận lỗi 401 (access token JWT hết hạn sau
// ACCESS_TOKEN_EXPIRE_MINUTES, xem backend/app/core/config.py), apiRequest
// gọi handler này để lấy access token mới rồi thử lại request đúng 1 lần,
// thay vì hiện thẳng lỗi "Invalid authentication credentials." (nguyên văn
// từ backend) lên UI. Handler trả về `null` nếu refresh thất bại thật sự
// (refresh token cũng hết hạn/không hợp lệ) — khi đó request gốc vẫn ném lỗi
// 401 ban đầu như cũ.
type UnauthorizedHandler = () => Promise<string | null>

let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler
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

async function performRequest<T>(
  path: string,
  options: RequestOptions,
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
    keepalive: options.keepalive ?? false,
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

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  try {
    return await performRequest<T>(path, options)
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status === 401 &&
      !options.skipAuthRetry &&
      unauthorizedHandler
    ) {
      const refreshedToken = await unauthorizedHandler()
      if (refreshedToken) {
        return performRequest<T>(path, { ...options, accessToken: refreshedToken })
      }
    }
    throw error
  }
}
