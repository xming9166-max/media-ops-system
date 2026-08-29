# Backend AGENTS.md

## 后端职责

Backend 负责：

- HTTP API
- 业务逻辑
- 数据访问
- 数据持久化
- 异步任务
- 缓存
- 第三方服务集成

后端必须保持模块化、高内聚、低耦合。

---

# Python 环境

Python 项目统一使用 `uv` 管理。

禁止：

```bash
pip install
pip3 install
python -m venv
```

禁止使用系统 Python 安装项目依赖。

统一使用：

```bash
uv add <package>
uv sync
uv run <command>
```

Python 版本由：

```text
.python-version
```

管理。

当前项目：

```text
Python 3.12
```

虚拟环境必须位于：

```text
backend/.venv/
```

---

# FastAPI 架构

后端业务依赖方向：

```text
Router
   ↓
Service
   ↓
Repository
   ↓
Database
```

依赖只能按照上述方向流动。

禁止反向依赖。

---

# Router

Router 只负责 HTTP 层。

职责：

- 接收请求
- Request 参数处理
- Schema 校验
- 调用 Service
- 返回 Response
- HTTP 状态码

Router 禁止：

- 直接访问数据库
- 直接调用 ORM
- 直接执行 SQL
- 编写复杂业务逻辑
- 直接调用 Repository

正确：

```text
Router
   ↓
Service
   ↓
Repository
```

---

# Service

Service 负责业务逻辑。

职责：

- 业务规则
- 业务流程
- 权限业务判断
- 状态转换
- 事务边界
- 并发控制
- 调用 Repository

Service 不负责：

- HTTP 细节
- SQL 实现
- ORM 底层细节

---

# Repository

Repository 负责数据访问。

职责：

- 查询
- 新增
- 创建版本
- 数据更新
- 数据库访问封装
- 锁相关查询

Repository 不负责：

- HTTP
- 业务流程
- API Response
- 页面逻辑

Repository 必须隐藏数据库实现细节。

---

# Schema

Schema 负责：

- Request 校验
- Response 结构
- 序列化
- 反序列化

Schema 不负责：

- 业务逻辑
- 数据库操作

---

# Model

Model 负责：

- ORM 映射
- 表结构
- 字段
- 数据库关系

Model 不负责：

- 业务流程
- HTTP
- Service 逻辑

---

# 后端模块结构

业务模块推荐：

```text
app/
├── core/
├── modules/
│   ├── content/
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schema.py
│   │   └── model.py
│   │
│   ├── media/
│   ├── publishing/
│   └── analytics/
│
└── main.py
```

业务模块必须保持独立。

禁止：

```text
content
 ↓
直接操作
 ↓
publishing 内部 Repository
```

跨模块调用应该通过明确的 Service / Interface / Domain 能力完成。

---

# 数据版本管理

需要保留历史的数据必须版本化。

例如：

```text
content_id = 1001

version = 1
version = 2
version = 3
```

version = 3 为最新版本。

历史版本永久保留。

禁止：

```sql
UPDATE
```

直接覆盖历史版本并造成历史数据丢失。

---

# 默认读取最新版本

所有普通 Repository 查询默认返回最新版本。

推荐统一封装：

```python
get_latest(...)
```

业务代码禁止到处重复编写：

```sql
ORDER BY version DESC
LIMIT 1
```

历史版本必须显式指定：

```python
get_version(..., version=2)
```

---

# 默认写入最新版本

普通修改流程：

```text
Service
   ↓
获取最新版本
   ↓
业务校验
   ↓
版本校验
   ↓
创建新版本
   ↓
version + 1
   ↓
提交事务
```

禁止直接覆盖历史版本。

---

# 乐观锁

对于存在并发修改可能的数据：

**默认优先使用乐观锁。**

例如：

```text
当前版本：

version = 3
```

客户端提交：

```text
expected_version = 3
```

事务中检查当前最新版本。

如果：

```text
3 == 3
```

允许创建：

```text
version = 4
```

如果：

```text
4 != 3
```

必须认为发生并发冲突。

禁止覆盖其他请求产生的新版本。

---

# 悲观锁

只有确实存在高竞争资源时才使用悲观锁。

例如：

```sql
SELECT ...
FOR UPDATE
```

适用于：

- 库存
- 配额
- 余额
- 唯一资源
- 高竞争计数器
- 必须串行处理的状态

禁止普通查询无差别使用：

```sql
FOR UPDATE
```

---

# 锁原则

优先使用：

```text
行锁
```

避免：

```text
表锁
```

锁的范围必须尽可能小。

事务必须尽可能短。

涉及多个资源时必须保持统一的加锁顺序。

例如：

```text
Content
 ↓
ContentVersion
 ↓
PublishTask
```

避免：

```text
事务 A：

锁 A
 ↓
锁 B


事务 B：

锁 B
 ↓
锁 A
```

防止死锁。

---

# 事务

所有具有业务关联的数据变更必须保持事务一致性。

例如：

```text
创建内容
+
创建版本
+
创建操作记录
```

必须：

```text
全部成功
```

或者：

```text
全部回滚
```

---

# Service 事务边界

事务边界原则上由 Service 控制。

推荐：

```text
Service
 ↓
BEGIN
 ↓
Repository A
 ↓
Repository B
 ↓
Repository C
 ↓
COMMIT
```

