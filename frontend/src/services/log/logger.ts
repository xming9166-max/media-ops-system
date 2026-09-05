/* 前端统一日志入口。
 *
 * - 分级：debug / info / warn / error
 * - 开关：VITE_LOG_LEVEL 控制最小输出级别（off 关闭全部）
 * - 统一出口：未来接错误上报（Sentry 等）只改本文件
 *
 * 注意：前端日志用于开发调试与前端错误定位，不承担与后端链路关联的
 * request_id（请求链路 ID 由 nginx 统一生成与管理）。
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'off'

const LEVEL_ORDER: Record<Exclude<LogLevel, 'off'>, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
}

function resolveLevel(): LogLevel {
  const raw = import.meta.env.VITE_LOG_LEVEL
  return (raw as LogLevel | undefined) ?? 'info'
}

const currentLevel = resolveLevel()

function isEnabled(level: Exclude<LogLevel, 'off'>): boolean {
  if (currentLevel === 'off') return false
  return LEVEL_ORDER[level] >= LEVEL_ORDER[currentLevel]
}

export const logger = {
  debug: (...args: unknown[]) => {
    if (isEnabled('debug')) console.debug('[debug]', ...args)
  },
  info: (...args: unknown[]) => {
    if (isEnabled('info')) console.info('[info]', ...args)
  },
  warn: (...args: unknown[]) => {
    if (isEnabled('warn')) console.warn('[warn]', ...args)
  },
  error: (...args: unknown[]) => {
    if (isEnabled('error')) console.error('[error]', ...args)
  },
}
