"""业务异常与业务状态码定义，对齐 docs/http/api-contract.md。"""

from typing import Any


class ApiException(Exception):
    """业务异常：携带 HTTP 状态码、业务状态码与描述。

    由全局异常处理器统一转换为 ApiResponse 格式返回。
    """

    def __init__(
        self,
        http_status: int,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        self.http_status = http_status
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class ApiCode:
    """业务状态码常量（见 docs/http/api-contract.md 状态码表）。"""

    SUCCESS = 0
    PARAM_ERROR = 40000
    UNAUTHORIZED = 40100
    FORBIDDEN = 40300
    NOT_FOUND = 40400
    CONFLICT = 40900
    INTERNAL_ERROR = 50000