异常：

```text
ROLLBACK
```

Repository 不应该自行创建独立事务。

---

# 短事务原则

禁止在数据库事务中执行耗时操作。

禁止：

```text
BEGIN
 ↓
调用 AI
 ↓
等待第三方 API
 ↓
等待 10 秒
 ↓
COMMIT
```

应该：

```text
准备数据
 ↓
调用外部 API
 ↓
获得结果
 ↓
BEGIN
 ↓
快速写入数据库
 ↓
COMMIT
```

---

# 死锁

必须考虑数据库死锁。

发生死锁时：

1. 回滚事务
2. 识别死锁异常
3. 对安全操作进行有限重试
4. 使用指数退避
5. 超过最大重试次数后失败
6. 记录日志

禁止无限重试。

---

# 幂等

所有可能重复执行的操作必须考虑幂等。

重点包括：

- 创建任务
- 发布任务
- Celery Task
- 定时任务
- Webhook
- 第三方回调
- AI Task

可使用：

- 唯一业务 ID
- 幂等 Key
- UNIQUE
- 状态机
- version

---

# Celery

Celery Task 不能假设只执行一次。

必须考虑：

```text
Task
 ↓
Worker 崩溃
 ↓
Retry
```

因此 Task 必须尽可能幂等。

对于不可重复执行的操作：

必须设计幂等机制。

---

# 状态机

复杂业务状态必须通过明确状态机管理。

例如：

```text
draft
 ↓
reviewing
 ↓
approved
 ↓
publishing
 ↓
published
```

状态转换必须由 Service 完成。

禁止 Router 直接修改状态。

---

# 数据库约束

关键数据一致性不能只依赖 Python。

必须尽可能使用数据库约束：

- PRIMARY KEY
- UNIQUE
- FOREIGN KEY
- NOT NULL
- CHECK
- INDEX

原则：

```text
Application Validation
        +
Database Constraint
```

共同保证数据正确性。

---

# 唯一约束

对于业务唯一数据：

优先使用数据库 UNIQUE。

禁止只依赖：

```python
if not exists:
    create()
```

高并发情况下必须由数据库最终保证唯一性。

---

# MySQL

MySQL 是后端最终数据源。

数据库设计必须考虑：

- 索引
- 查询性能
- 事务
- 锁
- 死锁
- 连接池
- 数据完整性

禁止为了方便而创建大量无意义索引。

---

# 数据库连接池

必须使用数据库连接池。

连接池大小必须根据：

- 实际并发量
- MySQL 最大连接数
- API Worker 数量
- 查询耗时

综合确定。

禁止无依据设置超大连接池。

---

# Redis

Redis 默认作为：

```text
Cache
```

使用。

MySQL：

```text
Source of Truth
```

Redis：

```text
Cache
```

涉及 MySQL + Redis 时必须明确：

- 缓存写入时机
- 缓存失效时机
- 缓存一致性
- 缓存击穿
- 缓存穿透
- 缓存雪崩

---

# MySQL + Redis 一致性

不能假设：

```text
MySQL
+
Redis
```

天然具备原子事务。

跨系统一致性根据场景使用：

- Transactional Outbox
- 消息队列
- 事件驱动
- 重试
- 幂等
- 最终一致性

---

# 外部 API

禁止在数据库事务中长时间等待外部服务。

推荐：

```text
创建任务
 ↓
COMMIT
 ↓
Celery
 ↓
第三方 API
 ↓
获得结果
 ↓
短事务
 ↓
创建新版本 / 更新状态
 ↓
COMMIT
```

---

# 数据删除

Backend 禁止任何形式的数据删除。

禁止：

```sql
DELETE FROM ...
```

禁止：

```python
session.delete(...)
```

禁止：

```python
repository.delete(...)
```

禁止增加：

```text
deleted_at
is_deleted
```

等软删除机制。

如果业务明确要求删除：

**必须停止实现并向用户确认。**

---

# 高并发原则

后端必须考虑高并发场景。

优先：

```text
无状态 API
+
连接池
+
索引
+
短事务
+
乐观锁
+
幂等
+
缓存
+
异步任务
```

避免：

```text
长事务
+
大范围锁
+
锁表
+
同步执行耗时任务
+
N+1 查询
+
重复查询
```

---

# 后端测试

新增后端功能必须考虑测试。

至少覆盖：

- 正常流程
- 参数错误
- 业务异常
- 数据库异常
- 并发冲突
- 重复请求
- 事务回滚

涉及版本控制的功能必须测试：

```text
version 1
 ↓
version 2
 ↓
version 3
```

并验证历史版本不会丢失。

---

# 后端开发流程

修改 Backend 代码：

```text
读取根目录 AGENTS.md
        ↓
读取 backend/AGENTS.md
        ↓
检查 backend 当前结构
        ↓
理解相关模块
        ↓
制定最小修改方案
        ↓
实现
        ↓
测试
        ↓
Review
        ↓
汇报
```

---

# 后端汇报规范

完成任务后：

```text
## Changes

修改了什么。

## Files

新增、修改、删除哪些文件。

## Verification

执行了什么测试。

## Database

如果涉及数据库：

- 事务
- 锁
- 版本
- 索引
- 并发

分别说明。

## Git Diff

主要变更。

## Problems

发现的问题。

## Next Step

建议下一步。
```
