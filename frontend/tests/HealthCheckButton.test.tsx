import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import HealthCheckButton from '@/components/common/HealthCheckButton'
import { fetchHealth } from '@/services/api/health'

vi.mock('@/services/api/health', () => ({
  fetchHealth: vi.fn(),
}))

const mockedFetchHealth = vi.mocked(fetchHealth)

describe('HealthCheckButton', () => {
  it('starts with error marker (❌)', () => {
    render(<HealthCheckButton />)
    expect(screen.getByRole('status')).toHaveTextContent('❌')
  })

  it('turns success marker (✅) after health check passes', async () => {
    mockedFetchHealth.mockResolvedValue({ status: 'ok' })

    render(<HealthCheckButton />)
    fireEvent.click(screen.getByRole('button', { name: '测试后端连接' }))

    expect(await screen.findByRole('status')).toHaveTextContent('✅')
    expect(mockedFetchHealth).toHaveBeenCalledTimes(1)
  })

  it('keeps error marker (❌) when health check fails', async () => {
    mockedFetchHealth.mockRejectedValue(new Error('network error'))

    render(<HealthCheckButton />)
    fireEvent.click(screen.getByRole('button', { name: '测试后端连接' }))

    expect(await screen.findByRole('status')).toHaveTextContent('❌')
  })
})