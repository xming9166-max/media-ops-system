/* orval mutator：让生成代码走框架统一 HTTP 客户端。
 *
 * orval 以 (url, options) 两参数调用本函数，options 为 fetch 风格 RequestInit。
 * 这里归一化为 axios 配置，从而自动获得 token 注入、401 刷新、
 * 错误归一化、ApiEnvelope 解包等能力。
 */

import type { AxiosRequestConfig } from 'axios'

import { httpClient } from './client'

type OrvalRequestConfig = Omit<RequestInit, 'body'> & { body?: unknown }

/** 将 fetch 风格 headers 归一化为普通对象。 */
function normalizeHeaders(headers: HeadersInit | undefined): Record<string, string> | undefined {
  if (!headers) return undefined
  if (Array.isArray(headers)) return Object.fromEntries(headers)
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    return Object.fromEntries(headers.entries())
  }
  return headers as Record<string, string>
}

export async function orvalMutator<T>(url: string, options?: OrvalRequestConfig): Promise<T> {
  const { body, headers, signal, ...rest } = options ?? {}
  const config: AxiosRequestConfig = {
    url,
    ...rest,
    ...(body !== undefined ? { data: body } : {}),
    ...(normalizeHeaders(headers) ? { headers: normalizeHeaders(headers) } : {}),
    ...(signal ? { signal } : {}),
  }
  const response = await httpClient.request<T>(config)
  // 拦截器已解包 ApiEnvelope，response.data 即业务数据
  return response.data
}
