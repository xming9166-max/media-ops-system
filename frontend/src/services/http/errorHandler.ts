/* HTTP 错误统一处理：错误形态归一化 + 业务码 → 默认行为映射。
 *
 * 目标：调用方只需面对「统一错误」一种形态；框架对常见业务码给出默认行为
 * （如 40100 → 通知未认证、40900 → 提示冲突），业务可通过注入覆盖。
 */

import { BUSINESS_CODE } from '@/constants'
import { logger } from '@/services/log/logger'

/** 统一网络/HTTP 层错误（非业务 ApiError 时使用） */
export interface HttpErrorInfo {
  /** 归一的错误码：优先业务码，否则 fallback 到 HTTP 层约定码 */
  code: number
  message: string
  /** 原始错误（axios error 等），便于排查 */
  cause?: unknown
  /** 请求 ID（后端响应头 X-Request-ID 回传），便于排查 */
  requestId?: string
}

/** HTTP 层约定错误码（非后端业务码，仅前端内部使用） */
export const HTTP_ERROR_CODE = {
  NETWORK: -1,
  TIMEOUT: -2,
  HTTP_STATUS: -3,
} as const

/**
 * 判断是否为网络/超时类错误（无 HTTP 响应）。
 * 超时在 axios 中以 ECONNABORTED / ETIMEDOUT 标识。
 */
export function isNetworkLikeError(error: unknown): boolean {
  if (!(typeof error === 'object' && error !== null)) return false
  const e = error as { code?: string }
  return e.code === 'ECONNABORTED' || e.code === 'ETIMEDOUT' || e.code === 'ERR_NETWORK'
}

/** 从后端返回的契约结构中解析 request_id（兜底失败返回 undefined） */
function extractRequestId(error: unknown): string | undefined {
  const data = (error as { response?: { data?: { request_id?: string } } })?.response?.data
  return data?.request_id
}

/** 归一化错误信息为统一结构 */
export function normalizeHttpError(error: unknown): HttpErrorInfo {
  // 网络断开 / 超时：无 HTTP 响应体
  if (isNetworkLikeError(error)) {
    const isTimeout = (error as { code?: string }).code === 'ECONNABORTED'
    return {
      code: isTimeout ? HTTP_ERROR_CODE.TIMEOUT : HTTP_ERROR_CODE.NETWORK,
      message: isTimeout ? '请求超时，请稍后重试' : '网络异常，请检查网络连接',
      cause: error,
    }
  }

  // 有 HTTP 响应
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status !== undefined) {
    return {
      code: HTTP_ERROR_CODE.HTTP_STATUS,
      message: `请求失败（HTTP ${status}）`,
      cause: error,
      requestId: extractRequestId(error),
    }
  }

  // 其他（如取消请求）
  return {
    code: HTTP_ERROR_CODE.HTTP_STATUS,
    message: '请求失败',
    cause: error,
  }
}

/* ---------- 业务码 → 默认行为映射（可注入覆盖） ---------- */

type ErrorAction = (info: HttpErrorInfo, message: string) => void

interface ErrorActions {
  unauthorized?: ErrorAction // 40100
  forbidden?: ErrorAction // 40300
  conflict?: ErrorAction // 40900
  [code: number]: ErrorAction | undefined
}

const errorActions: ErrorActions = {
  [BUSINESS_CODE.UNAUTHORIZED]: (info, message) => {
    logger.warn('[http] 未认证:', message, 'requestId:', info.requestId ?? '-')
  },
  [BUSINESS_CODE.FORBIDDEN]: (info, message) => {
    logger.warn('[http] 无权限:', message, 'requestId:', info.requestId ?? '-')
  },
  [BUSINESS_CODE.CONFLICT]: (info, message) => {
    logger.warn('[http] 数据冲突:', message, 'requestId:', info.requestId ?? '-')
  },
}

/** 注入自定义错误动作（可覆盖默认行为；业务在装配时调用） */
export function setErrorAction(code: number, action: ErrorAction): void {
  errorActions[code] = action
}

/** 触发某业务码对应的默认动作（无则忽略，仅打日志兜底） */
export function triggerErrorAction(code: number, message: string, requestId?: string): void {
  const action = errorActions[code]
  if (action) {
    action({ code, message, requestId }, message)
  } else {
    logger.info('[http] 业务错误:', message, 'code:', code, 'requestId:', requestId ?? '-')
  }
}
