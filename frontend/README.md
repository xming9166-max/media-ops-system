# Frontend

自媒体运营系统前端项目。

## 当前状态

本项目已完成 React 前端基础工程搭建（骨架阶段），尚未实现任何业务功能。

已完成：

- React + Vite + TypeScript 工程搭建
- 分层目录结构落地
- 统一 HTTP 客户端（Axios，Base URL 通过环境变量配置）
- 前端开发规范建立（`frontend/AGENTS.md`）

## 技术栈

- React 19
- TypeScript
- Vite
- React Router
- Ant Design
- TanStack Query
- Zustand（已安装，暂无实际 Store）
- Axios
- ESLint
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
│   ├── app/              # 应用级配置（Router、Providers）
│   ├── components/       # 可复用组件
│   │   ├── common/       # 通用组件
│   │   └── layout/       # 布局组件
│   ├── features/         # 业务模块
│   ├── pages/            # 页面
│   ├── services/         # 外部数据访问
│   │   ├── api/          # API 调用封装
│   │   └── http/         # HTTP 客户端
│   ├── stores/           # 跨组件状态
│   ├── hooks/            # 可复用 Hooks
│   ├── types/            # 共享类型
│   ├── utils/            # 工具函数
│   ├── constants/        # 常量
│   └── styles/           # 全局样式
├── public/               # 静态资源
└── tests/                # 测试目录
```

## 环境变量

复制 `.env.example` 为 `.env` 后按需修改：

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## 详细规范

请阅读 `frontend/AGENTS.md`。
