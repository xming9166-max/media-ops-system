"""日志上下文管理模块。

基于 contextvars 实现请求级 / 任务级上下文的隔离，为结构化日志提供统一字段：

- ``trace_id``：完整业务链路 ID（缺省回落到 request_id）
- ``request_id``：当前 HTTP 请求 ID（由 app.core.request_id 管理，本模块只读）
- ``task_id``：异步任务 / Celery / 后台任务 ID（v1 预留，留空待接入）
- ``user_id``：当前操作用户 ID（v1 预留，留空待接入）
- ``request_start_time``：请求起始时间戳（perf_counter），仅 AccessLogMiddleware 内部使用

约定：
- 请求级字段由中间件在请求进入时 set、结束时 reset，防止跨请求 / 跨任务泄漏。
- 业务代码只读（通过 ``get_*`` 取值）；写入由中间件或任务入口统一负责。
"""

import time
import uuid
from contextvars import ContextVar, Token

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_task_id_var: ContextVar[str] = ContextVar("task_id", default="")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")
_request_start_time_var: ContextVar[float] = ContextVar("request_start_time", default=0.0)


def get_trace_id() -> str:
    """返回当前链路 ID；未设置时返回空字符串（由日志层回落到 request_id）。"""
    return _trace_id_var.get()


def set_trace_id(trace_id: str | None = None) -> Token[str]:
    """设置当前链路 ID：优先复用传入值，否则生成 UUID4。

    返回 Token，调用方应在请求 / 任务结束时通过 :func:`reset_trace_id` 恢复。
    """
    tid = trace_id or str(uuid.uuid4())
    return _trace_id_var.set(tid)


def reset_trace_id(token: Token[str]) -> None:
    """将链路 ID 恢复为设置前的状态，防止跨请求 / 跨任务泄漏。"""
    _trace_id_var.reset(token)


def get_task_id() -> str:
    """返回当前任务 ID；未设置时返回空字符串（v1 预留）。"""
    return _task_id_var.get()


def set_task_id(task_id: str | None = None) -> Token[str]:
    """设置当前任务 ID：优先复用传入值，否则生成 UUID4。

    返回 Token，调用方应在任务结束时通过 :func:`reset_task_id` 恢复。
    """
    tid = task_id or str(uuid.uuid4())
    return _task_id_var.set(tid)


def reset_task_id(token: Token[str]) -> None:
    """将任务 ID 恢复为设置前的状态，防止跨任务泄漏。"""
    _task_id_var.reset(token)


def get_user_id() -> str:
    """返回当前操作用户 ID；未设置时返回空字符串（v1 预留）。"""
    return _user_id_var.get()


def set_user_id(user_id: str | None = None) -> Token[str]:
    """设置当前操作用户 ID。

    返回 Token，调用方应在请求结束时通过 :func:`reset_user_id` 恢复。
    """
    uid = user_id or ""
    return _user_id_var.set(uid)


def reset_user_id(token: Token[str]) -> None:
    """将用户 ID 恢复为设置前的状态，防止跨请求泄漏。"""
    _user_id_var.reset(token)


def get_request_start_time() -> float:
    """返回请求起始时间戳（perf_counter）；未设置时返回 0.0。"""
    return _request_start_time_var.get()


def set_request_start_time(start_time: float | None = None) -> Token[float]:
    """设置请求起始时间戳；缺省使用 ``time.perf_counter()``。

    返回 Token，调用方应在请求结束时通过 :func:`reset_request_start_time` 恢复。
    """
    st = start_time if start_time is not None else time.perf_counter()
    return _request_start_time_var.set(st)


def reset_request_start_time(token: Token[float]) -> None:
    """将请求起始时间戳恢复为设置前的状态，防止跨请求泄漏。"""
    _request_start_time_var.reset(token)


__all__: list[str] = [
    "get_trace_id",
    "set_trace_id",
    "reset_trace_id",
    "get_task_id",
    "set_task_id",
    "reset_task_id",
    "get_user_id",
    "set_user_id",
    "reset_user_id",
    "get_request_start_time",
    "set_request_start_time",
    "reset_request_start_time",
]
