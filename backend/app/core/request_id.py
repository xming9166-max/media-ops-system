"""请求 ID 管理模块。

基于 contextvars 实现请求级 request_id 的隔离：

- 客户端通过 `X-Request-ID` 请求头传入时复用该值
- 未传入时由后端生成 UUID4
- 请求结束时由中间件 reset，防止串到其他请求/任务

约定见 docs/http/api-contract.md。
"""

import uuid
from contextvars import ContextVar, Token

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """返回当前请求 ID；未设置时生成一个并写入上下文（兜底）。"""
    request_id = _request_id_var.get()
    if not request_id:
        request_id = str(uuid.uuid4())
        _request_id_var.set(request_id)
    return request_id


def set_request_id(request_id: str | None = None) -> Token[str]:
    """设置当前请求 ID：优先复用传入值，否则生成 UUID4。

    返回 Token，调用方应在请求结束时通过 :func:`reset_request_id` 恢复。
    """
    rid = request_id or str(uuid.uuid4())
    return _request_id_var.set(rid)


def reset_request_id(token: Token[str]) -> None:
    """将请求 ID 恢复为设置前的状态，防止跨请求/跨任务泄漏。"""
    _request_id_var.reset(token)