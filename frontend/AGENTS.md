# Frontend AGENTS.md

## Scope

本规则适用于 `frontend/`，必须同时遵守根目录 `AGENTS.md`。本文件只包含前端专属规则。

---

## Architecture

前端采用分层架构，各层职责：

- **app**：应用配置、Router、Providers
- **pages**：页面组合和路由入口
- **features**：业务领域逻辑
- **components**：可复用 UI
- **services**：外部数据访问
- **stores**：客户端全局状态
- **hooks**：可复用逻辑
- **types**：共享类型
- **utils**：纯工具函数
- **constants**：常量
- **styles**：全局样式

技术栈：UI → React / TS / Build → Vite / Routing → React Router / UI Components → Ant Design / Server State → TanStack Query / Client Global State → Zustand

---

## Module Boundaries

- Feature 默认不直接依赖其他 Feature 的内部文件
- 不跨模块使用相对路径访问内部实现
- 公共能力通过共享模块或明确导出的公共接口访问
- 禁止循环依赖
- 不要为了复用而过早抽象

---

## Features

业务代码优先放在 `features/<domain>/` 下。

- Feature 保持业务内聚，内部实现默认私有
- 公共代码只有真正具备复用价值后才提升到共享层
- 禁止为了"看起来模块化"而拆分本应在一起的代码

---

## Components / Pages

- **pages**：路由入口、页面组合，禁止堆积复杂业务逻辑
- **components/common**：真正通用的 UI 组件
- **components/layout**：布局组件
- **features/*/components**：业务专属组件，放在 Feature 内
- 禁止巨型组件（超过 300 行应考虑拆分）

---

## State

状态管理分类：

- **Local UI State** → React State
- **Global Client State** → Zustand
- **Server State** → TanStack Query

禁止把服务器数据复制到 Zustand。

---

## API

分层规则：

```
Feature/Page
    ↓
services/api
    ↓
services/http
    ↓
Backend
```

- 禁止在组件中创建 HTTP Client
- 禁止在业务代码中硬编码 API Base URL
- 所有 API 请求通过统一 HTTP 客户端

---

## TypeScript

- 禁止滥用 `any`
- Feature 私有类型放在 Feature 内
- 共享类型放在 `types/`
- API 类型与 UI 类型差异明显时分离
- 禁止用 `@ts-ignore` 忽略错误

---

## Dependencies

- 新增依赖前必须检查现有方案是否可满足
- 禁止为简单功能引入大型库
- 禁止引入功能重复的依赖
- 修改依赖必须更新 lock file

---

## Naming

核心命名规则：

- 组件：`PascalCase` → `UserProfile.tsx`
- Hook：`camelCase` → `useUser.ts`
- Store：`camelCase` → `userStore.ts`
- 类型：`lowercase` → `user.types.ts`
- 常量：`UPPER_SNAKE_CASE`
- 事件处理：`handle` 前缀
- 布尔值：`is`/`has`/`can` 前缀

---

## Environment Variables

- 禁止提交敏感信息
- API Base URL 等配置通过环境变量管理
- 环境变量不能散落在业务代码中
- 必须提供 `.env.example` 作为模板

---

## Testing

- 测试行为，不测试实现
- 测试用例独立
- 覆盖正常流程、边界情况、异常情况
- 测试文件：`*.test.ts(x)` 就近放置或统一放在 `tests/`
