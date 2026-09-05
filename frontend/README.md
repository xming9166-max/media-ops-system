# Frontend

前后端分离基础开发框架前端项目。

## 当前状态

本项目已完成 React 前端基础工程搭建（骨架阶段），尚未实现任何业务功能。

已完成：

- React + Vite + TypeScript 工程搭建
- 分层目录结构落地 + 模块依赖方向硬化（ESLint 禁止共享层反向依赖 features）
- Feature 注册机制（manifest 自动发现路由与菜单，见 `src/features/`）
- 统一 HTTP 客户端（Axios：token 注入、401 处理、超时、ApiEnvelope 自动解包）
- TanStack Query 统一默认配置、Zustand store 模板、通用 hooks / utils / constants
- 通用 Layout 骨架 + 全局 ErrorBoundary + 路由懒加载（Suspense）
- orval 类型生成（`npm run gen:api`，产物 `src/services/generated/`）
- 前端开发规范建立（`frontend/AGENTS.md`）

## 技术栈

- React 19
- TypeScript
- Vite
- React Router
- Ant Design
- TanStack Query
- Zustand
- Axios
- ESLint
- Prettier
- orval（OpenAPI → TS 类型与 hooks）
- Vitest + Testing Library + jsdom

## 开发环境要求

- Node.js >= 24（推荐使用当前 LTS）
- npm >= 11

## 安装依赖

```bash
npm install
```

## 启动开发服务器

```bash
npm run dev
```

## 构建

```bash
npm run build
```

## 测试

```bash
npm run test
npm run test:watch
```

## Lint

```bash
npm run lint
```

## 目录结构

```text
frontend/
├── src/                  # 源码目录
│   ├── app/              # 应用装配层
│   │   ├── layout/       # 通用布局（AppLayout，装配层允许依赖 features）
│   │   ├── providers/    # 全局 Providers 组装
│   │   └── router/       # 路由入口（由 feature registry 生成）
│   ├── components/       # 可复用组件
│   │   ├── common/       # 通用组件（ErrorBoundary 等）
│   │   └── ...
│   ├── features/         # 业务模块（manifest.tsx 注册路由/菜单）
│   ├── pages/            # 页面
│   ├── services/         # 外部数据访问
│   │   ├── api/          # API 调用封装（可放 orval 生成的业务接口）
│   │   ├── http/         # HTTP 客户端（client / tokenStore / mutator）
│   │   ├── query/        # TanStack Query 统一配置
│   │   └── generated/    # orval 生成产物（勿手改，`npm run gen:api` 重新生成）
│   ├── stores/           # 全局 UI 状态（Zustand）
│   ├── hooks/            # 可复用 Hooks
│   ├── types/            # 共享类型
│   ├── utils/            # 工具函数
│   ├── constants/        # 常量
│   └── styles/           # 全局样式
├── .githooks/            # 前端提交前检查（由根 .githooks 路由调用）
├── public/               # 静态资源
└── tests/                # 测试目录
```

## 提交前检查（pre-commit 钩子）

仓库级 git 钩子由**仓库根 `.githooks/`** 统一路由：提交变更涉及 `frontend/**` 时，
自动对前端执行 `npm run lint`（format:check 在 Prettier 基线完成后启用），
**不通过则提交被拒绝**。激活方式见根目录说明 / `backend/README.md`。

手动执行同样检查（不经钩子）：

```bash
npm run lint
npm run format:check
```

## 环境变量

复制 `.env.example` 为 `.env` 后按需修改：

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## 详细规范

请阅读 `frontend/AGENTS.md`。
