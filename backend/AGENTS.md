# Backend AGENTS.md

## Scope

本规则适用于 `backend/`，必须同时遵守根目录 `AGENTS.md`。本文件只包含后端专属规则。

---

## Python 环境

Python 项目统一使用 `uv` 管理。

禁止：`pip install`、`pip3 install`、`python -m venv`、使用系统 Python 安装项目依赖。

统一使用：`uv add <package>`、`uv sync`、`uv run <command>`。

Python 版本由 `.python-version` 管理（当前 Python 3.12）。虚拟环境必须位于 `backend/.venv/`。

---

## Architecture

后端业务依赖方向：

```
Router
    ↓
Service
    ↓
Repository
    ↓
Database
```

依赖只能按照上述方向流动，禁止反向依赖。

各层职责：

- **Router**：HTTP 层（接收请求、参数处理、Schema 校验、调用 Service、返回 Response）
- **Service**：业务逻辑（业务规则、流程、状态转换、事务边界、并发控制）
- **Repository**：数据访问（查询、新增、版本创建、数据库访问封装）
- **Schema**：Request 校验、Response 结构、序列化/反序列化
- **Model**：ORM 映射、表结构、字段、数据库关系

> Schema 与 Model 是模块内横向角色（位置见 Module Boundaries 推荐结构），不属于纵向调用链。

技术栈：FastAPI / SQLAlchemy / MySQL / Redis / Celery

---

## Module Boundaries

- 跨模块调用通过明确的 Service / Interface / Domain 能力完成
- 业务模块推荐结构：`app/modules/<domain>/{router,service,repository,schema,model}.py`

---

## Data Retention Strategy（业务数据保留策略）

涉及业务数据生命周期（历史保留、删除）的功能，**禁止擅自决定**保留策略。
必须向用户呈现以下三种候选并说明适用场景与代价，由**用户判定**：

| 策略         | 适用场景                     | 代价                                             |
| ------------ | ---------------------------- | ------------------------------------------------ |
| 硬删除       | 数据无保留价值、允许物理删除 | 物理 DELETE，不可恢复                            |
| 软删除       | 短期可恢复、低审计要求       | `is_deleted` / `deleted_at` 标记，查询需处处过滤 |
| 指针版本控制 | 完整历史、可审计、可回滚     | 版本表持续增长，读取需指针 join                  |

- 判定为**指针版本控制** → 必读 `docs/business/data-versioning/AGENTS.md`，严格执行其全部约束
- 判定为**硬删除 / 软删除** → 按用户明确确认的方案实施（满足根 AGENTS.md 删除需用户确认的要求）
- 未获得用户判定前，禁止实现任何一种策略

---

## Transaction & Concurrency

**事务一致性**：具有业务关联的数据变更必须全部成功或全部回滚。

**事务边界**：由 Service 控制，Repository 不应自行创建独立事务。

**短事务**：禁止在事务中执行耗时操作（调用 AI、等待第三方 API）。

**外部调用模式**：需要第三方服务时 → 创建任务 → COMMIT → Celery/后台执行 → 第三方 API →
获得结果 → 短事务内创建新版本/更新状态 → COMMIT。

**锁原则**：

- 默认优先使用乐观锁（version 检查）
- 仅高竞争资源使用悲观锁（`SELECT ... FOR UPDATE`）
- 优先行锁，避免表锁
- 涉及多资源时保持统一加锁顺序，防止死锁

**死锁处理**：回滚 → 识别异常 → 有限重试（指数退避）→ 超过最大重试次数后失败。禁止无限重试。

**幂等**：所有可能重复执行的操作必须考虑幂等（创建任务、Celery Task、Webhook、第三方回调等）。可使用唯一业务 ID、幂等 Key、UNIQUE、状态机、version。

**状态机**：复杂业务状态必须通过明确状态机管理，状态转换由 Service 完成。

---

## Database Constraints

关键数据一致性不能只依赖 Python，必须尽可能使用数据库约束：PRIMARY KEY、UNIQUE、FOREIGN KEY、NOT NULL、CHECK、INDEX。

业务唯一数据优先使用数据库 UNIQUE，禁止只依赖 `if not exists: create()`。

---

## High Concurrency

优先：无状态 API + 连接池 + 索引 + 缓存 + 异步任务。

避免：大范围锁 + 锁表 + N+1 查询。

（短事务、乐观锁、幂等、耗时任务外移等见 Transaction & Concurrency。）

---

## API Response

- 所有接口必须通过 `ApiResponse` 返回统一契约（格式见 `docs/http/api-contract.md`），
  禁止业务代码自行拼装响应 JSON
- 错误统一通过抛出 `ApiException` 表达（未捕获异常由全局处理器兜底），
  禁止在业务层自行构造错误响应
- 全局处理器已覆盖：`RequestValidationError` → 422/40000；未捕获异常 → 500/50000

---

## Configuration

- 新增配置必须加入 `app/core/config.py` 的 `Settings` 字段，并同步更新 `env/*.example` 模板
- 禁止在代码内硬编码环境相关值（端口、地址、开关等）
- 运行环境与读取方式（`APP_ENV` / `CONFIG_SOURCE`）见 `backend/README.md`「运行环境配置」

---

## Testing

新增后端功能必须考虑测试，至少覆盖：正常流程、参数错误、业务异常、数据库异常、并发冲突、重复请求、事务回滚。

涉及版本控制的功能，测试要求见 `docs/business/data-versioning/AGENTS.md`。
