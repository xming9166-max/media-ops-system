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

技术栈：FastAPI / SQLAlchemy / MySQL / Redis / Celery

---

## Module Boundaries

- 业务模块保持独立，禁止跨模块直接访问内部实现
- 跨模块调用通过明确的 Service / Interface / Domain 能力完成
- 禁止循环依赖
- 业务模块推荐结构：`app/modules/<domain>/{router,service,repository,schema,model}.py`

---

## Data Version

需要保留历史的数据必须版本化。

- 默认读取最新版本，历史版本需显式指定
- 变更时保留旧版本，创建新版本（version + 1）
- 禁止 UPDATE 直接覆盖历史版本
- 推荐统一封装 `get_latest(...)` / `get_version(..., version=N)`

---

## Transaction & Concurrency

**事务一致性**：具有业务关联的数据变更必须全部成功或全部回滚。

**事务边界**：由 Service 控制，Repository 不应自行创建独立事务。

**短事务**：禁止在事务中执行耗时操作（调用 AI、等待第三方 API）。

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

优先：无状态 API + 连接池 + 索引 + 短事务 + 乐观锁 + 幂等 + 缓存 + 异步任务。

避免：长事务 + 大范围锁 + 锁表 + 同步执行耗时任务 + N+1 查询。

---

## External API

禁止在数据库事务中长时间等待外部服务。推荐：创建任务 → COMMIT → Celery → 第三方 API → 获得结果 → 短事务 → 创建新版本/更新状态 → COMMIT。

---

## Data Deletion

Backend 禁止任何形式的数据删除：禁止 `DELETE FROM`、`session.delete()`、`repository.delete()`、`deleted_at`、`is_deleted` 等软删除机制。涉及删除需求时必须停止并向用户确认。

---

## Testing

新增后端功能必须考虑测试，至少覆盖：正常流程、参数错误、业务异常、数据库异常、并发冲突、重复请求、事务回滚。

涉及版本控制的功能必须测试版本链（version 1 → 2 → 3）并验证历史版本不会丢失。
