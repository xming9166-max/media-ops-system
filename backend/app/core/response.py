"""统一 API 响应封装。

提供 `ApiResponse` 基础类：只需传入 http 状态码、业务状态码、message、data，
自动生成符合 docs/http/api-contract.md 的响应结构，并注入当前请求的 request_id。
"""

from typing import Any

from fastapi.responses import JSONResponse

from app.core.request_id import get_request_id


class ApiResponse(JSONResponse):
    """统一响应，格式约定见 docs/http/api-contract.md。"""

    def __init__(
        self,
        http_status: int = 200,
        code: int = 0,
        message: str = "ok",
        data: Any = None,
    ) -> None:
        body = {
            "code": code,
            "message": message,
            "data": data,
            "request_id": get_request_id(),
        }
        super().__init__(status_code=http_status, content=body)

    @classmethod
    def success(cls, data: Any = None, message: str = "ok") -> "ApiResponse":
        """成功响应：HTTP 200 / 业务码 0。"""
        return cls(http_status=200, code=0, message=message, data=data)

    @classmethod
    def error(
        cls,
        http_status: int,
        code: int,
        message: str,
        data: Any = None,
    ) -> "ApiResponse":
        """失败响应：显式指定 HTTP 状态码与业务码。"""
        return cls(
            http_status=http_status,
            code=code,
            message=message,
            data=data,
        )