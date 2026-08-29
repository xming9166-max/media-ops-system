"""请求级中间件。"""

from typing import Any, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_id import get_request_id, reset_request_id, set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求建立统一 request_id。

    - 请求进入时：优先复用请求头 `X-Request-ID`，否则由后端生成 UUID4
    - 响应返回时：写入 `X-Request-ID` 响应头，便于前后端对齐追踪
    - 请求结束：reset 上下文，防止泄漏到其他请求
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        token = set_request_id(request.headers.get("X-Request-ID"))
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = get_request_id()
            return response
        finally:
            reset_request_id(token)


__all__: list[str] = ["RequestIDMiddleware"]