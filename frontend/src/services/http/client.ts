import axios from 'axios'

export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

/** 后端统一响应契约（见 docs/http/api-contract.md） */
export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
  request_id: string
}

/** 业务错误：业务 code 非 0，携带契约中的 request_id 便于排查 */
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

httpClient.interceptors.response.use(
  (response) => {
    if (!isApiEnvelope(response.data)) {
      return response
    }
    const { code, message, data, request_id } = response.data
    if (code !== 0) {
      return Promise.reject(new ApiError(code, message, request_id))
    }
    // 自动解包：调用方拿到的 response.data 即契约中的 data
    response.data = data
    return response
  },
  (error: unknown) => {
    if (axios.isAxiosError(error) && isApiEnvelope(error.response?.data)) {
      const { code, message, request_id } = error.response.data
      return Promise.reject(new ApiError(code, message, request_id))
    }
    return Promise.reject(error)
  },
)
