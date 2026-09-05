/* 健康检查 API：薄封装层。
 *
 * 底层请求与类型来自 orval 生成的 services/generated（勿直接手写 httpClient.get）。
 * 本文件提供语义化的业务接口，供组件与 hooks 调用。
 *
 * 说明：orval 经 mutator 已解包 ApiEnvelope，调用返回即业务数据（如 { status: 'ok' }）。
 * 当前后端 health 未声明 response_model，生成类型不精确，此处按运行时结构断言。
 */

import { healthCheckApiV1HealthGet } from '@/services/generated/api'

export interface HealthStatus {
  status: string
}

export async function fetchHealth(): Promise<HealthStatus> {
  const data = await healthCheckApiV1HealthGet()
  return (data as unknown as HealthStatus) ?? { status: 'unknown' }
}
