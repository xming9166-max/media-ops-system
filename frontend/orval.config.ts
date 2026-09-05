import { defineConfig } from 'orval'

export default defineConfig({
  api: {
    /*
     * 后端 OpenAPI 来源：
     * - 默认读取本地运行的后端（uvicorn 启动后访问 http://localhost:8000/openapi.json）
     * - 也可用环境变量 API_SPEC_URL 覆盖，或指向本地 JSON 文件
     */
    input: {
      target: process.env.API_SPEC_URL ?? 'http://localhost:8000/openapi.json',
    },
    output: {
      /*
       * 生成 React Query hooks + 类型。
       * 所有请求通过 mutator 走框架统一 HTTP 客户端（自动注入 token、解包 ApiEnvelope）。
       */
      target: './src/services/generated/api.ts',
      client: 'react-query',
      mode: 'split',
      schemas: './src/services/generated/schemas',
      override: {
        mutator: {
          path: './src/services/http/mutator.ts',
          name: 'orvalMutator',
        },
      },
    },
  },
})
