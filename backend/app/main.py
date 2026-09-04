from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import ApiCode, ApiException
from app.core.logging import get_app_logger, get_error_logger, setup_logging
from app.core.middleware import AccessLogMiddleware, CommitMiddleware, RequestIDMiddleware
from app.core.request_id import reset_request_id, set_request_id
from app.core.response import ApiResponse

# 装配日志系统（幂等，须在首次使用 logger 前调用）
setup_logging()

app_logger = get_app_logger(__name__)
error_logger = get_error_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# 中间件注册顺序：后添加者更外层。
# RequestID 最外层（设置 request_id 上下文）→ AccessLog 在其内层（写日志时 request_id 仍存活）
# → Commit 在其内层（业务返回后兜底提交/回滚）→ CORS 最内层
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CommitMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(ApiException)
async def api_exception_handler(request: Request, exc: ApiException) -> ApiResponse:
    """业务异常统一转为契约响应（预期流程，WARNING，不记堆栈）。"""
    app_logger.warning(
        "api error: path=%s code=%s message=%s",
        request.url.path,
        exc.code,
        exc.message,
        extra={
            "path": request.url.path,
            "error_code": exc.code,
            "action": "api_reject",
            "success": False,
        },
    )
    return ApiResponse.error(
        http_status=exc.http_status,
        code=exc.code,
        message=exc.message,
        data=exc.data,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> ApiResponse:
    """参数校验失败统一返回 422 / 40000（预期流程，WARNING，不记堆栈）。"""
    app_logger.warning(
        "validation error: path=%s errors=%s",
        request.url.path,
        exc.errors(),
        extra={
            "path": request.url.path,
            "action": "validate",
            "success": False,
            "error_code": ApiCode.PARAM_ERROR,
        },
    )
    return ApiResponse.error(
        http_status=422,
        code=ApiCode.PARAM_ERROR,
        message="参数错误",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> ApiResponse:
    """未捕获异常统一兜底为 500 / 50000，不向外泄露内部细节（ERROR，含完整堆栈）。"""
    # ServerErrorMiddleware 在用户中间件栈外处理异常；从 request.state 恢复原 request_id。
    request_id = getattr(request.state, "request_id", None)
    token = set_request_id(request_id) if request_id else None
    try:
        error_logger.error(
            "unhandled exception: %s %s: %s",
            request.method,
            request.url.path,
            exc,
            extra={
                "method": request.method,
                "path": request.url.path,
                "error_code": ApiCode.INTERNAL_ERROR,
                "exc_type": type(exc).__name__,
            },
            # 显式传递原始 traceback，不依赖异常处理器执行时的 sys.exc_info()。
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        response = ApiResponse.error(
            http_status=500,
            code=ApiCode.INTERNAL_ERROR,
            message="服务器内部错误",
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response
    finally:
        if token is not None:
            reset_request_id(token)


@app.get(f"{settings.api_v1_prefix}/health")
async def health_check() -> ApiResponse:
    """Health check endpoint."""
    return ApiResponse.success(data={"status": "ok"})
