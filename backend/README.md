# media-ops-system Backend

FastAPI 后端服务。

## 快速开始

```bash
# 安装依赖（uv 管理，Python 3.12）
uv sync

# 启动开发服务（默认 dev 环境，读取 env/.env.dev）
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# 运行测试
.venv/bin/python -m pytest -q
```

## 提交前检查（pre-commit 钩子）

仓库内置 Git 钩子：每次 `git commit` 前自动对后端代码执行 `ruff format --check` + `ruff check`，
**任一不通过则提交被拒绝**。

克隆仓库后激活钩子（每个本地仓库执行一次）：

```bash
git config core.hooksPath backend/.githooks
```

手动执行同样的检查（不经钩子）：

```bash
cd backend
.venv/bin/ruff format .        # 格式化
.venv/bin/ruff check --fix .   # lint 并自动修复
```

紧急绕过（应极少使用）：`git commit --no-verify`。
前端代码检查：`cd frontend && npm run lint`（当前未纳入钩子）。

## 运行环境配置

环境文件统一放在 `backend/env/` 目录，由环境变量 `APP_ENV` 控制运行环境（缺省 `dev`）。

配置读取方式由环境变量 `CONFIG_SOURCE` 控制（`file` / `env`），
**未显式设置时按环境推断**：`dev` → `file`；`test` / `pro` → `env`。

| APP_ENV | CONFIG_SOURCE | 行为 |
|---|---|---|
| `dev`（默认） | 未设置 → `file` | 读取 `env/.env.dev` |
| `dev` | `env` | 只读进程环境变量 |
| `test` | 未设置 → `env` | 只读进程环境变量 |
| `test` | `file` | 读取 `env/.env.test` |
| `pro` | 未设置 → `env` | 只读进程环境变量（生产推荐） |
| `pro` | `file` | 读取 `env/.env.pro` |

取值优先级：**进程环境变量 > 配置文件 > 字段默认值**。
`APP_ENV` / `CONFIG_SOURCE` 取值非法时启动直接报错（快速失败）。

### 配置键

每个环境各有一份模板：`env/.env.dev.example`、`env/.env.test.example`、`env/.env.pro.example`。
使用时复制为对应环境的真实文件（如 `cp env/.env.dev.example env/.env.dev`）。

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `APP_ENV` | `dev`/`test`/`pro` | `dev` | 运行环境 |
| `CONFIG_SOURCE` | `file`/`env` | 按环境推断 | 配置读取方式 |
| `APP_NAME` | `str` | `media-ops-system` | 应用名 |
| `DEBUG` | `bool` | `false` | 调试模式 |
| `API_V1_PREFIX` | `str` | `/api/v1` | API 路由前缀 |
| `CORS_ORIGINS` | `list[str]`（JSON 数组） | 本地 5173 来源 | 允许跨域的前端来源 |

### 日志配置键

日志系统说明与字段规范见 `docs/middleware/logging.md`。全部日志配置键（`LOG_ENABLED` / `LOG_OUTPUT` / `LOG_LEVEL` / `LOG_DIR` / `LOG_ACCESS_BODY` / `LOG_BODY_MAX_BYTES` / `LOG_SLOW_REQUEST_MS` / `LOG_TRUST_PROXY_HEADERS`）的类型、默认值、说明与推断规则，以 `docs/middleware/logging.md` 为唯一权威来源，env 模板 `env/*.example` 同步；本处不再重复列表。


输出文件（`FILE` / `BOTH` 时位于 `backend/logs/`）：

- `access.log`：HTTP 访问日志（`log_type=access`，级别 `< ERROR`）
- `app.log`：业务 INFO / WARNING 日志（`log_type=app`，级别 `< ERROR`）
- `error.log`：ERROR / CRITICAL 与异常堆栈（任意 `log_type`，级别 `>= ERROR`）

所有输出均为**单行 JSON**，字段恒定，可直接对接 Loki / ELK / Grafana / OpenTelemetry。

### 示例

```bash
# dev：读取 env/.env.dev（缺省行为）
.venv/bin/uvicorn app.main:app --port 8000

# test：临时切回文件模式（如 CI 中想用 env/.env.test）
APP_ENV=test CONFIG_SOURCE=file .venv/bin/uvicorn app.main:app --port 8000

# pro：只从环境变量读取（容器部署推荐）
APP_ENV=pro APP_NAME=media-ops CORS_ORIGINS='["https://ops.example.com"]' .venv/bin/uvicorn app.main:app --port 8000
```

> 注意：`env/` 下只有 `*.example` 模板入库；`.env.dev`、`.env.test`、`.env.pro`
> 等真实环境文件已被 `.gitignore` 忽略。禁止提交真实密钥。

