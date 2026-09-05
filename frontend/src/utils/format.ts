/* 通用格式化工具。 */

/** 数字千分位格式化：1234567 → 1,234,567 */
export function formatNumber(value: number | string): string {
  const num = typeof value === 'string' ? Number(value) : value
  if (Number.isNaN(num)) return String(value)
  return num.toLocaleString('en-US')
}

/**
 * 时长（毫秒）格式化为可读文本。
 * 例：formatDuration(61000) → 1分1秒
 */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '-'
  const totalSeconds = Math.round(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}小时${minutes}分`
  if (minutes > 0) return `${minutes}分${seconds}秒`
  return `${seconds}秒`
}
