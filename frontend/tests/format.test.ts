import { describe, expect, it } from 'vitest'
import { formatDuration, formatNumber } from '@/utils/format'

describe('formatNumber', () => {
  it('整数千分位', () => {
    expect(formatNumber(1234567)).toBe('1,234,567')
  })

  it('小数保留小数位', () => {
    expect(formatNumber(1234.56)).toBe('1,234.56')
  })

  it('非法输入返回原样字符串', () => {
    expect(formatNumber('abc')).toBe('abc')
  })
})

describe('formatDuration', () => {
  it('不足 1 秒显示为秒', () => {
    expect(formatDuration(500)).toBe('1秒')
  })

  it('分钟级', () => {
    expect(formatDuration(61000)).toBe('1分1秒')
  })

  it('小时级', () => {
    expect(formatDuration(3661000)).toBe('1小时1分')
  })

  it('非法输入返回占位', () => {
    expect(formatDuration(-1)).toBe('-')
    expect(formatDuration(Number.NaN)).toBe('-')
  })
})
