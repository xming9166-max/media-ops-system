import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchHealth } from '@/services/api/health'

vi.mock('@/services/http/client', () => {
  const mockedGet = vi.fn()
  const mockedAxios = { get: mockedGet }
  return {
    httpClient: mockedAxios,
  }
})

import { httpClient } from '@/services/http/client'

const mockedGet = vi.mocked(httpClient.get)

afterEach(() => {
  mockedGet.mockReset()
})

describe('fetchHealth', () => {
  it('GETs /api/v1/health and returns status', async () => {
    mockedGet.mockResolvedValue({ data: { status: 'ok' } })
    const result = await fetchHealth()
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/health')
    expect(result).toEqual({ status: 'ok' })
  })
})