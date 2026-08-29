import type { AxiosResponse } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import { ApiError, httpClient } from '@/services/http/client'

type AdapterResult = { status: number; data: unknown }

const originalAdapter = httpClient.defaults.adapter

/** 用自定义 adapter 模拟后端响应，走真实的 axios 拦截器链路 */
function mockAdapter(result: AdapterResult) {
  httpClient.defaults.adapter = async (config) =>
    ({
      data: result.data,
      status: result.status,
      statusText: 'OK',
      headers: {},
      config,
    }) as AxiosResponse
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter
})

describe('httpClient 统一响应拦截器', () => {
  it('code=0 时自动解包并返回 data', async () => {
    mockAdapter({
      status: 200,
      data: { code: 0, message: 'ok', data: { status: 'ok' }, request_id: 'r-1' },
    })
    const { data } = await httpClient.get<{ status: string }>('/api/v1/health')
    expect(data).toEqual({ status: 'ok' })
  })

  it('HTTP 200 但业务 code 非 0 时抛出 ApiError（含 requestId）', async () => {
    mockAdapter({
      status: 200,
      data: { code: 40400, message: '资源不存在', data: null, request_id: 'r-2' },
    })
    const error: unknown = await httpClient.get('/api/v1/health').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe(40400)
    expect((error as ApiError).message).toBe('资源不存在')
    expect((error as ApiError).requestId).toBe('r-2')
  })

  it('HTTP 错误且响应体为契约结构时转换为 ApiError', async () => {
    mockAdapter({
      status: 500,
      data: { code: 50000, message: '服务器内部错误', data: null, request_id: 'r-3' },
    })
    const error: unknown = await httpClient.get('/api/v1/boom').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe(50000)
    expect((error as ApiError).requestId).toBe('r-3')
  })

  it('HTTP 错误且响应体不是契约结构时保留原始错误', async () => {
    mockAdapter({ status: 404, data: 'Not Found' })
    const error: unknown = await httpClient.get('/api/v1/missing').catch((e: unknown) => e)
    expect(error).not.toBeInstanceOf(ApiError)
  })
})
