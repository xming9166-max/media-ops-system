# 日志系统规范

统一、可配置、可追踪的日志基础设施，覆盖访问日志、业务日志和错误日志。

## 总体架构

```
请求进入
  ├─ RequestIDMiddleware（已有）→ 生成/复用 request_id (ContextVar)
  ├─ AccessLogMiddleware     → 记录访问日志（单行 JSON）
  ├─ 路由处理
  │     ├─ 业务正常 → 业务日志 (get_app_logger)
  │     ├─ ApiException → 业务日志 (WARNING, success=false)
  │     └─ 未捕获异常 → 错误日志 (ERROR, 含堆栈)
  └─ 三类日志 → 按 LOG_OUTPUT 输出到控制台或 backend/logs/
```

**核心机制**：日志格式化器(Formatter)在输出瞬间从 ContextVar 读取 `request_id` / `trace_id` / `task_id` / `user_id` 并注入每一条日志。一次请求产生的访问/业务/错误日志拥有同一个 `request_id`，排查时按 `request_id` grep 即可串起整条链路。

## 技术约束

- **标准库 `logging`，零新增依赖**（不引入 Loguru / Structlog）
- **统一单行 JSON 输出**（console 与 file 完全一致），字段恒定，可直接对接 Loki / ELK / Grafana / OpenTelemetry
- **不改动现有 request_id 基础设施**（`app/core/request_id.py` 不动）
- **不改变现有 API Response 契约**（`ApiResponse` / `docs/http/api-contract.md` 不动）
- **不修改业务逻辑**，只增加日志能力
- **日志基础设施与业务代码解耦**

