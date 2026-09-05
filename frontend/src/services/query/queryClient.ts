/* TanStack Query 统一配置工厂。
 *
 * 每个业务项目在装配层调用 createQueryClient() 创建实例并注入 AppProviders。
 * 统一默认：staleTime、retry 策略、focus 重新拉取。
 */

import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/services/http/client'

interface CreateQueryClientOptions {
  staleTime?: number
}

export function createQueryClient(options: CreateQueryClientOptions = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // 默认 30s 内认为数据新鲜，减少重复请求
        staleTime: options.staleTime ?? 30_000,
        // 业务错误（ApiError）不重试，避免无效风暴；网络/超时等未知错误最多重试 1 次
        retry: (failureCount, error) => {
          if (failureCount >= 1) return false
          return !(error instanceof ApiError)
        },
        // 后台标签页重新聚焦时静默刷新（配合 staleTime 不会刷太频繁）
        refetchOnWindowFocus: true,
      },
      mutations: {
        retry: false,
      },
    },
  })
}
