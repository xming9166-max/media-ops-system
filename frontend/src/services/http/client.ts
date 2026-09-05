import axios from 'axios'

import { BUSINESS_CODE } from '@/constants'
import { getAccessToken } from './tokenStore'
import { normalizeHttpError, triggerErrorAction } from './errorHandler'

// 统一超时（毫秒），可用环境变量覆盖
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 15000)

export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
})

/** 后端统一响应契约（见 docs/http/api-contract.md） */
export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
  request_id: string
}

/** 统一错误：业务错误（业务 code 非 0）或归一化的网络/HTTP 层错误，携带 code / request_id */
export class ApiError extends Error {
  readonly code: number
  readonly requestId?: string

  constructor(code: number, message: string, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.requestId = requestId
  }
}

function isApiEnvelope(value: unknown): value is ApiEnvelope {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return typeof candidate.code === 'number' && typeof candidate.message === 'string'
}

/** 触发业务码对应的默认行为（code→action 映射见 errorHandler） */
function dispatch(code: number, message: string, requestId?: string): void {
  triggerErrorAction(code, message, requestId)
}

// 请求拦截器：自动注入 Bearer token（token 来源可注入，见 tokenStore）
httpClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

httpClient.interceptors.response.use(
  (response) => {
    if (!isApiEnvelope(response.data)) {
      return response
    }
    const { code, message, data, request_id } = response.data
    if (code !== 0) {
      const apiError = new ApiError(code, message, request_id)
      // 业务失败：触发该业务码对应的默认行为
      dispatch(code, message, request_id)
      return Promise.reject(apiError)
    }
    // 自动解包：调用方拿到的 response.data 即契约中的 data
    response.data = data
    return response
  },
  (error: unknown) => {
    // 取消请求（组件卸载 / 竞态 abort）透传原始错误，不做归一化，
    // 避免被误判为业务/网络错误；上层（如 TanStack Query）通过 signal.aborted 静默处理。
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }
    // 有契约响应体 → 业务错误（含 40100 等），归一到 ApiError 并触发行为
    if (axios.isAxiosError(error) && isApiEnvelope(error.response?.data)) {
      const { code, message, request_id } = error.response.data
      const apiError = new ApiError(code, message, request_id)
      dispatch(code, message, request_id)
      return Promise.reject(apiError)
    }
    // 无契约响应体：网络错误 / 超时 / 其他 HTTP 错误 → 归一化后转 ApiError
    const info = normalizeHttpError(error)
    const apiError = new ApiError(info.code, info.message, info.requestId)
    // HTTP 401 且无契约体时也走未认证行为
    if (error instanceof axios.AxiosError && error.response?.status === 401) {
      dispatch(BUSINESS_CODE.UNAUTHORIZED, info.message, info.requestId)
    }
    return Promise.reject(apiError)
  },
)