## 配置开关

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `LOG_ENABLED` | `bool` | `true` | 主开关；`false` 时项目 logger 不输出（不动全局 `logging`，保留调用能力） |
| `LOG_OUTPUT` | `console`/`file`/`both` | 按环境推断（`dev`→`console`，`test`/`pro`→`file`） | 输出位置 |
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO` | 输出最低级别 |
| `LOG_DIR` | `str` | `logs` | 文件输出目录（相对 `backend/` 运行目录），`FILE` / `BOTH` 生效 |
| `LOG_ACCESS_BODY` | `bool` | 按环境推断（`dev`→`true`，`test`/`pro`→`false`） | 是否采样请求/响应 Body |
| `LOG_BODY_MAX_BYTES` | `int` | `4096` | Body 采样上限（字节），超出截断并打 `truncated` 标记 |
| `LOG_SLOW_REQUEST_MS` | `int` | `1000` | 慢请求阈值（毫秒），超时访问日志升 `WARNING` 并打标；`0` 关闭 |
| `LOG_TRUST_PROXY_HEADERS` | `bool` | 按环境推断（`dev`/`test`→`false`，`pro`→`true`） | 是否信任 `X-Forwarded-For` 取客户端 IP |

各键未显式设置时按运行环境推断默认值，显式设置优先。详见 `backend/README.md`。

## 统一 Structured Log Schema

### 公共字段（三类日志恒定输出）

| 字段 | 类型 | 说明 |
|---|---|---|
| `timestamp` | string (ISO8601) | UTC 时间戳 |
| `level` | string | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `logger` | string | 来源模块（`__name__`） |
| `log_type` | string | `access` / `app` / `error` |
| `app_name` | string | 应用名（取自 Settings） |
| `app_env` | string | 运行环境 |
| `trace_id` | string | 完整业务链路 ID（缺省回落到 request_id，v1 预留） |
| `request_id` | string | 当前 HTTP 请求 ID |
| `task_id` | string | 异步任务 ID（v1 预留，留空待接入 Celery） |
| `user_id` | string | 当前操作用户 ID（v1 预留，留空待接入） |
| `message` | string | 日志正文 |

### 访问日志（`log_type=access`，由 AccessLogMiddleware 写入）

| 字段 | 类型 | 说明 |
|---|---|---|
| `method` | string | 请求方法 |
| `path` | string | 请求路径 |
| `status` | int | HTTP 状态码 |
| `duration_ms` | float | 请求耗时（毫秒） |
| `query` | object | Query 参数结构化 dict（`?a=1&b=2` → `{"a":"1","b":"2"}`），字符串保真、重复键取最后值，解析后脱敏 |
| `remote_addr` | string | 客户端 IP（受 `LOG_TRUST_PROXY_HEADERS` 控制） |
| `user_agent` | string | User-Agent |
| `referer` | string | Referer |
| `request_body` | object/string | 请求 Body（仅 `LOG_ACCESS_BODY=true` 且 DEBUG 模式） |
| `response_body` | object/string | 响应 Body（同上） |
| `slow` | bool | 慢请求标记（仅慢请求时出现） |

> 注：`query` / `remote_addr` / `user_agent` / `referer` / `request_body` / `response_body` 仅在 DEBUG 模式输出，生产环境默认不输出以控制日志量。

### 业务日志（`log_type=app`，由业务代码通过 `get_app_logger` 写入）

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | string | 业务动作（create / update / delete / 审核 / 发布 …） |
| `success` | bool | 处理结果 |
| `error_code` | int | 业务码（对齐 `ApiCode`） |
| `entity_type` | string | 操作对象类型 |
| `entity_id` | string | 操作对象 ID |
| `duration_ms` | float | 业务耗时（毫秒） |
| `context` | object | 业务附加上下文（非敏感信息） |

### 错误日志（`log_type=error`，由异常处理器写入）

| 字段 | 类型 | 说明 |
|---|---|---|
| `exc_type` | string | 异常类名 |
| `error_code` | int | 业务码 |
| `traceback` | string | 完整堆栈（仅 ERROR 及以上） |
| `method` | string | 请求方法 |
| `path` | string | 请求路径 |

### 异常请求与堆栈保存

- `AccessLogMiddleware` 在下游抛出异常时仍记录一条 `status=500` 的访问日志，然后原样重新抛出。
- 全局异常处理器显式使用异常对象的 `__traceback__`，不依赖隐式 `sys.exc_info()`，确保完整调用链写入 `traceback`。
- JSON 日志保持单行输出，因此堆栈换行在原始文件/终端中编码为 `\n`；JSON 解析后会恢复为真正的多行文本，这不是截断。
- `request_id` 同时保存在请求上下文和 `request.state`，确保异常越过用户中间件后，访问日志、错误日志和 500 响应仍可关联。

## 字段命名约定

- **字段名全局唯一**，不允许不同模块自行定义同义字段
- 业务日志扩展字段统一使用 `context` 对象承载，避免顶层字段膨胀
- 新增字段须在本文档登记后方可使用

## 日志分类与文件路由

```
backend/logs/
├── access.log   ← log_type=access, 级别 < ERROR
├── app.log      ← log_type=app,    级别 < ERROR
└── error.log    ← 任意 log_type,   级别 >= ERROR（含完整堆栈）
```

- 所有输出均为**单行 JSON**
- 文件轮转：`10MB × 5`（`RotatingFileHandler`），避免日志无限增长
- 链路关联依赖字段（`trace_id` / `request_id` / `task_id` / `user_id`），不依赖文件归属，未来可平滑迁移到 Loki / ELK

## 敏感信息脱敏

脱敏集中在日志基础设施层（`app/core/logging.py` 的 `sanitize`），业务代码无需自行处理。

### 键名匹配（大小写不敏感、子串命中）

`password` / `passwd` / `token` / `access_token` / `refresh_token` / `authorization` / `cookie` / `api_key` / `apikey` / `secret` / `client_secret` / `credential`

命中后整值置 `"***"`。

### 值形态正则（作用于字符串）

- 身份证号（18 位，末位可 X）：前 6 + `********` + 后 4
- 手机号（11 位，1[3-9] 开头）：前 3 + `****` + 后 4
- 银行卡号（13~19 位）：前 6 + `******` + 后 4
- 邮箱：本地部分首字符 + `***` + `@domain`

### 作用范围

- Query 参数（解析后递归脱敏）
- 业务日志 `context` 对象
- 访问日志 Body 采样内容
- 日志正文 `message`

## 使用示例

### 业务代码

```python
from app.core.logging import get_app_logger

logger = get_app_logger(__name__)

# 正常流程
logger.info("文章创建成功", extra={
    "action": "create",
    "entity_type": "article",
    "entity_id": "123",
    "success": True,
    "duration_ms": 42.5,
})

# 业务失败
logger.warning("库存不足", extra={
    "action": "deduct",
    "entity_type": "sku",
    "entity_id": "456",
    "success": False,
    "error_code": 40901,
    "context": {"requested": 10, "available": 3},
})
```

### 错误日志

```python
from app.core.logging import get_error_logger

error_logger = get_error_logger(__name__)

try:
    ...
except Exception:
    error_logger.exception("处理失败", extra={"action": "sync", "entity_type": "order"})
```

## 禁止事项

- **禁止使用 `print`**（业务日志一律走 Logger）
- **禁止业务代码自行处理 request_id / 耗时 / 日志格式 / 脱敏**
- **禁止因 `logger.info(request.dict())` 等操作把敏感信息直接写入日志**
- **禁止擅自调整日志基础设施架构**（修改 `app/core/logging.py` 须同步更新本文档）

## 未来扩展点

- `trace_id`：接入 OpenTelemetry 完整链路追踪
- `task_id`：接入 Celery 异步任务追踪
- `user_id`：接入认证体系后自动注入当前用户
- 输出目标：本地文件 → Loki / ELK → Grafana（业务层日志结构无需改动）
