import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useDebounce } from '@/hooks/useDebounce'

describe('useDebounce', () => {
  it('延迟后返回最新值', async () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 100), {
      initialProps: { value: 'a' },
    })
    // 初始值立即可见
    expect(result.current).toBe('a')

    // 更新值，未超时前仍是旧值
    rerender({ value: 'b' })
    expect(result.current).toBe('a')

    // 等待 debounce 到期后变成新值
    await waitFor(() => expect(result.current).toBe('b'))
  })

  it('频繁更新只取最后一次值', async () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 80), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'b' })
    rerender({ value: 'c' })
    rerender({ value: 'd' })

    await waitFor(() => expect(result.current).toBe('d'))
  })

  it('delayMs 为 0 时尽快同步（下一事件循环）', async () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 0), {
      initialProps: { value: 'x' },
    })
    rerender({ value: 'y' })
    await waitFor(() => expect(result.current).toBe('y'))
  })
})
