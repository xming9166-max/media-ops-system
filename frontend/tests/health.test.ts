import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchHealth } from '@/services/api/health'
import { healthCheckApiV1HealthGet } from '@/services/generated/api'

vi.mock('@/services/generated/api', () => ({
  healthCheckApiV1HealthGet: vi.fn(),
}))

const mockedHealthGet = vi.mocked(healthCheckApiV1HealthGet)

afterEach(() => {
  mockedHealthGet.mockReset()
})

describe('fetchHealth', () => {
  it('calls generated healthCheckApiV1HealthGet and returns status', async () => {
    mockedHealthGet.mockResolvedValue({ status: 'ok' } as never)
    const result = await fetchHealth()
    expect(mockedHealthGet).toHaveBeenCalledTimes(1)
    expect(result).toEqual({ status: 'ok' })
  })
})
