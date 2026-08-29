# Frontend

自媒体运营系统前端项目。

## 当前状态

本项目当前处于工程初始化阶段。

已完成：

- 目录结构规划
- 前端开发规范建立（`frontend/AGENTS.md`）

待完成：

- React + Vite 基础骨架搭建
- 依赖安装
- 基础组件库集成

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
├── tests/                # 测试目录
└── docs/                 # 文档
```

## 技术栈

- React
- TypeScript

具体构建工具、UI 库、状态管理库等由后续骨架阶段确定。

## 详细规范

请阅读 `frontend/AGENTS.md`。
