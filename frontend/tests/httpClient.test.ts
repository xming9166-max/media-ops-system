import type { AxiosResponse } from 'axios'
import { AxiosError, CanceledError } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, httpClient } from '@/services/http/client'
import { HTTP_ERROR_CODE, setErrorAction } from '@/services/http/errorHandler'
import { clearAccessToken, setAccessToken } from '@/services/http/tokenStore'
import { BUSINESS_CODE } from '@/constants'

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

/** 捕获请求配置，便于断言拦截器行为 */
function captureRequest() {
  let captured: unknown
  httpClient.defaults.adapter = async (config) => {
    captured = config
    return {
      data: { code: 0, message: 'ok', data: null, request_id: 'r' },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    } as AxiosResponse
  }
  return () => captured
}

/** 重置 setErrorAction 的默认动作，避免跨用例泄漏 */
function resetUnauthorizedAction() {
  setErrorAction(BUSINESS_CODE.UNAUTHORIZED, (info, message) => {
    console.warn('[http] 未认证请求被拒绝:', message, 'requestId:', info.requestId ?? '-')
  })
}

beforeEach(() => {
  clearAccessToken()
  resetUnauthorizedAction()
})

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

  it('HTTP 错误且响应体不是契约结构时归一化为 ApiError（HTTP 层错误码）', async () => {
    // 模拟真实网络错误：adapter reject 一个带 response 的 AxiosError（非契约体）
    httpClient.defaults.adapter = async (config) => {
      const response = {
        data: 'Not Found',
        status: 404,
        statusText: 'Not Found',
        headers: {},
        config,
      } as AxiosResponse
      throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, undefined, response)
    }
    const error: unknown = await httpClient.get('/api/v1/missing').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe(HTTP_ERROR_CODE.HTTP_STATUS)
  })
})

describe('httpClient 请求拦截器（token 注入）', () => {
  it('未设置 token 时不带 Authorization 头', async () => {
    const getCaptured = captureRequest()
    await httpClient.get('/api/v1/health')
    const config = getCaptured() as { headers: { Authorization?: string } }
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('设置 token 后自动注入 Bearer 头', async () => {
    setAccessToken('token-abc')
    const getCaptured = captureRequest()
    await httpClient.get('/api/v1/health')
    const config = getCaptured() as { headers: { Authorization?: string } }
    expect(config.headers.Authorization).toBe('Bearer token-abc')
  })

  it('清除 token 后不再注入', async () => {
    setAccessToken('token-abc')
    clearAccessToken()
    const getCaptured = captureRequest()
    await httpClient.get('/api/v1/health')
    const config = getCaptured() as { headers: { Authorization?: string } }
    expect(config.headers.Authorization).toBeUndefined()
  })
})

describe('httpClient 业务码 action 分发', () => {
  it('业务 code=40100 时触发已注入的未认证 action', async () => {
    const action = vi.fn()
    setErrorAction(BUSINESS_CODE.UNAUTHORIZED, action)
    mockAdapter({
      status: 200,
      data: { code: 40100, message: '未登录或登录已过期', data: null, request_id: 'r-401' },
    })

    const error: unknown = await httpClient.get('/api/v1/protected').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(action).toHaveBeenCalledTimes(1)
    expect(action).toHaveBeenCalledWith(
      expect.objectContaining({ code: BUSINESS_CODE.UNAUTHORIZED, requestId: 'r-401' }),
      expect.stringContaining('未登录'),
    )
  })

  it('业务 code=50000 不触发 40100 的 action', async () => {
    const action = vi.fn()
    setErrorAction(BUSINESS_CODE.UNAUTHORIZED, action)
    mockAdapter({
      status: 500,
      data: { code: 50000, message: '服务器内部错误', data: null, request_id: 'r-500' },
    })

    await httpClient.get('/api/v1/boom').catch(() => undefined)
    expect(action).not.toHaveBeenCalled()
  })
})

describe('httpClient 请求取消', () => {
  it('取消请求透传原始 CanceledError（不归一到 ApiError）', async () => {
    // 模拟组件卸载/竞态触发 abort：adapter reject 一个 CanceledError
    httpClient.defaults.adapter = async (config) => {
      throw new CanceledError('canceled', config)
    }
    const error: unknown = await httpClient.get('/api/v1/slow').catch((e: unknown) => e)
    // 透传原始取消错误，未被归一化成 ApiError
    expect(error).toBeInstanceOf(CanceledError)
    expect(error).not.toBeInstanceOf(ApiError)
  })
})
