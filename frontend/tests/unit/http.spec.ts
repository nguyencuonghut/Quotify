import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiRequest, ApiError } from '@/api/http'

describe('http client (apiRequest)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('parses standard JSON response with 200 OK', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => JSON.stringify({ data: 'success' }),
    }
    const fetchSpy = vi
      .spyOn(global, 'fetch')
      .mockResolvedValue(mockResponse as Response)

    const result = await apiRequest<{ data: string }>('/test')

    expect(result).toEqual({ data: 'success' })
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/test'),
      expect.any(Object),
    )
  })

  it('returns null for 204 No Content response', async () => {
    const mockResponse = {
      ok: true,
      status: 204,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => '',
    }
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResponse as Response)

    const result = await apiRequest<void>('/logout')

    expect(result).toBeNull()
  })

  it('returns null for 200 OK with empty response body', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => '',
    }
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResponse as Response)

    const result = await apiRequest<unknown>('/empty-json')

    expect(result).toBeNull()
  })

  it('throws ApiError with error detail from response', async () => {
    const mockResponse = {
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => JSON.stringify({ detail: 'Invalid input parameters.' }),
    }
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResponse as Response)

    await expect(apiRequest('/failed')).rejects.toThrow(ApiError)

    try {
      await apiRequest('/failed')
    } catch (error: unknown) {
      expect(error).toBeInstanceOf(ApiError)
      if (!(error instanceof ApiError)) {
        throw error
      }

      expect(error.status).toBe(400)
      expect(error.message).toBe('Invalid input parameters.')
    }
  })

  it('includes Authorization Bearer header when accessToken is provided', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => JSON.stringify({}),
    }
    const fetchSpy = vi
      .spyOn(global, 'fetch')
      .mockResolvedValue(mockResponse as Response)

    await apiRequest('/me', { accessToken: 'secret-token' })

    const lastCall = fetchSpy.mock.calls[0]
    const requestOptions = lastCall[1] as RequestInit
    const headers = requestOptions.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer secret-token')
  })
})
